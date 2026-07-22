# CHANGELOG — Community v4.2.9 (déploiement + gating)

> v4.2.9 = v4.2.8 + quickstart Docker et ruff bloquant. Aucune formule modifiée.

## Déploiement / quickstart (P1)
- **`Dockerfile`** : image Python 3.11-slim, utilisateur non-root, install
  `.[postgres]` pour le bootstrap réel.
- **`docker-compose.yml`** : `app` + PostgreSQL 16 (healthcheck). Bootstrap du
  schéma public par défaut ; démo des fonctions pures documentée
  (`docker compose run --rm app python examples/sa_pure_functions.py`).
- **`.dockerignore`**.

## Gating statique (P1)
- **ruff rendu bloquant** en CI (sous-ensemble critique `E9,F63,F7,F82`).
- **mypy** report-only, prêt à basculer (retirer `|| true` après un run local à 0 erreur).
- bandit reste bloquant ; couverture gate 60 % conservée.

## Versioning
- Bump package `4.2.8` → `4.2.9` ; en-têtes, manifeste et smoke test alignés.

## Note
Licence : voir `LICENSE-COMMUNITY.md` (licence d'évaluation ; passage à une OSS
permissive type Apache-2.0 = décision de positionnement à arbitrer).
