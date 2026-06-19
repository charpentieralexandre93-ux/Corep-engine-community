# Changelog v6.2.1 — Community

- synchronisation du DDL `core.core_standard_results` avec les 26 colonnes persistées par le moteur SA ;
- migration PostgreSQL idempotente pour les bases Community déjà bootstrapées ;
- variable `PGPASSWORD` disponible pendant le nettoyage Docker Compose ;
- test de contrat SQL empêchant une nouvelle divergence moteur/schéma ;
- bump cohérent de la chaîne de release vers 6.2.1.
