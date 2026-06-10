# Architecture

## Flux de données

```
                          ┌─────────────┐
                     ┌──► │ Prometheus  │
                     │    └──────┬──────┘
┌──────────────┐     │           │ scrape /metrics
│   FastAPI    │─────┤           ▼
│  /predict    │     │    ┌─────────────┐
│  /health     │     │    │   Grafana   │◄── datasource ES + Prometheus
│  /metrics    │     │    └─────────────┘
└──────┬───────┘     │
       │             │    ┌─────────────┐
       │ stdout JSON  └──►│  Fluentd    │
       │                  └──────┬──────┘
       │                         │
       │                         ▼
       │                  ┌─────────────┐
       │                  │Elasticsearch│
       │                  └─────────────┘
       │                         ▲
       │                         │
┌──────┴───────┐                 │
│  Streamlit   │─────────────────┘
│  (Evidently) │   datasource ES pour drift
└──────────────┘
```

## Stack

| Composant | Techno | Rôle |
|---|---|---|
| API | FastAPI + Pydantic | Scoring, endpoints |
| Modèle | LightGBM (pickle P6) | InferencePipeline complet |
| Logs structurés | JSON → Fluentd → Elasticsearch | Prédictions, latence, erreurs |
| Métriques | prometheus_client → Prometheus | Latence, taux erreur, volume |
| Dashboards | Grafana | Métriques temps réel + historique prédictions |
| Drift ML | Evidently AI + Streamlit | Data drift, distribution scores |
| Tests | pytest + httpx | Unit + integration, 90% coverage |
| Conteneurisation | Docker Compose | 6 services |
| CI/CD | GitHub Actions → HF Spaces | Lint, test, build, deploy |

## Docker Compose

6 services :

| Service | Image | Rôle |
|---|---|---|
| `api` | Custom (FastAPI + uvicorn) | API de scoring |
| `elasticsearch` | `elasticsearch:8.x` | Stockage des logs |
| `fluentd` | Custom (conf Fluentd) | Collecte des logs (Docker logging driver) |
| `prometheus` | `prometheus/prometheus` | Scraping métriques |
| `grafana` | `grafana/grafana` | Dashboards |
| `streamlit` | Custom | Dashboard drift Evidently |

## Structure du repo

```
.
├── docs/
│   ├── CONTEXT.md              # Mission, modèle source, objectif
│   ├── ARCHITECTURE.md         # Ce fichier
│   ├── DECISIONS.md            # Registre des choix délibérés
│   ├── ROADMAP.md              # Phases d'implémentation
│   └── STACK.md                # Stack technique validée
├── src/credit_risk_server/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app factory + exception handlers
│   │   ├── dependencies.py     # model + data_source injection via Depends
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── predict.py      # /predict (sk_ids), /predict/rows (JSON)
│   │   │   └── health.py       # /health
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── application.py   # Pydantic model table application
│   │       ├── bureau.py
│   │       ├── bureau_balance.py
│   │       ├── previous_application.py
│   │       ├── pos_cash_balance.py
│   │       ├── installments.py
│   │       ├── credit_card_balance.py
│   │       └── prediction.py    # Request/response schemas
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # pydantic-settings (AppSettings → ApiSettings)
│   │   ├── logging.py           # DevFormatter + JSONFormatter, correlation, Timer
│   │   └── exceptions.py       # PredictionError, InvalidInputError, ModelLoadError
│   ├── data/
│   │   ├── __init__.py          # public API: assemble, DataSource, make_source
│   │   ├── assembler.py         # assemble(source, sk_ids) → dict[str, DataFrame]
│   │   ├── factory.py           # make_source(settings) → DataSource | None
│   │   ├── source.py            # DataSource protocol + TABLE_NAMES + CSV_NAME_MAP
│   │   └── sources/
│   │       ├── __init__.py
│   │       ├── polars.py        # PolarsDataSource (PLLazyDataLoader adapter)
│   │       └── sql.py           # SqlDataSource (placeholder)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── loader.py            # load InferencePipeline pickle
│   │   └── predictor.py         # predict() + predict_from_tables() (no FastAPI dep)
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── drift.py             # Evidently drift detection
│   │   └── metrics.py           # Prometheus metrics (Histogram, Counter)
│   └── dashboard/
│       ├── __init__.py
│       └── app.py               # Streamlit app
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   └── data/
│   │       └── test_data_pipeline.py
│   └── integration/
├── docker/
│   ├── api/Dockerfile
│   ├── streamlit/Dockerfile
│   ├── fluentd/fluent.conf
│   ├── prometheus/prometheus.yml
│   └── grafana/
│       ├── datasources/
│       └── dashboards/
├── .env.example                 # shared + API sections
├── .env.api                     # API-specific vars (gitignored)
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── AGENTS.md
├── docker-compose.yml
├── LICENSE
├── pyproject.toml
├── README.md
└── uv.lock
```

## Conventions

### Exceptions custom

Le métier ne dépend pas de FastAPI. `predictor.py` lève des exceptions custom, les routes les catchent et les mappent en HTTP.

```python
# core/exceptions.py
class PredictionError(Exception): ...
class InvalidInputError(PredictionError): ...
class ModelLoadError(PredictionError): ...

# models/predictor.py — aucun import FastAPI
raise InvalidInputError("missing bureau data")

# api/main.py — handler global
@app.exception_handler(InvalidInputError)
async def invalid_input_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})
```

### Dependency groups séparés

Streamlit et FastAPI ont des cycles de vie différents. Chaque service a ses propres dépendances.

```toml
[dependency-groups]
api = ["fastapi", "uvicorn", "prometheus-client", "elasticsearch"]
dashboard = ["streamlit", "evidently"]
dev = ["pytest", "ruff", "pre-commit", "httpx", "ty"]
```

### Branching

GitHub Flow simplifié : `main` + branches courtes. Pas de PR formelle, merge direct après validation locale (pre-push hook).
