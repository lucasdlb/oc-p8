# Stack

## Stack validée

| Composant | Techno | Justification |
|---|---|---|
| API | FastAPI + Pydantic | Standard Python API, async, Swagger auto, validation intégrée |
| Modèle | LightGBM (pickle P6) | Modèle existant du projet précédent, bundlé dans le repo |
| Validation | Pydantic | Natif dans FastAPI, typage fort, 7 schémas de tables |
| Logs structurés | JSON → Fluentd → Elasticsearch | Stack pro de collecte/stockage, datasource Grafana native |
| Métriques | prometheus_client → Prometheus | Standard monitoring API, scraping /metrics |
| Dashboards métriques | Grafana | Standard industrie, datasources Prometheus + ES |
| Dashboard ML/drift | Streamlit + Evidently AI | Python-native, adapté au drift ML, complémentaire de Grafana |
| Tests | pytest + httpx | Écosystème standard, coverage 90%, TestClient FastAPI |
| Conteneurisation | Docker Compose | 6 services orchestrés, reproductible |
| CI/CD | GitHub Actions → Hugging Face Spaces | Gratuit, intégré GitHub, déployement automatique |
| Config | pydantic-settings | Env vars typées, validation au boot, .env local |
| Type checker | ty | Rapide, moderne, py312+ |
| Linter/formatter | ruff | Remplace flake8 + isort + black, un seul outil |
