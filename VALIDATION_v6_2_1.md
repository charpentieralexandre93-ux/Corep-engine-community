# Validation Corep Engine Community v6.2.1

Date de validation : 20 juin 2026

## Périmètre

Édition publique limitée à SA et SA-CCR. Cette release corrective synchronise
le schéma PostgreSQL du moteur Standard, sécurise le nettoyage Docker Compose
et conserve les contrôles de non-régression, de version et d'intégrité.

## Contrôles exécutés par le patch de livraison

- contrat de release et cohérence de version ;
- vérification du manifeste d'intégrité ;
- test de contrat DDL/INSERT du moteur Standard ;
- suite Pytest complète, sauf option explicite `--skip-full-tests` ;
- construction et vérification du ZIP source déterministe.
