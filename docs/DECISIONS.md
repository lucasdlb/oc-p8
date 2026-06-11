# Décisions

Registre incrémental des choix nécessitant une délibération.
Chaque entrée est ajoutée après co-réflexion entre l'utilisateur et l'agent.

---

## D-01 — Stockage des logs

- **Options** : SQLite / PostgreSQL / Elasticsearch / Loki
- **Choix** : Loki
- **Justif** : Même écosystème que Prometheus (LogQL ≈ PromQL), consommation RAM minimale (~100-200 Mo vs 2-4 Go pour ES), pas de tuning système (pas de `vm.max_map_count`), datasource Grafana native. Aligné avec le choix d'une stack Grafana unifiée (D-02).
- **Conséquences** : Les requêtes utilisent LogQL au lieu d'ES DSL. Streamlit interrogera Loki via l'API HTTP (`/loki/api/v1/query_range`).
- **Révision si** : Besoin de recherche full-text avancé → migration vers Elasticsearch.

## D-02 — Dashboards monitoring

- **Options** : Streamlit seul / Grafana seul / Streamlit + Grafana
- **Choix** : Grafana seul
- **Justif** : Grafana couvre métriques API (Prometheus) ET exploration de logs (Loki). Le drift Evidently sera exposé comme métriques Prometheus visibles dans Grafana, pas dans un dashboard Streamlit séparé. Supprime un conteneur (5 services au lieu de 6) et un dependency group.

## D-03 — Format entrée API /predict

- **Options** : Features pré-processées (305) / 7 tables brutes (pipeline complet) / les deux endpoints
- **Choix** : 7 tables brutes via DataSource + endpoint row-oriented
- **Justif** : Le endpoint `/predict` charge les données via DataSource (CSV, SQL…), le endpoint `/predict/rows` accepte du JSON inline. Les deux passent par l'InferencePipeline, fidèle au P6. L'approche DataSource permet un filtrage par `sk_ids` coté serveur.

## D-04 — Ingestion logs

- **Options** : elasticsearch-py direct / Fluentd / Promtail / Logstash
- **Choix** : Promtail
- **Justif** : Natif Loki, binaire Go léger, scrap les fichiers logs Docker. Remplace le driver Fluentd par une config simple. Pas de dépendance Ruby ni de plugin Docker logging driver.
- **Conséquences** : Docker logging driver = `json-file` (standard). Promtail scrap `/var/lib/docker/containers`.

## D-05 — Kibana

- **Options** : Oui / Non
- **Choix** : Non
- **Justif** : Grafana couvre le besoin d'exploration de logs (datasource Loki). Évite un conteneur supplémentaire et la redondance.

## D-06 — Stratégie de branching

- **Options** : main + feature branches + PR / GitHub Flow simplifié / Trunk-based
- **Choix** : GitHub Flow simplifié
- **Justif** : Projet solo, PR formelle sur-dimensionnée. Branches courtes + pre-push hook suffisent pour un historique propre.

## D-07 — Exceptions métier

- **Options** : HTTPException directe dans le business logic / exceptions custom découplées
- **Choix** : Custom découplées
- **Justif** : `predictor.py` ne doit pas dépendre de FastAPI. Les exceptions custom sont catchées par des handlers globaux dans l'app. Séparation des couches.

## D-08 — Dependency groups pyproject.toml

- **Options** : Tout dans dependencies / groups séparés (api / dashboard / dev)
- **Choix** : Groups séparés (api / dev)
- **Justif** : Seul l'API service tourne en Docker. Le groupe `dashboard` (Streamlit/Evidently) est supprimé (D-02). Chaque Dockerfile installe seulement le groupe nécessaire.

## D-09 — Dépendance preprocessing oc-p6

- **Options** : Copier le code / dépendre du repo entier / sous-package extrait
- **Choix** : Sous-package extrait, versionné par tag git
- **Justif** : Zéro duplication, surface d'import minimale, reproductibilité
  garantie par uv.lock qui pine le commit exact.
- **Conséquences** : Tag obligatoire avant tout bump en oc-p8. CI oc-p8
  nécessite accès GitHub au repo oc-p6.
- **Révision si** : Publication sur PyPI privé si le projet passe en équipe.

## D-10 — Config dependency dans le sous-package preprocessing

- **Options** : Injection des paramètres / extraire config / garder TOML
- **Choix** : Injection — data_path + csv_name_map comme arguments constructeur
- **Justif** : Inversion de dépendance. Le package ne connaît pas son contexte
  d'exécution. Le caller (oc-p8) injecte depuis son propre settings.
- **Conséquences** : Breaking change sur l'interface DataLoader dans oc-p6.
  Nouveau tag requis.
- **Révision si** : Jamais — c'est la bonne architecture.

## D-11 — Format de sérialisation du modèle

