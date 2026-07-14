# CHANGELOG — Community v4.2.7

> v4.2.7 = base v4.2.6 + durcissement P0/P1. Aucune formule réglementaire modifiée.

## Utilisable sans PostgreSQL (P0.4 / P1.6)
- `db.py` : import `psycopg2` **paresseux** → le paquet et les moteurs
  s'importent sans psycopg2 ; les fonctions de calcul pures (SA, CRM, SA-CCR)
  s'utilisent en mémoire.
- `pyproject.toml` : `psycopg2-binary` déplacé dans l'extra **`postgres`**.
- Exemple exécutable sans base : `examples/sa_pure_functions.py`.

## Gating & qualité (P0.2 / P0.3 / P1.8 / P1.9)
- CI : **bandit bloquant**, **couverture** (`--cov-fail-under=75` + artefact),
  **pip-audit** (report-only), **Dependabot**.
- Tests étoffés (`tests/test_community_smoke.py`) : haircuts FCP (Art.223/224),
  asymétrie de maturité (Art.239), substitution UFCP, recherche de haircut,
  facteur de maturité SA-CCR, import sans psycopg2, **déterminisme**.

## Provenance
Édition **générée** depuis le dépôt enterprise via
`tools/build_community_edition.py` (frontière d'imports vérifiée par AST). Ne pas
modifier les moteurs partagés ici : corriger côté enterprise puis régénérer.

Licence : voir `LICENSE-COMMUNITY.md` (positionnement à arbitrer).
