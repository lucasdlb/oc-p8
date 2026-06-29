# Mission — Déployez et monitorez votre modèle de scoring

## 1. Initialisation du projet

- [x] Initialiser le dépôt Git
- [x] Définir une stratégie de branching (GitHub Flow simplifié — voir DECISIONS.md D-06)
- [x] Ajouter un `.gitignore`
- [x] Structurer le projet (`src/oc_p8/` layout)
- [x] Compléter le `.gitignore` (.env, htmlcov/, .ruff_cache, data/, etc.)
- [x] Ajouter un `.env.example` documentant les variables
- [x] Ajouter une LICENSE (MIT)
- [x] Ajouter des commits explicites
- [x] Pousser sur GitHub (repo public)

## 2. API de scoring

- [x] Développer l'app FastAPI (`src/credit_risk_server/api/main.py`)
- [x] Charger le modèle InferencePipeline UNE seule fois au démarrage (`dependencies.py`)
- [x] Endpoint `/predict` — sk_ids → DataSource → InferencePipeline — DATA_SOURCE configurable, 503 si absent
- [x] Endpoint `/predict/rows` — JSON row-oriented, pas de DataSource requis
- [x] Endpoint `/health`
- [x] Endpoint `/metrics` — port 9100 séparé via `start_http_server()` (voir D-18)
- [x] Schémas Pydantic pour les 7 tables (`api/schemas/`)
- [x] Exceptions custom découplées de FastAPI (`core/exceptions.py`)
- [x] Handlers globaux d'exceptions dans l'app
- [x] Documentation Swagger automatique
- [x] Config pydantic-settings avec Literal types (`core/config.py`)
- [x] Logging structuré JSON + DevFormatter avec extras (`core/logging.py`)
- [x] Data layer : DataSource protocol, PolarsDataSource, assembler, factory
- [x] Correlation middleware (X-Correlation-ID)

## 3-bis. Scripts utilitaires

- [x] `scripts/build_reference.py` — snapshot de référence (scores + features pour chaque table)
- [x] `scripts/predict_sampler.py` — échantillonneur de prédictions réel
- [x] `scripts/traffic_simulator.py` — simulateur de trafic mixte (health/predict/erreurs) avec logs stdout Promtail-ready

## 3. Tests automatisés

- [x] Tests unitaires data pipeline (assembler, PolarsDataSource, protocol)
- [x] Tests unitaires prédiction
- [x] Tests validation input (Pydantic schemas)
- [x] Cas critiques :
  - [x] données manquantes
  - [x] types invalides
  - [x] valeurs aberrantes
  - [x] tables vides
- [x] Tests d'intégration API (`TestClient` FastAPI + httpx)
- [x] Coverage ≥ 85% (89% atteint — lifespan et SQL source non testables sans infra)

## 4. Logging structuré

- [x] Correlation middleware (X-Correlation-ID propagé dans chaque log)
- [x] Format JSON structuré (production) + DevFormatter avec extras key=value (dev)
- [x] Configurable via `ENV=dev|prod` dans `.env`
- [x] Sortie stdout (capté par Promtail via Docker json-file driver)
- [x] Données de démo pour tester le pipeline de logs (`scripts/traffic_simulator.py`)

## 5. Conteneurisation (Docker)

- [x] `docker/api/Dockerfile` (FastAPI + uvicorn)
- [x] `docker/prometheus/prometheus.yml`
- [x] `docker/promtail/config.yml`
- [x] `docker/loki/config.yml`
- [x] `docker/grafana/datasources/` (Prometheus + Loki) + `dashboards/` (dashboard.json, dashboard-hardware.json)
- [x] `docker/evidently/Dockerfile` (Evidently UI python:3.12-slim)
- [x] `docker-compose.yml` (8 services : api, prometheus, loki, promtail, grafana, evidently-ui, node-exporter, cadvisor)
- [x] Tester le stack complet en local
- [x] Tester l'API conteneurisée

## 6. Monitoring API (Prometheus + Grafana)

- [x] `monitoring/metrics.py` — HTTP metrics + business metrics (predictions, latency, model_loaded)
- [x] Port 9100 séparé pour `/metrics` (D-18)
- [x] Configurer Prometheus pour scraper `api:9100` (prometheus.yml)
- [x] Datasources Grafana : Prometheus + Loki (datasources.yml)
- [x] Dashboard Grafana : latence, taux erreur, volume requêtes, distribution scores (dashboard.json 804 lignes)
- [ ] Captures d'écran pour la documentation

## 7. Drift & monitoring avancé

- [x] `monitoring/drift.py` — DriftMonitor (Evidently AI, PSI par feature + score)
- [x] `scripts/build_reference.py` — snapshot de référence (scores + features parquet)
- [x] Conteneur `evidently-ui` (:8501) — UI Evidently avec workspace partagé (D-02b)
- [x] Dashboard Evidently : drifted-columns count, score PSI, feature PSI, score quantiles
- [x] `DriftMonitor.record()` appelé après chaque prédiction (predictor.py)
- [x] Compute périodique asynchrone (60s, deque maxlen=5000, D-23)
- [ ] Afficher dans Grafana :
  - [ ] latence API (depuis Loki via LogQL)
  - [ ] volume de requêtes
  - [ ] erreurs éventuelles
- [ ] Captures d'écran (Grafana + Evidently UI)

## 8. CI/CD

- [x] GitHub Actions workflow (`.github/workflows/ci.yml` + `cd.yml`)
- [x] Pipeline CI : lint → format check → type check → tests (coverage ≥85%) + build Docker
- [x] Pipeline CD : déploiement auto sur Hugging Face Space (`workflow_run` sur CI succès)
- [x] Secrets GitHub (`HF_TOKEN`) — à configurer dans les repo settings

## 9. Optimisation post-déploiement

- [x] Benchmark API (latence, temps d'inférence, mémoire CPU/RAM) — `docs/benchmark.md`
- [x] Identifier goulots d'étranglement — profiling pyinstrument (I/O 72% `/predict`, Polars↔pandas 34% `/predict/rows`)
- [x] Tester optimisation :
  - [x] **ONNX Runtime** — LightGBM exporté vers ONNX, benchmark comparatif (scripts/bench_onnx.py)
  - [x] **Preprocessing optimisé** — cache schema (+11.5%) + bureau_balance lazy fix (+3.4%), **total +9%** (scripts/optimize_pipeline.py, `docs/benchmark.md §10`)
  - [ ] joblib compression
  - [ ] batch inference (si pertinent)
- [x] Comparer avant/après — voir `docs/benchmark.md §9` et `docs/benchmark/onnx_full.json`
- [x] Comparer avant/après preprocessing — voir `docs/benchmark.md §10` et `docs/benchmark/preprocessing_opt.json`

## 10. Documentation finale

- [ ] README complet (instructions de lancement, Docker, monitoring)
- [ ] Justification des choix techniques (référence DECISIONS.md)
- [ ] Captures d'écran (API, Grafana, drift)
- [ ] Archiver les dernières décisions dans DECISIONS.md
