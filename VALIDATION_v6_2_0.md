# Validation Corep Engine Community v6.2.0

Date de validation locale : 19 juin 2026

## Périmètre

Édition publique générée depuis Enterprise et strictement limitée à SA et SA-CCR.

## Non-régression locale

- Pytest : **178 réussis, 1 ignoré** ;
- couverture combinée officielle : **67,99 %** ;
- couverture statements : **69,19 %** ;
- couverture branches : **63,53 %** ;
- `community_gui.py` : **55,01 %** combiné et **60,20 %** de branches ;
- `standard_engine.py` : **63,47 %** combiné ;
- `saccr_engine.py` : **65,30 %** combiné ;
- Mypy : **16/16 modules validés** ;
- docstrings CLI/GUI : **72/72, soit 100 %** ;
- Ruff complet, Ruff format, Bandit moyen/élevé, frontière publique, SBOM et contrats : **PASS** ;
- benchmark local : cinq noyaux au-dessus de **445 000 appels/s**, seuil bloquant **5 000 appels/s**.

## Contrôles exclusivement CI

Le test ignoré localement est la recette PostgreSQL Community. Docker, PostgreSQL 16, `pip-audit` réseau et les matrices Python 3.11/3.12/3.13 précèdent obligatoirement la publication.
