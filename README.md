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

![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)
![Coverage](https://codecov.io/gh/lucasdlb/oc-p8/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
