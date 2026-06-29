---
title: Credit Scores API
emoji: 🏦
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
---

# OC P8 — Déployez et monitorez votre modèle de scoring

Déploiement et monitoring d'un modèle de scoring crédit (LightGBM) en production.

API FastAPI, logs structurés JSON → Promtail → Loki, métriques Prometheus, dashboards Grafana, drift detection Evidently UI.

## Documentation

| Document | Contenu |
|---|---|
| [CONTEXT.md](docs/CONTEXT.md) | Mission, modèle source, objectif portfolio |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Flux de données, stack, structure repo, conventions |
| [DECISIONS.md](docs/DECISIONS.md) | Registre des choix délibérés et justifications |
| [ROADMAP.md](docs/ROADMAP.md) | Phases d'implémentation |
| [STACK.md](docs/STACK.md) | Stack technique validée |

## Lancement rapide

```bash
# API en local
 uv run uvicorn src.credit_risk_server.api.main:app --reload

# Stack complète
docker compose up
```

## Stack

FastAPI · LightGBM · Loki · Promtail · Prometheus · Grafana · Evidently AI · Docker · GitHub Actions

## URLs des services

### API FastAPI

| URL | Méthode | Description |
|---|---|---|
| [http://localhost:8000/health](http://localhost:8000/health) | GET | Health check |
| [http://localhost:8000/predict](http://localhost:8000/predict) | POST | Scoring depuis DataSource |
| [http://localhost:8000/predict/rows](http://localhost:8000/predict/rows) | POST | Scoring depuis données inline |
| [http://localhost:9100](http://localhost:9100) | GET | Prometheus metrics |

### Stack Docker Compose

| Service | URL | Port |
|---|---|---|
| API | [http://localhost:8000](http://localhost:8000) | 8000 |
| Metrics | [http://localhost:9100](http://localhost:9100) | 9100 |
| Prometheus | [http://localhost:9090](http://localhost:9090) | 9090 |
| Loki | [http://localhost:3100](http://localhost:3100) | 3100 |
| Grafana | [http://localhost:3000](http://localhost:3000) | 3000 |
| Evidently UI | [http://localhost:8501](http://localhost:8501) | 8501 |

### Cibles Prometheus (`docker/prometheus/prometheus.yml`)

| URL | Job |
|---|---|
| [http://api:9100](http://api:9100) | credit-risk-api |
| [http://localhost:9090](http://localhost:9090) | prometheus |
| [http://node-exporter:9100](http://node-exporter:9100) | node-exporter |
| [http://cadvisor:8080](http://cadvisor:8080) | cadvisor |

### Datasources Grafana (`docker/grafana/datasources/datasources.yml`)

| URL | Source |
|---|---|
| [http://prometheus:9090](http://prometheus:9090) | Prometheus |
| [http://loki:3100](http://loki:3100) | Loki |

### Promtail (`docker/promtail/config.yml`)

| URL | Description |
|---|---|
| [http://loki:3100/loki/api/v1/push](http://loki:3100/loki/api/v1/push) | Endpoint push logs Loki |

### CI / CD

| URL | Description |
|---|---|
| [https://github.com/lucasdlb/oc-p6/releases/download/model-inference-v0.1.0/inference_pipeline_full.pkl](https://github.com/lucasdlb/oc-p6/releases/download/model-inference-v0.1.0/inference_pipeline_full.pkl) | Téléchargement modèle (CI) |
| [https://github.com/lucasdlb/oc-p6/releases/download/model-inference-v0.1.0/inference_pipeline_light.pkl](https://github.com/lucasdlb/oc-p6/releases/download/model-inference-v0.1.0/inference_pipeline_light.pkl) | Téléchargement modèle léger (CI) |
| [https://github.com/lucasdlb/oc-p6.git](https://github.com/lucasdlb/oc-p6.git) | Packages internes (credit-risk-data, credit-risk-models, credit-risk-processing) |
| [https://huggingface.co/spaces/Lucas-dlb/credit-scores-api](https://huggingface.co/spaces/Lucas-dlb/credit-scores-api) | Déploiement Hugging Face Spaces |

### Container Images

| Image | URL |
|---|---|
| uv base | [ghcr.io/astral-sh/uv:python3.12-trixie-slim](https://ghcr.io/astral-sh/uv:python3.12-trixie-slim) |
| Prometheus | [prom/prometheus:v2.54.1](https://hub.docker.com/layers/prom/prometheus/v2.54.1) |
| Loki | [grafana/loki:2.9.4](https://hub.docker.com/layers/grafana/loki/2.9.4) |
| Promtail | [grafana/promtail:2.9.4](https://hub.docker.com/layers/grafana/promtail/2.9.4) |
| Grafana | [grafana/grafana:latest](https://hub.docker.com/layers/grafana/grafana/latest) |
| Node Exporter | [prom/node-exporter:latest](https://hub.docker.com/layers/prom/node-exporter/latest) |
| cAdvisor | [gcr.io/cadvisor/cadvisor:latest](https://gcr.io/cadvisor/cadvisor:latest) |
| pre-commit hooks | [https://github.com/pre-commit/pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) |

![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)
![Coverage](https://codecov.io/gh/lucasdlb/oc-p8/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
