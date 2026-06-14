# Corep Engine Community v5.0.6

[![CI](https://github.com/charpentieralexandre93-ux/Corep_engine_community/actions/workflows/ci.yml/badge.svg)](https://github.com/charpentieralexandre93-ux/Corep_engine_community/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)


Édition publique volontairement limitée à deux moteurs réglementaires :

- **SA** — approche standard du risque de crédit, CRM et supporting factors ;
- **SA-CCR** — calcul de l'exposition au risque de contrepartie sur dérivés.


## Release v5.0.6 — alignement et non-régression public

La v5.0.6 aligne le versionnement et les garde-fous de build avec la release
Enterprise sans élargir le périmètre open-core : **SA et SA-CCR uniquement**.
Les moteurs Enterprise, le stress testing, l'IMA et les schémas privés ne sont
ni copiés ni importables depuis cette distribution. Les 129 tests Community
restent verts. Voir `CHANGELOG_v5_0_6.md`.


## Interface graphique Community

La v5.0.5 ajoute un centre de contrôle limité au périmètre public SA / SA-CCR.
Il permet de configurer PostgreSQL, consulter le contrat SQL Community, lancer
le bootstrap et exécuter les smoke tests sans exposer de composant Enterprise.

```bash
python scripts/launch_community_gui.py
# ou, après installation
corep-community-gui
```

Sous Windows, utiliser `launch_community_gui.bat`. Les commandes longues sont
exécutées hors du thread graphique, sérialisées et peuvent être arrêtées depuis
la console. Voir `CHANGELOG_v5_0_5.md`.

## Installation

Les **fonctions de calcul pures** (SA, CRM, SA-CCR) ne nécessitent **pas**
PostgreSQL ni psycopg2 :

```bash
python -m pip install -e ".[dev]"     # base : calcul pur + tests
python -m pytest -q
python examples/sa_pure_functions.py  # démonstration sans base de données
corep-community
```

Pour exécuter les moteurs complets (`run_standard_engine` / `run_saccr_engine`)
sur PostgreSQL, ajouter l'extra dédié puis initialiser le schéma Community :

```bash
python -m pip install -e ".[dev,postgres]"
python -m corep_crr3.community_bootstrap --list
python -m corep_crr3.community_bootstrap
```

Reset destructif, réservé à une base locale ou éphémère :

```bash
python -m corep_crr3.community_bootstrap --reset --confirm-reset RESET
```

Le bootstrap utilise `DATABASE_URL` ou les variables PostgreSQL standard
`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` et `PGPASSWORD`.

## Périmètre publié

Le package expose uniquement :

- `standard_engine.py` ;
- `saccr_engine.py` ;
- leurs dépendances techniques directes ;
- un registre public limité à `SA` et `SA_CCR` ;
- un bootstrap PostgreSQL autonome et un sous-ensemble SQL strictement limité
  au socle partagé, à SA et à SA-CCR ;
- des tests unitaires, une CI multi-version et une recette PostgreSQL réelle.

## Périmètre exclu

Aucun moteur ni composant Enterprise n'est fourni : IRB, CVA, SFT, FRTB,
Market Risk, liquidité, IRRBB, risque opérationnel, titrisation, grands
risques, fonds propres, crypto-actifs, Output Floor, FINREP, DPM/XBRL,
mappings propriétaires des autres moteurs et orchestration multi-moteurs.

## Utilisation

Deux niveaux d'usage :

- **Fonctions pures (sans base)** : haircuts CRM, substitution UFCP, asymétrie de
  maturité, facteur de maturité SA-CCR… s'utilisent directement en mémoire
  (voir `examples/sa_pure_functions.py`). Aucun psycopg2 requis.
- **Moteurs complets** (`run_standard_engine` / `run_saccr_engine`) : utilisent
  l'interface `Database`. Les tables, règles, seeds et mappings publics requis
  sont fournis dans `sql/` et installables avec `community_bootstrap`.

## SQL public et frontière open-core

Le contrat `sql/COMMUNITY_SQL_CONTRACT.json` constitue la liste blanche des
scripts distribués. Il inclut uniquement :

- un socle BCNF public dédié aux deux moteurs, sans objets FINREP ni tables de
  moteurs privés ;
- le schéma, les règles et les mappings COREP SA ;
- le schéma, les règles et les mappings SA-CCR ;
- la normalisation des conditions et les contraintes finales Community.

Les scripts IRB, SFT, CVA, Liquidité, Market Risk/FRTB, IRRBB, Output Floor,
DPM/XBRL et autres moteurs Enterprise ne sont ni copiés ni exécutables depuis
cette édition. Les ressources SQL sont également embarquées dans le package,
ce qui permet au bootstrap de fonctionner après installation en wheel.

## Licence

Cette publication est proposée sous une licence d'évaluation source-visible.
Voir `LICENSE-COMMUNITY.md`.

> Certaines versions antérieures du projet ont pu être publiées sous licence
> MIT. Les droits déjà accordés sur ces versions antérieures ne sont pas
> révoqués par cette édition.
