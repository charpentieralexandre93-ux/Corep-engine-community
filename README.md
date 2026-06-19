# COREP CRR3 Engine Community — v6.3.0

Édition publique open-core limitée à **SA crédit + SA-CCR**. Elle contient les fonctions de calcul, le bootstrap PostgreSQL public, les schémas SQL autorisés, une interface graphique de diagnostic et les garde-fous de frontière Community/Enterprise.

> Aucun moteur Enterprise n'est inclus : IRB, CVA, liquidité, market risk, titrisations, grands risques, output floor, risque opérationnel et fonds propres restent privés.

## Points d'entrée

| Usage | Commande |
|---|---|
| Afficher le registre public | `corep-community` |
| Interface graphique Community | `corep-community-gui` ou `python -m corep_crr3.community_gui` |
| Bootstrap PostgreSQL | `corep-community-bootstrap` |
| Diagnostic PostgreSQL | `corep-community-health` |
| Vérification release | `corep-community-release-verify --root . --manifest RELEASE_MANIFEST.json --version 6.3.0` |

L'édition Community n'embarque pas l'orchestrateur Enterprise `batch/run_batch.py`. Elle sert de moteur public SA/SA-CCR et de socle d'intégration.

## Installation

Calculs purs, sans PostgreSQL :

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
corep-community
```

Avec PostgreSQL et outils de développement :

```bash
python -m pip install -e ".[postgres,dev]"
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:5432/DBNAME"
corep-community-bootstrap --list
corep-community-bootstrap
corep-community-health
corep-community-gui
```

Sous Windows : `launch_community_gui.bat`.

## Utilisation Python

```python
from corep_crr3.standard_engine import ccf_from_annex_i_bucket
from corep_crr3.saccr_engine import _calc_multiplier

assert ccf_from_annex_i_bucket("BUCKET_5") == 0.10
```

Pour une exécution base de données, importer `run_standard_engine` ou `run_saccr_engine` dans votre propre orchestrateur et fournir une instance `Database` ainsi qu'un `batch_id`.

## Périmètre public

- SA crédit : CCF, RW, CRM FCP/UFCP, facteurs PME/infrastructure ;
- SA-CCR : RC, PFE, add-ons taux/change/crédit/actions/commodities ;
- schémas, seeds et mappings strictement nécessaires à ces deux moteurs ;
- aucune dépendance runtime obligatoire pour les calculs purs ; `psycopg2-binary` est un extra.

Notes méthodologiques : [`docs/REGULATORY_METHODOLOGY_INDEX.md`](docs/REGULATORY_METHODOLOGY_INDEX.md). Politique Python : [`docs/PYTHON_COMPATIBILITY.md`](docs/PYTHON_COMPATIBILITY.md).

## Preuves qualité v6.3.0

- **178 tests réussis**, avec une recette PostgreSQL exécutée exclusivement en CI ;
- couverture officielle incluant le GUI Community : **67,99 %**, dont **63,53 %** de branches ;
- GUI Community couvert à **55,01 %** grâce à des tests headless de configuration, logs, processus et événements ;
- Ruff complet `E/F/W/I/C90`, formatage déterministe, Bandit et politique des exceptions bloquants ;
- Mypy valide les **16 modules** publics ;
- baseline de branche sur `standard_engine.py`, `saccr_engine.py` et `community_gui.py` ;
- benchmark JSON des noyaux SA/SA-CCR/CRM avec budget minimal bloquant ;
- frontière AST et wheel public limités à SA et SA-CCR ;
- CI Python 3.11 / 3.12 / 3.13, PostgreSQL 16, Docker non-root, audit runtime et artefacts reproductibles ;
- **72/72 fonctions CLI/GUI documentées**.

Python 3.11 reste la baseline reproductible hashée ; Python 3.12 et 3.13 sont testés en compatibilité CI.

Les résultats exacts de cette archive sont consignés dans `RELEASE_REPORT_v6_3_0.md` et `RELEASE_MANIFEST.json`.

## Docker

L’image Community exécute `corep-community` comme **commande one-shot** de diagnostic et se termine normalement. Utilisez `docker compose run --rm app`; l’image n’est pas présentée comme un service HTTP permanent.

## Historique et licence

Voir [`CHANGELOG_v6_3_0.md`](CHANGELOG_v6_3_0.md) et les autres fichiers `CHANGELOG_v*.md`.

Apache License 2.0 : [`LICENSE`](LICENSE), [`LICENSE-COMMUNITY.md`](LICENSE-COMMUNITY.md) et [`NOTICE`](NOTICE).
