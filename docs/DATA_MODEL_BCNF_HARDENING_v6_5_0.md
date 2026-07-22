# Data Model BCNF Hardening — v6.5.0

## Objectif

La v6.5.0 durcit le modèle relationnel sans refonte destructive. Le périmètre visé est volontairement limité aux sources de vérité réglementaires : référentiels, rule sets, règles de décision, mappings COREP/DPM et conditions atomiques.

Les tables de staging, de résultats et d'audit restent stables. Elles peuvent rester dénormalisées lorsque c'est nécessaire pour conserver un snapshot explicable, performant et comparable aux sorties v6.4.1.

## Changements principaux

- ajout du script `04_post_seed/99_bcnf_hardening_v6_5_0.sql` ;
- création du dictionnaire `ref.ref_condition_fields` ;
- ajout de FK des conditions atomiques vers ce dictionnaire ;
- contrôle des opérateurs de conditions ;
- vérification des champs/valeurs non vides ;
- stabilisation des natural keys des mappings ;
- ajout de vues de compatibilité `ref.v_ref_mapping_rules_authoring` et `ref.v_ref_template_mapping_rules_authoring`.

## Non-régression

Le script est idempotent et n'exécute aucun `DROP TABLE`, aucun `DROP SCHEMA`, aucune suppression de colonne. Les moteurs existants continuent d'utiliser les mêmes tables de calcul et les mêmes contrats d'entrée/sortie.

## Limite volontaire

Cette version ne transforme pas tout le projet en BCNF stricte. Elle applique la BCNF là où elle apporte le plus de valeur réglementaire : les référentiels et mappings. Les résultats calculés restent des preuves d'exécution et peuvent conserver des colonnes matérialisées.
