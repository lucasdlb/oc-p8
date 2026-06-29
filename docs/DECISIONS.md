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

## D-02b — Drift monitoring : Evidently UI (révise D-02)

- **Options** : Drift dans Grafana via Prometheus / Evidently UI dédiée (6e conteneur)
- **Choix** : Grafana pour l'infra/HTTP + Evidently UI pour le drift ML/statistique
- **Justif** : Evidently offre une profondeur statistique purpose-built (20+ stattests,
  panels ML natifs, snapshots comparables dans le temps) qu'une reproduction Prometheus
  ne pourrait qu'approximer. La séparation des concerns est nette :
  Grafana = HTTP, latence, erreurs, hardware ; Evidently UI = PSI par feature,
  distribution des scores, drifted-columns count. Grafana reste le point d'entrée
  unique pour l'infra ; Evidently UI est le point d'entrée dédié pour l'observabilité ML.
- **Conséquences** : 6 services Docker (ajout de `evidently-ui` sur :8501).
  `drift.py` ne touche plus Prometheus — il produit des Evidently Snapshots écrits
  dans un Workspace partagé (bind mount `./workspace`). `metrics.py` garde ses
  métriques HTTP/business intactes.
- **Révision si** : Besoin de corréler drift et infra dans un même dashboard →
  réintégrer les drifted-count dans Prometheus via un bridge custom.

## D-22 — Métrique de drift : PSI

- **Options** : PSI / KS test / Wasserstein / Chi-2 / auto (Evidently)
- **Choix** : PSI (Population Stability Index), seuil configurable (défaut 0.25)
- **Justif** : PSI est interprétable ( < 0.1 stable, 0.1–0.25 modéré, > 0.25 drift),
  applicable aux colonnes numériques ET catégorielles, et standard dans le crédit.
  Le seuil 0.25 signale un drift significatif nécessitant une investigation.
- **Conséquences** : `ValueDrift(method="psi", threshold=0.25)` pour le score et
  chaque feature monitorée. `DriftedColumnsCount(drift_share=0.3)` déclare un
  dataset drifté si ≥ 30% des colonnes dérivent.

## D-23 — Buffer et compute périodique

- **Options** : Compute synchrone à chaque requête / compute périodique asynchrone
- **Choix** : `collections.deque(maxlen=5000)` + `asyncio` task périodique (60s)
- **Justif** : Le drift est un signal agrégé, pas par-requête. Un ring buffer
  fixe la fenêtre glissante sans croissance mémoire. Le compute périodique via
  `asyncio.to_thread()` ne bloque pas l'event loop FastAPI.
- **Conséquences** : `DriftMonitor.record()` ajoute au deque (O(1)).
  `start_periodic_compute()` lance une task qui appelle `compute()` toutes les
  60s. `compute()` skip si < `min_samples` (défaut 50) dans le buffer.

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

## D-24 — Déploiement API-only sur Hugging Face Spaces

- **Options** : Stack complète sur VPS / API seule sur HF Spaces + monitoring local / Demo 100% locale
- **Choix** : API seule sur HF Spaces (`Lucas-dlb/credit-scores-api`) + monitoring local via `docker-compose`
- **Justif** : HF Spaces ne supporte qu'un seul conteneur — impossible d'y exécuter la stack de 8 services
  (Prometheus, Loki, Promtail, Grafana, Evidently UI, node-exporter, cadvisor). Le monitoring nécessite
  le scrape du port 9100 et l'accès aux logs Docker host, tous deux inaccessibles depuis HF Spaces.
  Déployer uniquement l'API donne une URL publique démontrable pour le portfolio, tandis que le
  monitoring reste démontrable en local via `docker-compose` (captures d'écran).
  Port 9100 reste interne sur HF (non exposé) ; `/predict/rows` fonctionne sans DataSource.
- **Conséquences** : Dockerfile unifié à la racine du repo (même comportement local et HF).
  Le modèle `inference_pipeline.pkl` est téléchargé au build depuis un GitHub Release
  d'oc-p6 (`model-inference-v0.1.0`) avec fallback de tier (prod → dev → debug) — pas bundlé dans le repo. HF Space variables
  (`DATA_SOURCE=""`, `DRIFT_ENABLED=false`) configurées dans l'UI HF. CI (lint + type + tests +
  build Docker) déclenche CD (`workflow_run` sur CI succès) qui pousse le repo vers le HF remote.
- **Révision si** : Besoin de monitoring en production réel → migrer vers un VPS avec la stack complète.

## D-25 — Méthodologie de benchmark

