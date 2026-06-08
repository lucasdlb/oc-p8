# Mission — Déployez et monitorez votre modèle de scoring

## 1. Initialisation du projet

- [x] Initialiser le dépôt Git
- [x] Définir une stratégie de branching (GitHub Flow simplifié — voir DECISIONS.md D-06)
- [x] Ajouter un `.gitignore`
- [x] Structurer le projet (`src/oc_p8/` layout)
- [x] Compléter le `.gitignore` (.env, htmlcov/, .ruff_cache, data/, etc.)
- [x] Ajouter un `.env.example` documentant les variables
- [x] Ajouter une LICENSE (MIT)
- [ ] Ajouter des commits explicites
- [ ] Pousser sur GitHub (repo public)

## 2. API de scoring

- [ ] Développer l'app FastAPI (`src/oc_p8/api/main.py`)
- [ ] Charger le modèle InferencePipeline UNE seule fois au démarrage (`dependencies.py`)
- [ ] Endpoint `/predict` — 7 tables brutes en entrée, pipeline complet P6
- [ ] Endpoint `/health`
- [ ] Endpoint `/metrics` (Prometheus format)
- [ ] Schémas Pydantic pour les 7 tables (`api/schemas/`)
- [ ] Exceptions custom découplées de FastAPI (`core/exceptions.py`)
- [ ] Handlers globaux d'exceptions dans l'app
- [ ] Documentation Swagger automatique
- [ ] Config pydantic-settings (`core/config.py`)
- [ ] Logging structuré JSON (`core/logging.py`)

## 3. Tests automatisés

- [ ] Tests unitaires preprocessing (par table)
- [ ] Tests unitaires prédiction
- [ ] Tests validation input (Pydantic schemas)
- [ ] Cas critiques :
  - [ ] données manquantes
  - [ ] types invalides
  - [ ] valeurs aberrantes
  - [ ] tables vides
- [ ] Tests d'intégration API (`TestClient` FastAPI + httpx)
- [ ] Coverage ≥ 90%

## 4. Logging structuré

- [ ] Middleware FastAPI : logger chaque requête (timestamp, input hash, score, latence, erreurs)
- [ ] Format JSON structuré
- [ ] Sortie stdout (capté par Fluentd via Docker logging driver)
- [ ] Données de démo pour tester le pipeline de logs

## 5. Conteneurisation (Docker)

- [ ] `docker/api/Dockerfile` (FastAPI + uvicorn)
- [ ] `docker/streamlit/Dockerfile`
- [ ] `docker/fluentd/fluent.conf`
- [ ] `docker/prometheus/prometheus.yml`
- [ ] `docker/grafana/datasources/` + `dashboards/`
- [ ] `docker-compose.yml` (6 services : api, elasticsearch, fluentd, prometheus, grafana, streamlit)
- [ ] Tester le stack complet en local
- [ ] Tester l'API conteneurisée

## 6. Monitoring API (Prometheus + Grafana)

- [ ] `monitoring/metrics.py` — Histogram latence, Counter erreurs, Counter prédictions
- [ ] Configurer Prometheus pour scraper `/metrics`
- [ ] Datasources Grafana : Prometheus + Elasticsearch
- [ ] Dashboard Grafana : latence, taux erreur, volume requêtes, distribution scores
- [ ] Captures d'écran pour la documentation

## 7. Drift & Dashboard Streamlit

- [ ] `monitoring/drift.py` — détection data drift avec Evidently AI
- [ ] `dashboard/app.py` — Streamlit
- [ ] Afficher :
  - [ ] distribution des scores
  - [ ] drift report Evidently
  - [ ] latence API (depuis ES)
  - [ ] volume de requêtes (depuis ES)
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
- [ ] Captures d'écran (API, Grafana, Streamlit, drift)
- [ ] Archiver les dernières décisions dans DECISIONS.md
