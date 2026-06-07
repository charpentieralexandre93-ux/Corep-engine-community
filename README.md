# Corep Engine Community v4.2.6

Édition publique volontairement limitée à deux moteurs réglementaires :

- **SA** — approche standard du risque de crédit, CRM et supporting factors ;
- **SA-CCR** — calcul de l'exposition au risque de contrepartie sur dérivés.

## Installation

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
corep-community
```

## Périmètre publié

Le package expose uniquement :

- `standard_engine.py` ;
- `saccr_engine.py` ;
- leurs dépendances techniques directes ;
- un registre public limité à `SA` et `SA_CCR` ;
- des tests de fumée et une CI multi-version.

## Périmètre exclu

Aucun moteur ni composant Enterprise n'est fourni : IRB, CVA, SFT, FRTB,
Market Risk, liquidité, IRRBB, risque opérationnel, titrisation, grands
risques, fonds propres, crypto-actifs, Output Floor, FINREP, DPM/XBRL,
bootstrap SQL complet, mappings propriétaires et orchestration multi-moteurs.

## Utilisation

Les moteurs utilisent l'interface `Database` et supposent que les tables et
règles nécessaires à SA et SA-CCR sont disponibles dans PostgreSQL. Le schéma
complet de la plateforme Enterprise n'est pas inclus.

## Licence

Cette publication est proposée sous une licence d'évaluation source-visible.
Voir `LICENSE-COMMUNITY.md`.

> Certaines versions antérieures du projet ont pu être publiées sous licence
> MIT. Les droits déjà accordés sur ces versions antérieures ne sont pas
> révoqués par cette édition.
