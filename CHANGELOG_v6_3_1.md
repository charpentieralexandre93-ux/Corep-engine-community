# Changelog v6.3.1 — COREP Engine Community

Date : 20 juin 2026

## P0 — CI et robustesse PostgreSQL

- remplacement du contrôle Docker fragile basé sur `docker compose images -q app` par une image explicitement taguée et inspectée ;
- ajout de `docker compose config --quiet` avant le build pour faire échouer immédiatement les configurations invalides ;
- conservation des images Python/PostgreSQL épinglées par digest ;
- correction de l'import optionnel de `psycopg2.extensions.make_dsn` : l'absence de ce helper ne désactive plus `connect`, `extras` et `pool` ;
- prise en charge d'une connexion DB-API injectée sans `RealDictCursor`, sans modifier le chemin PostgreSQL normal.

## P1 — qualité et release engineering

- bump complet en 6.3.1 des versions, commandes CI, smoke tests, préfixes ZIP, preuves et contrats de release ;
- seuil minimal de performance relevé de 5 000 à 100 000 appels/s par noyau ;
- correction des imports tardifs des scripts GUI et smoke PostgreSQL afin que Ruff couvre aussi `scripts/` ;
- ajout de tests anti-régression pour le pilote PostgreSQL minimal, le contrat Docker et la parité des règles FCP compilées ;
- SBOM CycloneDX, preuves de couverture, rapport de validation et manifeste SHA-256 synchronisés.

## P2 — performance

- compilation des règles de haircut FCP dans un index par type de collatéral, une seule fois par batch ;
- suppression des normalisations de chaînes et du scan des types non pertinents dans le chemin chaud ;
- compatibilité conservée avec les listes de règles historiques ;
- priorité exacte/générique et premier résultat à rang égal couverts par tests.

Aucune formule réglementaire, calibration prudentielle ou règle de décision n'est modifiée. Périmètre : SA et SA-CCR publics.
