# COREP CRR3 Engine Community — v6.6.0


## Installation utilisateur rapide

Sous Windows, le parcours utilisateur final est volontairement réduit à des doubles-clics :

1. `INSTALL_WINDOWS.bat` — crée `.venv` et installe COREP Engine Community v6.6.0.
2. `RUN_GUI_WINDOWS.bat` — lance le GUI.
3. `BOOTSTRAP_SQL_WINDOWS.bat` — vérifie le plan SQL et régénère le manifeste SQL.

Documentation complète : `docs/INSTALLATION_UTILISATEUR.md`.

Édition publique open-core limitée à **SA crédit + SA-CCR**. Elle contient les fonctions de calcul, le bootstrap PostgreSQL public, les schémas SQL autorisés, une interface graphique de diagnostic et les garde-fous de frontière Community/Enterprise.

> Aucun moteur Enterprise n'est inclus : IRB, CVA, liquidité, market risk, titrisations, grands risques, output floor, risque opérationnel et fonds propres restent privés.

## Points d'entrée

| Usage | Commande |
|---|---|
| Afficher le registre public | `corep-community` |
| Interface graphique Community | `corep-community-gui` ou `python -m corep_crr3.community_gui` |
| Bootstrap PostgreSQL | `corep-community-bootstrap` |
| Diagnostic PostgreSQL | `corep-community-health` |
| Vérification release | `corep-community-release-verify --root . --manifest RELEASE_MANIFEST.json --version 6.6.0` |

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
from corep_crr3.supporting_factors import sme_blended_factor

assert ccf_from_annex_i_bucket("BUCKET_5") == 0.10
assert round(sme_blended_factor(0.7619, 3_000_000), 6) == 0.776583
```

Pour une exécution base de données, importer `run_standard_engine` ou `run_saccr_engine` dans votre propre orchestrateur et fournir une instance `Database` ainsi qu'un `batch_id`.

## Périmètre public

- SA crédit : CCF, RW, CRM FCP/UFCP, facteurs PME/infrastructure ;
- SA-CCR : RC, PFE, add-ons taux/change/crédit/actions/commodities ;
- schémas, seeds et mappings strictement nécessaires à ces deux moteurs ;
- aucune dépendance runtime obligatoire pour les calculs purs ; `psycopg2-binary` est un extra.

Notes méthodologiques : [`docs/REGULATORY_METHODOLOGY_INDEX.md`](docs/REGULATORY_METHODOLOGY_INDEX.md). Politique Python : [`docs/PYTHON_COMPATIBILITY.md`](docs/PYTHON_COMPATIBILITY.md).

<!-- RELEASE_METRICS_START -->
## Preuves qualité v6.6.0

- **214 tests réussis, 1 ignoré** ;
- couverture lignes/branches combinée : **79.21 %**, dont **72.93 %** de branches ;
- Mypy valide les **16 modules** du périmètre ;
- **104/104 fonctions CLI/GUI documentées** ;
- Ruff, formatage, Bandit, seuils par composant, manifeste et reproductibilité sont bloquants en CI.
<!-- RELEASE_METRICS_END -->

## Docker

L’image Community exécute `corep-community` comme **commande one-shot** de diagnostic et se termine normalement. Utilisez `docker compose run --rm app`; l’image n’est pas présentée comme un service HTTP permanent.

## Historique et licence

Voir [`CHANGELOG_v6_6_0.md`](CHANGELOG_v6_6_0.md) et les autres fichiers `CHANGELOG_v*.md`.

Apache License 2.0 : [`LICENSE`](LICENSE), [`LICENSE-COMMUNITY.md`](LICENSE-COMMUNITY.md) et [`NOTICE`](NOTICE).
