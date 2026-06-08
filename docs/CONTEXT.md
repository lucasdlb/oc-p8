# Contexte projet

## Mission

**OC P8 — Déployez et monitorez votre modèle de scoring**

Déployer le modèle de scoring crédit du projet P7 (P6 dans le parcours) en production, le monitorer, et détecter le data drift. Le projet couvre : API de scoring, tests, logging, monitoring, drift detection, dashboard, conteneurisation, CI/CD.

## Modèle source (P6)

Le modèle provient du projet `~/oc/oc-p6` et est bundlé dans ce repo.

- **Type** : `LGBMClassifier` (LightGBM)
- **Pipeline** : `InferencePipeline` custom (pickle) — pas un sklearn Pipeline standard
- **Entrée** : 7 tables brutes en Polars DataFrames (`application`, `bureau`, `bureau_balance`, `previous_application`, `pos_cash_balance`, `installments`, `credit_card_balance`)
- **Sortie** : `(SK_ID_CURR, probabilité classe positive)`
- **Features** : 305 features sélectionnées (voir `models/features_prod.json`)
- **Preprocessing** : 7 pipelines sklearn par table (cleaner → imputer → aggregator → transformer → encoder → schema), puis CrossTableTransformer, puis NaNReplacer + estimator
- **Fichiers** : `inference_pipeline_debug.pkl` (~5 Mo), `features_prod.json`, `final_model_prod.pkl` (~2 Mo)

## Objectif portfolio

- Repo public GitHub, rendu professionnel
- Historique git lisible (commits explicites, branching clair)
- Démonstrable : API fonctionnelle, dashboards, monitoring en action
- Documenté : README, architecture, captures d'écran

## Audience

- Évaluateur OC (validation des compétences déploiement/monitoring)
- Recruteurs (démonstration de rigueur technique et de vision production)