- **Options** : Grafana seul / script in-process + Grafana / HTTP load test seul
- **Choix** : Script in-process reproductible (pyinstrument + perf_counter + getrusage) + Grafana pour la vue HTTP live
- **Justif** : Grafana donne des agrégats fenêtrés, pas un rapport statistique reproductible diffable.
  Le script in-process élimine le jitter réseau, permet le profiling pyinstrument, et produit un JSON
  stable pour le diff avant/après. La vue HTTP (latence end-to-end, mémoire conteneur) reste capturée
  par Grafana (screenshots portfolio). pyinstrument (profilage statistique, faible overhead) répond à
  "preprocessing vs LightGBM" mieux que cProfile (instrumentation déterministe bruitée sur Polars/LGBM).
  Mémoire processus via `resource.getrusage` (stdlib, pas de psutil).
- **Conséquences** : `monitoring/benchmark.py` (primitives partagées) + `scripts/bench_predict.py` +
  `scripts/bench_predict_rows.py` + `docs/benchmark.md` + `docs/benchmark/*.json/html/txt`.
  Le benchmark mesure les code paths des routes sans la surcouche HTTP/uvicorn (~1-5ms, constant).
  Deux scripts séparés car `/predict` (I/O-bound, 7 CSVs) et `/predict/rows` (compute-bound, JSON)
  ont des profils de performance fondamentalement différents.
- **Révision si** : Besoin de mesurer l'overhead HTTP lui-même → ajouter un flag `--http` au script.

## D-26 — Optimisation post-déploiement : ONNX Runtime

- **Options** : Native LightGBM / ONNX Runtime (LightGBM exporté) / ONNX full pipeline (preprocessing + modèle)
- **Choix** : **ONNX Runtime partiel** — seule l'inférence LightGBM est exportée vers ONNX
- **Justif** :
  - Le preprocessing (7 pipelines sklearn Polars-native) n'est pas convertible en ONNX (steps custom)
  - L'inférence ONNX seule est **+47% plus rapide** que native (0.64ms vs 1.21ms, batch=50)
  - La différence de précision est négligeable (5.3e-07, float32 vs float64)
  - ONNX Runtime allège l'image Docker (~30-40 Mo sans lightgbm/scikit-learn)
  - Le pipeline complet reste dominé par le preprocessing (78ms) — l'impact end-to-end est <1%
  - Le full pipeline ONNX (conversion preprocessing complet via skl2onnx) n'est pas réalisable : les steps Polars custom n'ont pas de converter implémenté
- **Conséquences** : `onnxruntime` ajouté aux dépendances dev. Le ONNX model est exporté one-shot via `onnxmltools` et mis en cache (`/tmp/lgbm_export.onnx`). `scripts/bench_onnx.py` sert de benchmark de comparaison et de preuve de concept pour une migration future.
- **Révision si** : Besoin de supprimer la dépendance `lightgbm` de l'image Docker → produire le ONNX model dans le CI et le bundler dans l'artefact de déploiement.

## D-27 — Optimisation post-déploiement : preprocessing (schema caching + lazy fix)

- **Options** : Ne rien faire (ONNX suffit) / Vendoriser credit-risk-models/processing pour patcher / **Wrapper monkey-patch pour benchmark uniquement** / Réécrire le preprocessing en Polars pur
- **Choix** : **Wrapper monkey-patch** — un module `scripts/optimize_pipeline.py` deep-copie le pipeline et patche `InferencePipeline.predict()` et `BureauBalanceAggregator.transform()`.
- **Justif** :
  - Le preprocessing est dominé par deux causes identifiées (pyinstrument §7) : des appels répétés à `merged.columns` dans `predict()` (7% du temps) et un round-trip lazy→collect→eager inutile dans `BureauBalanceAggregator` (22% collect + 5% lazy).
  - Le cache schema (`set(merged.columns)` au lieu de `f in merged.columns`) donne **+11.5%** à lui seul.
  - Le fix bureau_balance (garder le plan lazy jusqu'au collect final) ajoute **+3.4%**.
  - Total : **+9% pipeline** (82.9ms → 75.4ms, 8 batch sizes, 20 runs).
  - Les packages `credit-risk-models` et `credit-risk-processing` viennent du repo P6 (git tags). Les vendoriser pour un patch permanent alourdirait la maintenance. Le wrapper est suffisant pour benchmarker l'impact et documenter le potentiel.
  - L'API n'est pas modifiée — le wrapper est réservé aux scripts de benchmark/exploration.
- **Conséquences** : `scripts/optimize_pipeline.py` créé. Résultats dans `docs/benchmark.md §10` et `docs/benchmark/preprocessing_opt.json`. La priorité de l'optimisation preprocessing passe de **Haute** à **Faible** dans le tableau de conclusion — le gain est modeste et l'API reste sur l'implémentation d'origine.
- **Révision si** : Le preprocessing est vendorisé ou réécrit → appliquer les patches directement dans le code source.
