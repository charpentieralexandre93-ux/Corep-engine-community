# Release Report — Corep Engine Community v6.2.0

**Statut local : GO pour soumission à la CI. Publication interdite tant que le workflow Community complet n’est pas vert.**

Date de validation locale : 19 juin 2026

## Périmètre

Édition publique générée depuis Enterprise v6.2.0, limitée à SA et SA-CCR. Aucun moteur privé, aucune formule prudentielle et aucun schéma SQL public n’est modifié volontairement.

## Travaux lourds

- Ruff complet `E/F/W/I/C90`, seuil de complexité 20 et formatage déterministe ;
- Mypy strict renforcé sur les moteurs et contrats partagés ;
- GUI Community inclus dans la couverture officielle ;
- tests headless du cycle de configuration, de la journalisation, des commandes et des files d’événements ;
- baseline de couverture de branche SA/SA-CCR/GUI ;
- benchmark SA/SA-CCR/CRM machine-readable et bloquant en CI.

## Résultats locaux

- Pytest : **178 réussis, 1 ignoré** ;
- couverture combinée : **67,99 %** ; statements : **69,19 %** ; branches : **63,53 %** ;
- GUI Community : **55,01 %** combiné ;
- Ruff complet et format : **PASS** ;
- Mypy : **PASS, 16 modules** ;
- Bandit moyen/élevé : **PASS** ;
- docstrings CLI/GUI : **72/72 (100 %)** ;
- frontière SA/SA-CCR, SBOM, contrat de release et manifeste : **PASS**.

## Performance

Sur 50 000 itérations par noyau, le débit local le plus bas est resté supérieur à **445 000 appels/s**. Le seuil CI est fixé à **5 000 appels/s par noyau** pour détecter les régressions significatives tout en restant portable.

## Chaîne de publication

La publication dépend de l’intégralité du workflow Community : tests, couverture, Ruff, Mypy, Bandit, PostgreSQL, Docker, audit runtime, performance, frontière publique et reproductibilité.

## Limites locales

Docker, PostgreSQL réel, `pip-audit` réseau et Python 3.11/3.12 n’ont pas été exécutés localement. Ils restent bloquants dans GitHub Actions.
