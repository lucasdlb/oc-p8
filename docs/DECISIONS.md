# Décisions

Registre incrémental des choix nécessitant une délibération.
Chaque entrée est ajoutée après co-réflexion entre l'utilisateur et l'agent.

---

## D-01 — Stockage des logs

- **Options** : SQLite / PostgreSQL / Elasticsearch
- **Choix** : Elasticsearch
- **Justif** : Compatible Fluentd natif, datasource Grafana native, aligné objectif portfolio pro. Plus lourd que SQLite mais la stack Docker l'absorbe.
- **Conséquences** : Requiert vm.max_map_count=262144, mapping explicite à l'init.
- **Révision si** : Contrainte RAM en prod → migration vers PostgreSQL.
-
## D-02 — Dashboards monitoring

- **Options** : Streamlit seul / Grafana seul / Streamlit + Grafana
- **Choix** : Streamlit + Grafana
- **Justif** : Grafana = standard industrie pour métriques API (latence, erreurs, volume). Streamlit = adapté pour drift ML Evidently (Python-native). Chaque outil dans son rôle.

## D-03 — Format entrée API /predict

- **Options** : Features pré-processées (305) / 7 tables brutes (pipeline complet) / les deux endpoints
- **Choix** : 7 tables brutes (pipeline complet)
- **Justif** : Fidèle au P6, démontre le preprocessing end-to-end. Plus lourd en input mais réaliste pour un cas crédit avec données multi-sources.

## D-04 — Ingestion logs vers Elasticsearch

- **Options** : elasticsearch-py direct / Fluentd / Logstash
- **Choix** : Fluentd
- **Justif** : Standard de collecte de logs en conteneur (Docker logging driver), découple l'API du stockage, plus "production-like" que l'écriture directe.

## D-05 — Kibana

- **Options** : Oui / Non
- **Choix** : Non
- **Justif** : Grafana couvre le besoin d'exploration (datasource ES). Évite un 7e conteneur et la redondance.

## D-06 — Stratégie de branching

- **Options** : main + feature branches + PR / GitHub Flow simplifié / Trunk-based
- **Choix** : GitHub Flow simplifié
- **Justif** : Projet solo, PR formelle sur-dimensionnée. Branches courtes + pre-push hook suffisent pour un historique propre.

## D-07 — Exceptions métier

- **Options** : HTTPException directe dans le business logic / exceptions custom découplées
- **Choix** : Custom découplées
- **Justif** : `predictor.py` ne doit pas dépendre de FastAPI. Les exceptions custom sont catchées par des handlers globaux dans l'app. Séparation des couches.

## D-08 — Dependency groups pyproject.toml

- **Options** :Tout dans dependencies / groups séparés (api / dashboard / dev)
- **Choix** : Groups séparés
- **Justif** : FastAPI et Streamlit ont des cycles de vie et des deps différents. Dockerfiles séparés installent seulement le groupe nécessaire.

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
