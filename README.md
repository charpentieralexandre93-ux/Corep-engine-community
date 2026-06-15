# COREP CRR3 Engine Community — v6.0.4

Édition publique open-core limitée à **SA crédit + SA-CCR**. Elle contient les fonctions de calcul, le bootstrap PostgreSQL public, les schémas SQL autorisés, une interface graphique de diagnostic et les garde-fous de frontière Community/Enterprise.

> Aucun moteur Enterprise n'est inclus : IRB, CVA, liquidité, market risk, titrisations, grands risques, output floor, risque opérationnel et fonds propres restent privés.

## Points d'entrée

| Usage | Commande |
|---|---|
| Afficher le registre public | `corep-community` |
| Interface graphique Community | `corep-community-gui` ou `python -m corep_crr3.community_gui` |
| Bootstrap PostgreSQL | `corep-community-bootstrap` |
| Diagnostic PostgreSQL | `corep-community-health` |
| Vérification release | `corep-community-release-verify --root . --manifest RELEASE_MANIFEST.json --version 6.0.4` |

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

## Preuves qualité v6.0.4

- `standard_engine.py` byte-identique à l'Enterprise ;
- refactoring P0 avec unités sous CC 20 ;
- tests de non-régression SA ;
- garde AST empêchant l'import de moteurs privés ;
- politique documentée des exceptions larges ;
- SBOM CycloneDX avec licence SPDX du runtime PostgreSQL ;
- CI, manifest SHA-256 et wheel public contrôlé.

- Python 3.11 est la baseline reproductible ; 3.9/3.12/3.13 sont des compatibilités best-effort testées en CI ;
- 100 % des 71 fonctions des modules exposés par les CLI/GUI disposent d’une docstring, avec gate à 85 % ;
- la couverture de branche de `standard_engine.py` est comparée à la baseline v6.0.2 et publiée dans la preuve de release.

Les résultats exacts de cette archive sont consignés dans `RELEASE_REPORT_v6_0_4.md` et `RELEASE_MANIFEST.json`.

## Historique et licence

Voir [`CHANGELOG_v6_0_4.md`](CHANGELOG_v6_0_4.md) et les autres fichiers `CHANGELOG_v*.md`.

Apache License 2.0 : [`LICENSE`](LICENSE), [`LICENSE-COMMUNITY.md`](LICENSE-COMMUNITY.md) et [`NOTICE`](NOTICE).
