# Release Report — Corep Engine Community v6.0.4

## Correctif

- priorité déterministe des licences runtime revues sur les métadonnées installées ;
- NumPy normalisé vers `BSD-3-Clause` ;
- `psycopg2-binary` normalisé vers `LGPL-3.0-or-later` ;
- expressions SPDX composites sérialisées dans CycloneDX `expression` ;
- tests de normalisation PEP 503, idempotence et stricte résolution ajoutés.

## Non-régression

- Pytest : **161 passed, 1 skipped** ;
- tests SBOM ciblés : **7 réussis** ;
- cohérence de version : **OK** ;
- frontière Community/Enterprise : **OK** ;
- aucune formule prudentielle, API moteur ou structure SQL fonctionnelle modifiée.

## Environnement de validation

- Python 3.13 ;
- validation locale sans PostgreSQL actif : les tests E2E conditionnels restent ignorés selon leur garde existante.
