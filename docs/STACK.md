# Stack

## Stack validée

| Composant | Techno | Justification |
|---|---|---|
| API | FastAPI + Pydantic | Standard Python API, async, Swagger auto, validation intégrée |
| Modèle | LightGBM (pickle P6) | Modèle existant du projet précédent, bundlé dans le repo |
| Validation | Pydantic | Natif dans FastAPI, typage fort, 7 schémas de tables |
| Logs structurés | JSON stdout → Promtail → Loki | Stack Grafana unifiée (LogQL ≈ PromQL), faible empreinte RAM, datasource Grafana native (D-01, D-04) |
| Métriques | prometheus_client → Prometheus (port 9100) | Standard monitoring API, scraping isolé du trafic API (D-18) |
| Dashboards infra/HTTP | Grafana | Standard industrie, datasources Prometheus + Loki, HTTP/latence/erreurs/hardware |
| Drift ML/statistique | Evidently UI (`evidently-ui` :8501) | Profondeur statistique purpose-built (PSI, 20+ stattests, snapshots), workspace partagé (D-02b) |
| Tests | pytest + httpx | Écosystème standard, coverage ≥85%, TestClient FastAPI |
| Conteneurisation | Docker Compose | 8 services orchestrés (6 principaux + node-exporter + cadvisor), reproductible |
| Config | pydantic-settings | Env vars typées, validation au boot, `.env` local |
| Type checker | ty | Rapide, moderne, py312+ |
| Linter/formatter | ruff | Remplace flake8 + isort + black, un seul outil |
| CI/CD | GitHub Actions → Hugging Face Spaces | Gratuit, intégré GitHub, déploiement automatique (planned) |
