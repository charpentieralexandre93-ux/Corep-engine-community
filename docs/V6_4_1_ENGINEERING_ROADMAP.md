# COREP Community v6.4.1 — chantiers techniques

Cette version ajoute les garde-fous techniques préparatoires avant toute extension fonctionnelle :

- plan SQL déterministe contrôlé par `corep_crr3.sql_migrations` ;
- budgets temps/mémoire contrôlés par `corep_crr3.resource_budgets` ;
- benchmark volumétrique public `benchmarks/bench_volume_e2e.py` ;
- dossier de readiness réglementaire en fail-closed `evidence/regulatory_dossier_v6_4_1.json`.

Le périmètre public reste volontairement limité à SA et SA-CCR. Les éléments de readiness ne transforment pas l'édition Community en chaîne de remise officielle.
