# Corep Engine Enterprise v6.0.1

## Objet

Release de durcissement P0/P1 sans modification volontaire des formules prudentielles.

## P0 corrigés

- chaîne batch fail-closed : les échecs de contrôles ou de réconciliation interdisent désormais un statut `COMPLETED` et bloquent les exports officiels ;
- statuts structurés `COMPLETED_WITH_WARNINGS`, `FAILED_CONTROLS`, `FAILED_RECONCILIATION` et `FAILED_ENGINE` ;
- findings qualité persistés et sérialisables avec statuts `PASS`, `WARNING`, `FAIL`, `NOT_APPLICABLE` ;
- readiness PostgreSQL réelle : connexion, identité serveur, migrations et relations obligatoires ;
- registre réglementaire YAML unique, avec applicabilité par module, template et date ;
- dates spécifiques C 16.02/C 16.03/C 16.04 à partir du 30 juin 2026.

## P1 corrigés

- `safe_read()` ne masque plus les erreurs SQL, permissions ou connexions ; seules les absences optionnelles explicitement reconnues sont tolérées ;
- activation runtime des paramètres versionnés pour SA-CCR, CVA et mapping ;
- mypy complet bloquant, dette ramenée de 62 erreurs à zéro ;
- couverture renforcée des contrôles et validations critiques ;
- dépendances Python 3.11 verrouillées dans `constraints-py311.txt` ;
- images Python et PostgreSQL épinglées par digest ;
- matrice CI étendue à Python 3.13 ;
- manifest étendu à l’intégralité du payload de release ;
- génération de preuve de release JSON liant tests, couverture, E2E, manifest, SBOM et artefact.

## Correctifs découverts pendant le typage

- correction de l’ordre des arguments FINREP F 01.01 ;
- correction de l’index d’agrégation `rwa_total` du moteur titrisation.

## Non-régression

- tests unitaires/intégration complets ;
- seuils de couverture par composant critique ;
- Ruff, mypy, Bandit, manifest, frontière Community/Enterprise et reproductibilité des wheels.
