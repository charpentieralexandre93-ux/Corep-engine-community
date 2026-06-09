# CHANGELOG — Community v4.3.1

> v4.3.1 = v4.3.0 + correctifs de cohérence de version et outil de versioning. Aucune formule modifiée.

## Correctifs de cohérence de version
- **Garde-fou bootstrap dynamique** : le contrôle du contrat SQL
  (`COMMUNITY_SQL_CONTRACT.json`) comparait à une version **codée en dur**
  (`!= "4.2.8"`) ; il vérifie désormais
  `contrat["version"] == corep_crr3.__version__`. Le contrat est aligné sur la
  version du package.
- **Note d'audit dynamique** : la note écrite dans `meta.schema_migrations`
  utilise `__version__` au lieu d'un littéral.
- **En-têtes harmonisés** : en-têtes `VERSION :` et titre du fichier SQL de
  validation réalignés.

## Outillage de versioning (nouveau)
- Ajout de **`tools/bump_version.py`** (`--check` / `--set X.Y.Z [--dry-run]`) :
  cohérence de version par découverte automatique (aucune liste figée).
- **CI** : étape bloquante « Cohérence de version » ajoutée — toute dérive future
  est arrêtée au push.

## Versioning
- Bump package : `4.3.0` → `4.3.1`.
- `corep_crr3.__version__` aligné sur `4.3.1`.

## Note
Édition **générée** depuis l'enterprise via `tools/build_community_edition.py`
(frontière Python + contrat SQL vérifiés, version contrôlée dynamiquement).
