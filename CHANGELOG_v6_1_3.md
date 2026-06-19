# Changelog v6.1.3 — COREP Engine Community

Date : 19 juin 2026

Release corrective d’industrialisation générée depuis Enterprise. **Le périmètre public reste strictement limité à SA et SA-CCR et aucune formule réglementaire n’est modifiée.**

## Corrigé

- publication GitHub impossible tant que la CI Community complète n’est pas verte ;
- ajout d’un job Docker bloquant : build, utilisateur non-root, smoke test, bootstrap Community et readiness PostgreSQL 16 ;
- preuves de release alignées sur la matrice Python réelle 3.11/3.12/3.13 ;
- ZIP source déterministe, sans caches ni sorties de build, construit deux fois et comparé en CI ;
- ZIP source inclus dans les artefacts de release ;
- PostgreSQL de `docker-compose.yml` épinglé par digest ;
- contrat public renforcé pour vérifier les nouveaux garde-fous.

Les refactorings lourds de couverture, complexité et typage restent planifiés pour v6.2.0.
