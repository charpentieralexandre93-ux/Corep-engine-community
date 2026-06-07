-- =============================================================================
-- 00_reset_database_dev_ONLY.sql
-- ⚠️  SCRIPT DESTRUCTIF — RÉSERVÉ AU DÉVELOPPEMENT LOCAL
-- =============================================================================
-- Supprime complètement les 5 schémas applicatifs et toutes leurs données.
-- À NE JAMAIS exécuter sur une base contenant des données métier réelles.
--
-- Ce script n'est PAS chargé automatiquement par bootstrap_postgresql().
-- Il doit être déclenché explicitement :
--   - Windows : reset_database_dev_ONLY.bat   (demande saisie "RESET")
--   - Manuel  : psql -d <db> -f sql/00_reset_database_dev_ONLY.sql
--
-- Après exécution, relancer :
--   - Windows : init_database_windows.bat
--   - Manuel  : python -m corep_crr3.bootstrap
-- pour reconstruire toutes les tables, contraintes et seeds.
-- =============================================================================

BEGIN;

-- Suppression en cascade — toutes les tables, vues, séquences, triggers,
-- types et contraintes de chaque schéma sont effacés.
DROP SCHEMA IF EXISTS rpt  CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS ref  CASCADE;
DROP SCHEMA IF EXISTS stg  CASCADE;
DROP SCHEMA IF EXISTS meta CASCADE;

COMMIT;

-- Vérification post-reset (à lancer après) :
--   SELECT schema_name FROM information_schema.schemata
--   WHERE schema_name IN ('meta','stg','ref','core','rpt');
-- → doit renvoyer 0 lignes.
