# Architecture

## Flux de données

```
                           ┌─────────────┐
                      ┌──► │ Prometheus  │
                      │    └──────┬──────┘
┌──────────────┐     │           │ scrape :9100
│   FastAPI    │─────┤           ▼
│  /predict    │     │    ┌─────────────┐
│  /health     │     │    │   Grafana   │◄── datasource Loki + Prometheus
│ :8000/:9100 │     │    └─────────────┘
└──────┬───────┘     │
       │             │    ┌─────────────┐
       │ stdout JSON  └──►│  Promtail   │
       │                  └──────┬──────┘
       │                         │
       │                         ▼
       │                  ┌─────────────┐
       │                  │    Loki      │
       │                  └─────────────┘
       │
       │  Evidently Snapshot
       ▼
┌──────────────┐     ┌─────────────────┐
│  DriftMonitor│────►│ Evidently UI    │
│ (drift.py)   │ ws  │ :8501           │
└──────────────┘     └─────────────────┘
  bind mount ./workspace (shared)
```

## Stack

| Composant | Techno | Rôle |
|---|---|---|
| API | FastAPI + Pydantic | Scoring, endpoints |
| Modèle | LightGBM (pickle P6) | InferencePipeline complet |
| Logs structurés | JSON stdout → Promtail → Loki | Prédictions, latence, erreurs |
| Métriques | prometheus_client → Prometheus (port 9100) | Latence, taux erreur, volume, prédictions |
| Dashboards | Grafana | HTTP, latence, erreurs, hardware, logs |
| Drift ML | Evidently UI (`evidently-ui` :8501) | PSI par feature, distribution scores, drifted-columns count |
| Tests | pytest + httpx | Unit + integration, 90% coverage |
| Conteneurisation | Docker Compose | 6 services (+ node-exporter, cadvisor) |
| CI/CD | GitHub Actions → HF Spaces | Lint, test, build, deploy |

## Docker Compose

6 services principaux (+ 2 exporters) :

| Service | Image | Rôle |
|---|---|---|
| `api` | Custom (FastAPI + uvicorn) | API de scoring + DriftMonitor |
| `prometheus` | `prom/prometheus` | Scraping métriques (:9100) |
| `loki` | `grafana/loki` | Stockage des logs |
| `promtail` | `grafana/promtail` | Collecte des logs (Docker json-file) |
| `grafana` | `grafana/grafana` | Dashboards (datasources Prometheus + Loki) |
| `evidently-ui` | Custom (python:3.12-slim + evidently) | UI drift ML (:8501, workspace partagé) |
| `node-exporter` | `prom/node-exporter` | Hardware metrics (CPU, RAM, disk) |
| `cadvisor` | `gcr.io/cadvisor/cadvisor` | Container metrics (CPU, mémoire par conteneur) |

## Structure du repo

```
.
├── artifacts/
│   └── inference_pipeline_debug.pkl  # InferencePipeline pickle (~5 Mo, self-contained)
├── data/                         # 7 CSV brutes + data/reference/ (drift snapshot, gitignored)
├── docs/
│   ├── CONTEXT.md              # Mission, modèle source, objectif
│   ├── ARCHITECTURE.md         # Ce fichier
│   ├── DECISIONS.md            # Registre des choix délibérés
│   ├── ROADMAP.md              # Phases d'implémentation
│   └── STACK.md                # Stack technique validée
├── scripts/
│   ├── build_reference.py      # snapshot de référence (scores + features parquet)
│   ├── predict_sampler.py      # échantillonneur de prédictions réel
│   └── traffic_simulator.py    # simulateur de trafic mixte (logs stdout Promtail-ready)
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
│   │   ├── drift.py             # Drift detection (Evidently UI — PSI, snapshots)
│   │   └── metrics.py           # Prometheus metrics (Histogram, Counter, Gauge)
│   └── (dashboard/ removed — see D-02)
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── api/
│   │   │   ├── test_dependencies.py
│   │   │   ├── test_main.py
│   │   │   └── test_schemas.py
│   │   ├── core/
│   │   │   ├── test_config.py
│   │   │   ├── test_exceptions.py
│   │   │   └── test_logging.py
│   │   ├── data/
│   │   │   ├── test_data_pipeline.py
│   │   │   └── test_factory.py
│   │   ├── models/
│   │   │   ├── test_loader.py
│   │   │   └── test_predictor.py
│   │   ├── monitoring/
│   │   │   ├── test_drift.py
│   │   │   └── test_metrics.py
│   │   └── test_critical_cases.py    # cas critiques: manquants, invalides, aberrants, vides
│   └── integration/
│       └── test_api.py
├── docker/
│   ├── api/Dockerfile
│   ├── evidently/Dockerfile       # Evidently UI (python:3.12-slim + evidently)
│   ├── prometheus/prometheus.yml
│   ├── promtail/config.yml
│   ├── loki/config.yml
│   └── grafana/
│       ├── datasources/
│       │   └── datasources.yml    # Prometheus + Loki
│       └── dashboards/
│           ├── dashboard.json          # API : latence, taux erreur, volume, scores
│           ├── dashboard-hardware.json # node-exporter + cadvisor
│           └── dashboard.yml           # provisioning
├── workspace/                    # Evidently UI workspace (bind mount, gitignored)
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

### Métriques Prometheus

Toutes les métriques sont centralisées dans `monitoring/metrics.py`. Les modules importent les objets nécessaires depuis ce module unique. L'exposition se fait sur un port séparé (9100) via `start_http_server()` dans le lifespan (voir D-18).

```python
# monitoring/metrics.py
from prometheus_client import Counter, Gauge, Histogram

REQUESTS_TOTAL = Counter("fastapi_requests_total", ...)
PREDICTIONS_TOTAL = Counter("credit_risk_predictions_total", ...)

# main.py — middleware utilise les imports depuis monitoring.metrics
# predictor.py — _run() observe PREDICTION_DURATION et incrémente PREDICTIONS_TOTAL
# loader.py — set MODEL_LOADED à 1 après chargement
```

### Dependency groups séparés

Seul l'API service a un dependency group dédié. Le groupe `dashboard` (Streamlit) est supprimé (D-02).

```toml
[dependency-groups]
api = ["fastapi", "uvicorn", "prometheus-client", ...]
dev = ["pytest", "ruff", "pre-commit", "httpx", "ty"]
```

### Branching

GitHub Flow simplifié : `main` + branches courtes. Pas de PR formelle, merge direct après validation locale (pre-push hook).
