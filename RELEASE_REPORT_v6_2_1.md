# COREP Engine Community v6.2.1 — rapport correctif

Cette version corrige les blocages PostgreSQL et Docker observés dans la CI de la v6.2.0.

## Correctifs

1. Ajout de `ccf_applied` et des neuf autres champs de traçabilité déjà écrits par `standard_engine.py`.
2. Ajout des mêmes colonnes via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pour la rejouabilité.
3. Définition globale du mot de passe PostgreSQL de test dans le workflow Docker.
4. Ajout d'un test de synchronisation entre l'INSERT Python et le DDL PostgreSQL.

Aucune formule réglementaire SA ou SA-CCR n'est modifiée.
