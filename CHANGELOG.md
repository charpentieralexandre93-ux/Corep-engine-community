# Changelog — COREP Engine CRR3 (Community)
- **6.10.1** — `product_version` des benchmarks dérivé de `__version__` (fin du littéral figé) et alignement de version sur l'Enterprise v6.10.1 (correctifs P1 IRB/Market-Risk hors périmètre Community). Statut réglementaire NO-GO fail-closed inchangé. Durcissement qualité : typage strict global (disallow_untyped_defs sur les 20 modules), warn_return_any, hygiène lint. Ratchet complexité (16) et taille de fonction (160) ; revue P2 : aucun écart. Bank-readiness P1 : gates pip-audit+semgrep, SBOM licencié, policy vulnérabilités, registre sécurité, BCBS 239, lignage, runbook avec drill DR évidencé. Itération 11 : défaut CLI du dossier dérivé de `__version__`, manifeste saccr régénéré depuis le contrat, `mypy_modules` dérivé (16→20) + bloc README rescellé, règles anti-drift `bump_version` alignées sur l'Enterprise. Reproductibilité SBOM restaurée (rescellement canonique, contenu invariant). Itération 12 : workflow de rescellement des preuves `reseal_metrics.yml` (toolchain verrouillée, fichier de preuves dérivé de `pyproject.toml`) et note de gouvernance `RELEASING.md` sur les jalons internes v6.9.0/v6.10.0. *(cf. `changelogs/CHANGELOG_v6_10_1.md`)*
- **6.10.0** — Décotes collatéral alignées sur l'Art.224 CRR3 consolidé (tranches ≤1/1-3/3-5/5-10/>10 ans ; corporates CQS1 1/3/4/6/12 %, CQS2-3 2/4/6/12/20 % ; actions 20/30 %, or 20 % — table 3) ; catégorie LCR « Secured Funding L2B Other » à 35 % (Art.28(3) DR 2015/61) ; nouvel orchestrateur local `tools/release_check.py` enchaînant les 14 gates de la CI avant empaquetage ; tests de référence cités et tests hérités mis à jour. Souverains inchangés en effet ; statut réglementaire NO-GO fail-closed inchangé.
- **6.9.0** — Correctif latent du contrat de release (référence dérivée de `__version__`), archivage des preuves historiques et alignement des tampons de version. *(cf. `changelogs/CHANGELOG_v6_9_0.md`)*
- **6.8.1** — SBOM généré depuis le lockfile (reproductible, `--check` CI) et contrat de release auto-porté par `__version__` ; alignement sur l'Enterprise v6.8.1. *(cf. `changelogs/CHANGELOG_v6_8_1.md`)*
- **6.8.0** — Hygiène du dépôt (archivage `changelogs/` + `releases/`) et alignement de version sur l'Enterprise v6.8.0. *(cf. `changelogs/CHANGELOG_v6_8_0.md`)*
- **6.7.1** — Alignement de version sur l'Enterprise v6.7.1 (corrections documentaires réglementaires). *(cf. `changelogs/CHANGELOG_v6_7_1.md`)*
- **6.7.0** — Gate de preuves durcie (`tests_collected` dérivé du JUnit, garde de cohérence interne) et exécutée sur la toolchain verrouillée (leg 3.12) ; métriques réconciliées. *(cf. `changelogs/CHANGELOG_v6_7_0.md`)*
- **6.4.1** — Chantiers techniques : migrations SQL, budgets ressources, benchmarks volumétriques et dossier réglementaire fail-closed. *(cf. `changelogs/CHANGELOG_v6_4_1.md`)*
- **6.4.1** — Consolidation pré-v6.4.1 : métriques de release stabilisées, nettoyage des références actives et garde-fous P1 renforcés. *(cf. `changelogs/CHANGELOG_v6_4_1.md`)*

- **6.4.1** — Consolidation P0/P1, preuves de gouvernance, métriques reproductibles, nettoyage des références actives et versioning aligné. *(cf. `changelogs/CHANGELOG_v6_4_1.md`)*
- **6.4.1** — Remédiation complète des P1 v6.3.1, durcissement production/release et refactoring sans régression. *(cf. `changelogs/CHANGELOG_v6_4_1.md`)*
- **6.3.1** — Remédiation P0/P1 Docker/PostgreSQL, durcissement de release et optimisation P2 des haircuts FCP. *(cf. `changelogs/CHANGELOG_v6_3_1.md`)*
- **6.3.0** — Correction P0 du contrat SQL SA, migration PostgreSQL et durcissement CI/packaging. *(cf. `changelogs/CHANGELOG_v6_3_0.md`)*

- **6.2.0** — Qualité statique renforcée, couverture GUI publique et budget de performance partagé. *(cf. `changelogs/CHANGELOG_v6_2_0.md`)*
- **6.1.3** — Release Community gated, Docker/PostgreSQL CI et ZIP source déterministe. *(cf. `changelogs/CHANGELOG_v6_1_3.md`)*
- **6.1.2** — Release reproductible depuis Enterprise, SBOM/manifest synchronisés et durcissement PostgreSQL partagé. *(cf. `changelogs/CHANGELOG_v6_1_2.md`)*
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
