# CHANGELOG — Community v4.2.8

> v4.2.8 = étape 1 de sécurisation CI : couverture unitaire pure SA / SA-CCR, seuil de couverture réaliste et versioning harmonisé.

## Ajouts

- Ajout de `tests/test_v4_2_8_step1_unit_coverage.py` : tests unitaires sans PostgreSQL sur les helpers purs :
  - `decision_engine` : matching, cache de règles, trace buffer ;
  - `standard_engine` : CRM UFCP/FCP, buckets de maturité, haircut FX, maturity mismatch ;
  - `supporting_factors` : SME two-tier, booléens PostgreSQL, trace buffer ;
  - `saccr_engine` : delta optionnel, maturity factor, adjusted notionals, add-ons IRD/FX/Credit/Equity/Commodity, multiplier et margin state.

## CI / garde-fous

- Couverture Community mesurée : environ 66 %.
- Seuil CI `--cov-fail-under` remonté à 60 %.
- `pip-audit` reste report-only sans rendre le workflow rouge.

## Versioning

- Bump package : `4.2.7` → `4.2.8`.
- `corep_crr3.__version__` aligné sur `4.2.8`.

## Correctif packaging SQL Community

- Ajout d'un contrat SQL en liste blanche (`COMMUNITY_SQL_CONTRACT.json`) limité
  aux moteurs publics SA et SA-CCR.
- Ajout du bootstrap autonome `corep_crr3.community_bootstrap` avec suivi des
  checksums dans `meta.schema_migrations` et reset destructif explicitement
  confirmé.
- Distribution d'un socle SQL public dédié, des seeds et mappings SA/SA-CCR dans
  `sql/`, ainsi que dans les ressources du package pour les installations wheel.
- Les variantes Community du schéma commun, des domaines, du seed de référence
  et du mapping SA excluent explicitement FINREP, la titrisation et toute
  référence aux moteurs Enterprise.
- Ajout d'une contrainte finale dédiée Community, sans référence à un moteur
  Enterprise.
- Ajout de tests unitaires du bootstrap et d'une recette PostgreSQL réelle dans
  GitHub Actions.
- Le builder Enterprise vérifie désormais simultanément les frontières Python,
  les chemins SQL et le contenu SQL avant de générer l'archive publique.