- **Options** : joblib / ONNX / pickle
- **Choix** : joblib en MVP, migration ONNX en étape 9
- **Justif** : joblib = débogage facile en dev. ONNX = standard déploiement,
  gain latence et image Docker allégée. Benchmark avant/après dans étape 9.

## D-12 — Config pattern : Settings par service, fichier .env unique

- **Options** : Settings plat unique / Settings par service avec préfixes / Settings par service avec `.env.<service>` séparés
- **Choix** : Settings par service avec `.env.<service>` séparés + `.env` partagé
- **Justif** : Chaque service Docker a ses propres variables. `AppSettings` fournit les
  champs communs (`log_level`, `env`, `log_path`). `ApiSettings(AppSettings)` lit `.env.api`,
  `DashboardSettings(AppSettings)` lira `.env.dashboard`, etc. Les variables partagées
  (`LOG_LEVEL`, `ENV`, `LOG_PATH`) restent dans `.env`.
- **Conséquences** : `.env.example` unique avec sections partagées + par service.
  `.gitignore` : `.env` et `.env.*` ignorés, `!.env.example` autorisé.
- **Révision si** : Si les services partagent trop de vars → fusionner en Settings plat.

## D-13 — Data source optionnelle (DATA_SOURCE)

- **Options** : Toujours créer le DataSource / rendre DATA_SOURCE optionnel
- **Choix** : `DATA_SOURCE` optionnel via `Literal["csv", "sql"] | None`
- **Justif** : L'endpoint `/predict/rows` n'a pas besoin de DataSource. Si `DATA_SOURCE`
  est absent, l'API démarre quand même et `/predict` retourne 503. Permet de déployer
  l'API sans fichiers CSV (utile en test, CI, ou pour ne servir que `/predict/rows`).
- **Conséquences** : `make_source()` retourne `DataSource | None`. `get_data_source()`
  retourne `DataSource | None`. Le route `/predict` lève HTTPException 503 si None.

## D-14 — Assembler : un seul chemin (DataFrames)

- **Options** : Garder `assemble()` (Pydantic) + `assemble_tables()` (DataFrames) / unifier
- **Choix** : Unifier en un seul `assemble(source, sk_ids) -> dict[str, pl.DataFrame]`
- **Justif** : Le chemin Pydantic (`assemble()`) convertissait Polars → list[dict] → validation
  Pydantic → retour DataFrames, un round-trip inutile. Le chemin DataFrames est plus direct
  et utilisé par le seul endpoint qui charge depuis la source. L'endpoint `/predict/rows`
  construit déjà ses DataFrames depuis le JSON, sans passer par l'assembler.
- **Conséquences** : `DictDataSource` supprimé (jamais appelé au runtime). Un seul point
  d'entrée dans le module data.

## D-15 — Endpoints synchrones

- **Options** : `async def` partout / `def` sync pour les endpoints CPU-bound
- **Choix** : `def` sync (endpoint handlers)
- **Justif** : Toute la chaîne est CPU-bound (Polars, LightGBM, Pydantic). Un `async def`
  sans `await` bloque l'event loop. FastAPI dispatche les endpoints sync dans un threadpool
  via `run_in_threadpool`, évitant de starvationner l'event loop.

## D-16 — Literal types pour la config

- **Options** : Tous les champs en `str` / `Literal` pour les enums fermées
- **Choix** : `Literal` pour `env` et `data_source`, `str` pour le reste
- **Justif** : `env` a exactement 2 valeurs (`"dev"`, `"prod"`) qui déterminent le formatteur
  de logs. `data_source` a 2 valeurs connues (`"csv"`, `"sql"`) pilotées par match/case.
  Les autres champs (`log_level`, `api_host`, etc.) sont libres. Valider tôt > runtime error.

## D-17 — DevFormatter : affichage des extras

- **Options** : JSON compact / `key=value` space-separated / tabulaire aligné
- **Choix** : `key=value` space-separated
- **Justif** : Format lisible, grep-friendly, logfmt-compatible. En production, le
  JSONFormatter sérialise déjà en JSON structuré. Le DevFormatter ne sert qu'en local.
- **Conséquences** : Sortie type : `2024-01-15 10:30:00 | ... | data source created | source_type=csv data_path=data/`

## D-18 — Exposition /metrics

- **Options** : Port séparé 9100 (`start_http_server`) / ASGI mount sur port 8000 (`make_asgi_app`) / Route FastAPI `/metrics`
- **Choix** : Port séparé 9100 (`start_http_server`)
- **Justif** : Isolation du trafic metrics du trafic API. Config Prometheus standard (scrape sur port dédié). Pas de pollution des logs API par les scrapes. Le port 9100 est déjà configuré dans Docker et Prometheus.
- **Conséquences** : La route `/metrics` sur le port 8000 est supprimée. Docker expose 2 ports (8000 + 9100).
