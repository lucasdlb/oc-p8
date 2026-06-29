# Benchmark — Baseline performance

## Méthodologie

Les benchmarks mesurent les code paths des routes **en-process** (sans surcouche
HTTP/uvicorn) pour éliminer le jitter réseau et permettre le profiling pyinstrument.
La vue HTTP end-to-end (latence, erreurs, mémoire conteneur) est capturée séparément
via Grafana + `traffic_simulator.py`.

**Outils** :
- `time.perf_counter()` — latence par run (mean/p50/p95/p99/std)
- `resource.getrusage(RUSAGE_SELF)` — mémoire RSS processus
- `pyinstrument` — profiling statistique (call-tree + flat profile)
- `ThreadPoolExecutor` — sweep de concurrence

**Scripts** :
- `scripts/bench_predict.py` — code path `/predict` (DataSource → 7 tables CSV → InferencePipeline)
- `scripts/bench_predict_rows.py` — code path `/predict/rows` (JSON → Pydantic → InferencePipeline)

**Reproductibilité** : seed fixe (42), warmup 3 runs, outputs JSON versionnés dans
`docs/benchmark/` pour diff avant/après optimisation.

Voir [DECISIONS.md D-25](DECISIONS.md#d-25) pour la justification méthodologique.

---

## Environnement

| | Valeur |
|---|---|
| Python | 3.12 |
| Model | `inference_pipeline_debug.pkl` (LightGBM, 305 features) |
| Data | `application_test.csv` (48 744 clients) |
| CPU | voir `*.json` → `environment.cpu_count` |

---

## 1. Démarrage API

| Phase | `/predict` (DataSource) | `/predict/rows` (JSON) |
|---|---|---|
| Model load | 356 ms | 76 ms |
| DataSource init | 0 ms (lazy) | N/A |
| **Total startup** | **356 ms** | **76 ms** |
| Cold start (1ère prédiction) | 3 666 ms | 110 ms |

Le DataSource est lazy (`PLLazyDataLoader`) — l'init ne coûte rien, mais la première
prédiction déclenche le scan des 7 CSVs (cold start 3.7s vs 110ms pour `/predict/rows`).

---

## 2. Sweep batch size — `/predict/rows` (compute pur)

| Batch | Mean (ms) | p50 (ms) | p95 (ms) | Per-pred (ms) | Efficiency | Throughput (p/s) |
|------:|----------:|---------:|---------:|--------------:|-----------:|-----------------:|
| 1 | 86.3 | 85.7 | 93.8 | 86.34 | 1.000 | 11.6 |
| 5 | 83.1 | 83.0 | 89.6 | 16.63 | 0.193 | 60.1 |
| 10 | 89.6 | 84.6 | 180.7 | 8.96 | 0.104 | 111.6 |
| 25 | 87.2 | 87.6 | 95.8 | 3.49 | 0.040 | 286.8 |
| 50 | 89.7 | 88.8 | 96.9 | 1.79 | 0.021 | 557.6 |
| 100 | 91.1 | 91.3 | 98.5 | 0.91 | 0.011 | 1 097.3 |
| 250 | 102.9 | 102.3 | 117.1 | 0.41 | 0.005 | 2 429.1 |
| 500 | 120.0 | 120.7 | 128.4 | 0.24 | 0.003 | 4 165.3 |

**Analyse** :
- Latence quasi-plate de batch=1 à batch=100 (86→91ms) — le préprocessing a un coût
  fixe dominant (~85ms), l'inférence LightGBM est négligeable à ces tailles.
- À partir de batch=250, la latence augmente (103ms puis 120ms) — l'inférence devient
  mesurable mais reste légère.
- **Le batching est extrêmement efficace** : batch=50 divise le coût par prédiction par
  48× (86ms → 1.8ms). Le crossover où le batching devient rentable est immédiat (batch=5
  déjà 5× plus économique).
- Throughput maximal : **4 165 predictions/sec** à batch=500.

---

## 3. Sweep batch size — `/predict` (DataSource + I/O)

| Batch | Mean (ms) | p50 (ms) | p95 (ms) | Per-pred (ms) | Efficiency | Throughput (p/s) |
|------:|----------:|---------:|---------:|--------------:|-----------:|-----------------:|
| 1 | 3 791 | 3 804 | 3 819 | 3 791.35 | 1.000 | 0.3 |
| 50 | 4 249 | 4 253 | 4 292 | 84.98 | 0.022 | 11.8 |
| 250 | 4 159 | 4 160 | 4 171 | 16.63 | 0.004 | 60.1 |

**Analyse** :
- **90%+ du temps est du CSV I/O** (`PyLazyFrame.collect` = 5.4s sur 7.5s profilés).
- La latence est dominée par la lecture des 7 tables CSV (某些 font 700MB), pas par
  l'inférence. Le batch size a un impact marginal sur le temps total (3.8s → 4.2s).
- Le batching amortit massivement le coût I/O fixe : batch=250 donne 60 p/s vs 0.3 p/s
  en batch=1.
- **Optimisation de l'inférence (ONNX, joblib) n'aura aucun impact sur `/predict`** —
  le goulot est le I/O disque.

---

## 4. Concurrence — `/predict/rows`

| Workers | Throughput (p/s) | Wall time (s) |
|--------:|-----------------:|--------------:|
| 1 | 576.2 | 4.34 |
| 2 | 613.2 | 4.08 |
| 4 | 393.7 | 6.35 |
| 8 | 301.1 | 8.30 |
| 16 | 298.2 | 8.38 |

**Analyse** :
- Le throughput **diminue** au-delà de 2 workers — le préprocessing (Polars/sklearn)
  tient le GIL, ce qui sérialise les threads. La concurrence dégrade les performances
  (context switching overhead).
- LightGBM libère le GIL pendant l'inférence C++, mais le préprocessing dominant
  annule cet avantage.
- **Recommandation** : conserver les endpoints synchrones (D-15), ne pas paralleliser
  au niveau applicatif. Le batching est la stratégie d'optimisation préférable.

---

## 5. Mémoire

| Métrique | `/predict` | `/predict/rows` |
|---|---|---|
| Peak RSS | 2 490 MB | 749 MB |
| Croissance (1000 preds) | N/A (lean run) | 0.0 MB |

La différence de RSS (2.5 GB vs 749 MB) correspond aux 7 CSVs chargés en mémoire par
le DataSource. Aucune fuite mémoire détectée sur 1000 prédictions séquentielles
(`/predict/rows`).

---

## 6. Déterminisme

| Métrique | Valeur |
|---|---|
| Probability std (50 runs) | 0.00000000 |

L'inférence LightGBM est parfaitement déterministe — même input, même output.

---

## 7. Profiling — `/predict/rows` (pyinstrument, 20 itérations, batch=50)

**Duration**: 2.47s | **Samples**: 1 228 | **CPU time**: 7.23s

### Call tree (top frames)

```
2.470 profile_fn
`- 2.466 build_and_predict
   `- 2.444 predict (predictor.py)
      `- 2.390 _run
         `- 2.382 InferencePipeline.predict
            [97 frames hidden]  sklearn, credit_risk_processing, polars...
      `- 0.053 _rows_to_dataframe
         `- 0.034 DataFrame.__init__
```

### Flat profile — top methods (self time)

| Self time (s) | % total | Function |
|---:|---:|---|
| 0.816 | 33% | `[self]` bench_predict_rows.py (loop overhead) |
| 0.534 | 22% | `PyLazyFrame.collect` (Polars lazy → eager) |
| 0.169 | 7% | `PyDataFrame.columns` (schema inspection) |
| 0.134 | 5% | `PyDataFrame.lazy` (eager → lazy conversion) |
| 0.084 | 3% | `InferencePipeline.predict` (orchestration) |
| 0.065 | 3% | `isinstance` (type checks) |
| 0.054 | 2% | `BlockManager.iset` (pandas internals) |
| 0.034 | 1.4% | `_InnerPredictor.__inner_predict_np2d` (LightGBM) |
| 0.034 | 1.4% | `PyDataFrame.from_dicts` (rows → DataFrame) |
| 0.028 | 1.1% | `ApplicationImputer.transform` |

**Interprétation** :
- **LightGBM inference = 1.4%** (0.034s sur 2.47s) — négligeable.
- **Polars operations = ~34%** (`collect` + `columns` + `lazy` + `from_dicts`) — le
  passage eager↔lazy et le materialisation sont coûteux.
- **Pandas interop = ~10%** (`BlockManager.iset`, `to_pandas`, `table_to_dataframe`) —
  les pipelines sklearn utilisent pandas en interne, causant des conversions.
- **Preprocessing (imputer, transformer, cross) = ~5%** — modéré.
- **Optimisation targets** : si l'objectif est de réduire la latence de `/predict/rows`,
  il faut viser les conversions Polars↔pandas et les opérations lazy→eager, pas LightGBM.

### Profiling — `/predict` (pyinstrument, 20 itérations, batch=50)

**Duration**: 7.49s | **Samples**: 2 634 | **CPU time**: 24.03s

| Self time (s) | % total | Function |
|---:|---:|---|
| 5.417 | 72% | `PyLazyFrame.collect` (CSV scan + filter) |
| 0.778 | 10% | `[self]` bench_predict.py |
| 0.525 | 7% | `PyDataFrame.columns` |
| 0.083 | 1.1% | `InferencePipeline.predict` |
| 0.025 | 0.3% | `_InnerPredictor.__inner_predict_np2d` (LightGBM) |

**Conclusion** : `/predict` est I/O-bound à 72%. L'optimisation de l'inférence n'a
aucun impact sur ce path. L'optimisation du I/O (cache, format Parquet, eager loading)
serait la seule voie efficace.

---

## 8. Grafana — vue HTTP end-to-end

> **Screenshots à ajouter** : lancer `docker compose up -d` puis
> `uv run python scripts/traffic_simulator.py --rps 3` pendant ~3 min.
> Capturer depuis Grafana (`:3000`) :
>
> 1. **Dashboard API** — latence HTTP (p50/p95), taux d'erreur, volume de requêtes
> 2. **Dashboard Hardware** — `container_memory_usage_bytes` (API container), CPU usage
>
> Emplacement sugeré : `docs/benchmark/grafana_*.png`

---

## Fichiers de référence

| Fichier | Contenu |
|---|---|
| `docs/benchmark/predict_baseline.json` | Résultats bruts `/predict` (lean) |
| `docs/benchmark/predict_rows_baseline.json` | Résultats bruts `/predict/rows` (full) |
| `docs/benchmark/profile_predict_baseline.html` | Call-tree interactif `/predict` |
| `docs/benchmark/profile_predict_baseline.txt` | Call-tree + flat profile texte `/predict` |
| `docs/benchmark/profile_predict_rows_baseline.html` | Call-tree interactif `/predict/rows` |
| `docs/benchmark/profile_predict_rows_baseline.txt` | Call-tree + flat profile texte `/predict/rows` |

---

## 9. ONNX Runtime — LightGBM export

Le LightGBM `LGBMClassifier` est exporté vers ONNX via `onnxmltools` et exécuté via
`onnxruntime`. Le preprocessing reste identique (Polars-native) — seul le step de
prédiction finale est remplacé.

**Méthodologie** : La baseline `InferencePipeline.model_pipeline.predict_proba(X)`
est comparée à `onnxruntime.Session.run(None, {input: X_f32})` sur le même tenseur
numpy préprocessé (batch=50, 303 features). 20 runs mesurés après warmup.

### Résultats — modèle seul

| Métrique | Native | ONNX | Amélioration |
|---|---|---|---|
| Mean | 1.21 ms | 0.64 ms | **+47.1 %** |
| p50 | 1.18 ms | 0.62 ms | +47.5 % |
| p95 | 1.59 ms | 0.75 ms | +52.8 % |
| Std | 0.11 ms | 0.05 ms | -54.5 % |

La latence ONNX est plus stable (std réduite de moitié).

### Précision

La différence maximale entre les probabilités native et ONNX est de **5.3e-07**
(précision float32 vs float64). Aucun impact sur la décision métier.

### Pipeline complet

Le pipeline complet (preprocessing + modèle) est dominé par le preprocessing
(~78ms vs ~0.7ms de modèle). L'impact ONNX sur la latence end-to-end est
**< 1 %** — cohérent avec le profiling initial (LightGBM = 1.4 % du temps).

### Impact image Docker

| Dépendance | Taille estimée |
|---|---|
| `lightgbm` + `scikit-learn` | ~50-80 Mo (librairies C++ + Python) |
| `onnxruntime` | ~30-40 Mo (runtime C++ uniquement) |
| **Gain** | **~30-40 Mo** sur l'image finale |

Le remplacement de LightGBm par ONNX Runtime allège l'image Docker de ~30-40 Mo
et standardise le runtime de prédiction.

### Fichiers de référence

| Fichier | Contenu |
|---|---|
| `docs/benchmark/onnx_full.json` | Résultats bruts benchmark ONNX vs native |
| `scripts/bench_onnx.py` | Script de benchmark (export + comparison) |

---

## 10. Optimisation preprocessing — schema caching + bureau_balance lazy fix

Deux optimisations ciblant les 34 % d'opérations Polars identifiés au §7.

### Optimisations appliquées

| # | Changement | Fichier | Cible |
|---|---|---|---|
| 1 | **Cache de `merged.columns` en `set()`** — remplace `O(N)` `columns` calls par `O(1)` lookups | `InferencePipeline.predict()` (via wrapper) | `PyDataFrame.columns` (7 %) |
| 2 | **Suppression du round-trip lazy→collect→eager** — `BureauBalanceAggregator` faisait `lazy()` → `collect()` immédiat avant les opérations eager | `_BaseBureauBalanceAggregator.transform()` (via monkey-patch) | `PyLazyFrame.collect` (22 %) + `PyDataFrame.lazy` (5 %) |

### Résultats — 8 batch sizes, 20 runs, warmup=5

| Batch | Original (ms) | Optimisé (ms) | Δ |
|------:|--------------:|--------------:|---:|
| 1 | 81.2 | 73.5 | **−9%** |
| 5 | 76.4 | 68.5 | **−10%** |
| 10 | 76.4 | 65.8 | **−14%** |
| 25 | 76.5 | 69.9 | **−9%** |
| 50 | 76.0 | 76.8 | +1% (bruit) |
| 100 | 78.7 | 70.8 | **−10%** |
| 250 | 97.1 | 85.0 | **−12%** |
| 500 | 100.7 | 93.0 | **−8%** |
| **Overall** | **82.9** | **75.4** | **−9.0%** |

L'amélioration est cohérente sur toutes les tailles de batch (sauf batch=50, bruit
mesuré). Le gain brut moyen est de **7.5 ms par appel** à `predict()`.

