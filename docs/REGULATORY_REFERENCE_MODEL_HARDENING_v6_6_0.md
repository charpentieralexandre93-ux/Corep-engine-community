# Community v6.6.0 — Regulatory Reference Model Hardening

## Objectif

La v6.6.0 renforce le modèle de références réglementaires sans refonte destructive.
Elle ajoute un catalogue auditable des relations `ref.*`,
de leurs clés naturelles, de leur cible de normalisation et de leur périmètre d'édition.

## Stratégie de non-régression

- aucune suppression de table, colonne ou donnée ;
- aucune modification des tables de staging, résultats ou audit ;
- ajout uniquement de tables de gouvernance `meta.reference_model_assertions` et `ref.ref_reference_tables` ;
- contraintes idempotentes sur les référentiels actifs ;
- script appliqué après `99_bcnf_hardening_v6_6_0.sql` et avant les contraintes finales.

## Statut de normalisation cible

- référentiels réglementaires, taxonomies, règles et mappings : BCNF ciblée ;
- entités métier opérationnelles : 3NF forte ou quasi-BCNF ;
- staging/résultats/audit : dénormalisation contrôlée hors périmètre du hardening.

## Script livré

`sql/04_post_seed/99_regulatory_reference_model_hardening_v6_6_0.sql`

## Vue de contrôle

`ref.v_reference_model_hardening_status`

