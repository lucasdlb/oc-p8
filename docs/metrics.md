# Prometheus metrics

Variables exposées par l'API sur `http://localhost:9100/metrics`.

Source : `src/credit_risk_server/monitoring/metrics.py` + métriques automatiques de `prometheus_client`.

## Métriques applicatives

| Metric | Type | Description |
|---|---|---|
| `credit_risk_model_loaded` | gauge | Modèle chargé (1 = oui, 0 = non) |
| `credit_risk_prediction_duration_seconds` | histogram | Latence de scoring en secondes |
| `credit_risk_predictions_total` | counter | Nombre total de prédictions réussies |
| `fastapi_active_requests` | gauge | Requêtes HTTP en cours |
| `fastapi_request_latency_seconds` | histogram | Latence HTTP en secondes |
| `fastapi_request_latency_seconds_created` | gauge | Timestamp de création (généré automatiquement) |
| `fastapi_requests_total` | counter | Nombre total de requêtes HTTP |
| `fastapi_requests_created` | gauge | Timestamp de création (généré automatiquement) |

## Métriques processus

| Metric | Type | Description |
|---|---|---|
| `process_cpu_seconds_total` | counter | Temps CPU total (user + system) en secondes |
| `process_max_fds` | gauge | Nombre max de descripteurs de fichiers |
| `process_open_fds` | gauge | Descripteurs de fichiers ouverts |
| `process_resident_memory_bytes` | gauge | Mémoire résidente en octets |
| `process_start_time_seconds` | gauge | Heure de démarrage du processus (epoch) |
| `process_virtual_memory_bytes` | gauge | Mémoire virtuelle en octets |

## Métriques runtime Python

| Metric | Type | Description |
|---|---|---|
| `python_gc_collections_total` | counter | Nombre de collections GC par génération |
| `python_gc_objects_collected_total` | counter | Objets collectés lors du GC |
| `python_gc_objects_uncollectable_total` | counter | Objets non collectables |
| `python_info` | gauge | Informations plateforme Python |
