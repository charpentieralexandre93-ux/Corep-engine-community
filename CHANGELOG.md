# Changelog — COREP Engine CRR3 (Community)

- **6.2.0** — Qualité statique renforcée, couverture GUI publique et budget de performance partagé. *(cf. `CHANGELOG_v6_2_0.md`)*
- **6.1.3** — Release Community gated, Docker/PostgreSQL CI et ZIP source déterministe. *(cf. `CHANGELOG_v6_1_3.md`)*
- **6.1.2** — Release reproductible depuis Enterprise, SBOM/manifest synchronisés et durcissement PostgreSQL partagé. *(cf. `CHANGELOG_v6_1_2.md`)*
Le format suit la convention [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/)
et le projet adhère au [versionnage sémantique](https://semver.org/lang/fr/).

> **Note de consolidation (v6.1.1, audit P3-3).** Ce fichier devient le journal
> canonique unique. L'historique détaillé par version est conservé en archive et
> tracé par `RELEASE_MANIFEST.json`.

---

## [6.1.1] — 2026-06-16

Release de correctifs issue d'un audit technique externe. Les correctifs
applicables à l'édition Community portent sur le noyau de calcul partagé et
l'outillage. La frontière Community/Enterprise et la byte-identité du noyau
partagé sont préservées.

### Modifié
- **P1-2 — Noyau typé `mypy` étendu.** Signatures de `standard_engine` et
  `saccr_engine` (modules partagés, byte-identiques à l'édition Enterprise)
  intégralement annotées et ajoutées au noyau strict bloquant.
- **P2-2 — Driver PostgreSQL.** L'extra `postgres` documente la recommandation
  d'utiliser `psycopg2` source en production (le `-binary` restant pour dev/test).

### Ajouté
- **P2-1 — Recette E2E PostgreSQL auto-portée.** `scripts/run_e2e_local.sh` lève
  la base via `docker-compose`, bootstrappe le schéma Community et exécute la
  suite E2E Community.

### À finaliser via la chaîne d'outils
- Confirmer `mypy`, `pytest`, couverture et `pip-audit` via la CI / un toolchain
  local ; régénérer le wheel reproductible et son empreinte.

---

## Historique condensé

- **6.1.0** — Alignement sur l'édition Enterprise (contrat Python 3.11–3.13,
  release sur outils verrouillés).
- **≤ 6.0.x** — Édition Community open-core (Apache-2.0) : moteurs SA et SA-CCR,
  GUI, bootstrap, registre public.
