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
- [ ] Sortie stdout (capté par Promtail via Docker json-file driver)
- [ ] Données de démo pour tester le pipeline de logs

## 5. Conteneurisation (Docker)

- [ ] `docker/api/Dockerfile` (FastAPI + uvicorn)
- [ ] `docker/prometheus/prometheus.yml`
- [ ] `docker/promtail/config.yml`
- [ ] `docker/loki/config.yml`
- [ ] `docker/grafana/datasources/` (Prometheus + Loki) + `dashboards/`
- [ ] `docker-compose.yml` (5 services : api, prometheus, loki, promtail, grafana)
- [ ] Tester le stack complet en local
- [ ] Tester l'API conteneurisée

## 6. Monitoring API (Prometheus + Grafana)

- [x] `monitoring/metrics.py` — HTTP metrics + business metrics (predictions, latency, model_loaded)
- [x] Port 9100 séparé pour `/metrics` (D-18)
- [ ] Configurer Prometheus pour scraper `api:9100`
- [ ] Datasources Grafana : Prometheus + Loki
- [ ] Dashboard Grafana : latence, taux erreur, volume requêtes, distribution scores
- [ ] Captures d'écran pour la documentation

## 7. Drift & monitoring avancé

- [ ] `monitoring/drift.py` — métriques de drift exposées via Prometheus
- [ ] Afficher dans Grafana :
  - [ ] distribution des scores
  - [ ] indicateurs de data drift
  - [ ] latence API (depuis Loki via LogQL)
  - [ ] volume de requêtes
  - [ ] erreurs éventuelles
- [ ] Captures d'écran

## 8. CI/CD

- [ ] GitHub Actions workflow
- [ ] Pipeline CI : lint → tests → build Docker
- [ ] Pipeline CD : déploiement auto sur Hugging Face Spaces
- [ ] Secrets GitHub si nécessaire

## 9. Optimisation post-déploiement

- [ ] Benchmark API (latence, temps d'inférence, mémoire CPU/RAM)
- [ ] Identifier goulots d'étranglement
- [ ] Tester optimisation :
  - [ ] joblib compression
  - [ ] preprocessing optimisé
  - [ ] batch inference (si pertinent)
- [ ] Comparer avant/après

## 10. Documentation finale

- [ ] README complet (instructions de lancement, Docker, monitoring)
- [ ] Justification des choix techniques (référence DECISIONS.md)
- [ ] Captures d'écran (API, Grafana, drift)
- [ ] Archiver les dernières décisions dans DECISIONS.md