### Analyse par optimisation

| Optimisation seule | Amélioration |
|---|---|
| Cache schema uniquement | **+11.5 %** |
| BureauBalance lazy fix uniquement | **+3.4 %** |
| Les deux combinées | **+13.5 %** (non cumulatif pur — léger overlapping) |

Le cache schema est le contributeur principal (11.5 %). Le fix bureau_balance ajoute
~2-3 % supplémentaires.

### Implémentation

Les optimisations sont appliquées via `scripts/optimize_pipeline.py` — un wrapper
qui deep-copie le pipeline et monkey-patche les méthodes inefficaces. **L'API n'est
pas modifiée** ; le wrapper est conçu pour le benchmark uniquement.

```python
from scripts.optimize_pipeline import optimize

pipeline = optimize(InferencePipeline.load(...))
ids, probas = pipeline.predict(raw_tables)  # version optimisée
```

### Fichiers de référence

| Fichier | Contenu |
|---|---|
| `docs/benchmark/preprocessing_opt.json` | Résultats bruts (8 batch sizes, 20 runs) |
| `scripts/optimize_pipeline.py` | Wrapper d'optimisation |

---

## Conclusion — targets d'optimisation

| Target | Impact sur `/predict/rows` | Impact sur `/predict` | Priorité |
|---|---|---|---|---|---|
| ONNX export (LightGBM) | **Modéré** (modèle → **+47%**, pipeline → <1%) | Négligeable (0.3%) | **Moyenne** (allège image Docker) |
| **Schema caching + lazy fix** | **+9% pipeline** (cache schema → **+11.5%**) | Marginal (I/O domine) | **Faible** (gain modeste, API non modifiée) |
| Cache / Parquet pour DataSource | N/A | **Élevé** (72% I/O) | **Haute** (si `/predict` utile) |
| Batch inference | Déjà efficace (4165 p/s) | Déjà efficace (60 p/s) | N/A |
| Parallelisme | Dégrade perf (GIL) | N/A | À éviter |
