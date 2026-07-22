# CHANGELOG v6.10.1

- **6.10.1** — `product_version` des benchmarks volumétriques désormais dérivé de `__version__` (fin du littéral figé à 6.4.1) ; alignement de version sur l'Enterprise v6.10.1 (les correctifs réglementaires P1 IRB / Market-Risk sont hors périmètre Community : SA crédit + SA-CCR uniquement). Statut réglementaire NO-GO fail-closed inchangé.

- **Durcissement qualité (même release)** — Typage strict global accompli : l'intégralité de `src/corep_crr3` (20 modules) passe `disallow_untyped_defs`, `disallow_incomplete_defs`, `check_untyped_defs` et `warn_return_any` au niveau global du `pyproject` (liste d'overrides supprimée car redondante), annotations alignées sur l'Enterprise pour les modules partagés (`db`, `saccr_engine`, …) plus `public_registry` et `community_bootstrap`, sans changement de comportement ; retrait d'un `type: ignore` obsolète dans `db.py` (stubs psycopg2 du lock dev).

- **Gouvernance qualité & revue P2 (même release)** — Ratchet des seuils : `max-complexity` 20→16 et garde de taille de fonction 200→160 lignes (maxima réellement observés sur le périmètre Community). Revue P2 des constantes réglementaires du périmètre (SA crédit, SA-CCR, facteurs de soutien, grands risques) : **aucun écart**.

- **Bank-readiness P1 (même release)** — SBOM enrichis des licences par composant (lues des métadonnées des paquets, produit inclus) ; gate CI « pip-audit » sur le lock runtime (0 vulnérabilité connue au 18/07/2026) et gate « semgrep » sur règles locales versionnées `.semgrep/rules.yml` (0 finding après statuts) ; politique de gestion des vulnérabilités avec SLA (`docs/VULNERABILITY_MANAGEMENT_POLICY.md`) ; registre des findings sécurité statués (`docs/SECURITY_FINDINGS_REGISTER.md`) ; cartographie BCBS 239 → contrôles (`docs/BCBS239_CONTROL_MAPPING.md`) ; lignage des données source→états (`docs/DATA_LINEAGE_COREP.md`) ; runbook d'exploitation avec drill de sauvegarde/restauration exécuté et évidencé (`docs/OPERATIONS_RUNBOOK.md`, `evidence/dr_restore_drill_v6_10_1.json` côté Enterprise : restore 1,45 s, digest identique, 0 erreur).

*(Historique : voir CHANGELOG.md et changelogs/.)*
