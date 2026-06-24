# AGENTS.md — oc-p8

## Directive de co-réflexion

En cas de doute ou d'ambiguïté, **demander avant d'agir**.
Si plusieurs options se présentent, **proposer un exemple minimal pour chaque** afin de faciliter la délibération et trancher.
Après réflexion et décision commune, **archiver le choix dans DECISIONS.md** avec sa justification.

## Documents de référence

- **docs/CONTEXT.md** — Mission, modèle source, objectif portfolio
- **docs/ARCHITECTURE.md** — Stack, flux, structure repo, conventions
- **docs/DECISIONS.md** — Registre incrémental des choix délibérés
- **docs/ROADMAP.md** — Phases d'implémentation

## Toolchain

- **Package manager** : `uv` (pas pip/poetry). Utiliser `uv run <command>` ou `uv add`.
- **Python** : 3.12+ (voir `.python-version`)
- **Formatter/linter** : `ruff` (line-length=100, target py312, rules E/F/I/B)
- **Type checker** : `ty` (`uv run ty check`), pas mypy ou pyright
- **Tests** : `pytest` avec coverage. Layout `src/` (coverage sources = `src`)

## Commandes de référence

```bash
uv run ruff check . --fix    # auto-fix
uv run ruff check .          # vérification
uv run ruff format .         # formatage
uv run ty check              # type check
uv run pytest                # tests (≥85% coverage, voir pyproject.toml fail_under)
```

Pre-commit hooks : `ruff-fix → ruff-check → ruff-format → ty`. Pre-push : `pytest`.
**Ne pas lancer les tests systématiquement après chaque modification** — le pre-push hook s'en charge.

Pour lancer un test spécifique :
```bash
uv run pytest tests/path/test_file.py::test_name
```



## Git

- **Never commit or push without explicit user request.**
- After completing code changes, present a summary of what changed — but do NOT `git commit`, `git push`, or `gh pr create` unless explicitly asked.
- When asked to commit, inspect `git status`, `git diff`, and recent commits first. Write concise commit messages matching the repo style.

## Config & secrets

- Utiliser `pydantic-settings` + env vars — voir le skill `python-configuration`.
- `.env` pour le local (gitignored), jamais de secrets dans le code.
