# Release Report — Corep Engine Community v6.3.0

**Statut local : GO pour soumission à la CI. Publication interdite tant que tous les jobs GitHub Actions ne sont pas verts.**

## Cause racine des quatre checks Community rouges

Le moteur Standard persistait dix colonnes absentes du DDL PostgreSQL exécuté. Le bootstrap et le wheel devaient également utiliser exactement le même SQL.

## Remédiation

1. DDL et INSERT Python alignés.
2. `cqs_used` stocké en texte pour supporter `UNRATED`.
3. Migration v6.2.x idempotente.
4. Tests anti-dérive et contrôle du SQL embarqué.
5. Version et noms d'artefacts alignés en 6.3.0.
6. Manifeste et ZIP alignés sur l’exclusion des sorties temporaires de couverture.

Aucune réussite PostgreSQL/Docker distante n'est revendiquée avant l'exécution GitHub Actions.
