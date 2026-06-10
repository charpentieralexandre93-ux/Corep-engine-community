# CHANGELOG — Community v4.3.2

> v4.3.2 = v4.3.1 + alignement de version. Aucune fonctionnalité IRB (enterprise-only). Aucune formule modifiée.

## Changement
- `standard_engine.py` (module partagé) reçoit un **garde de routage par approche**
  identique à l'édition enterprise : une exposition `calculation_approach`
  IRB-F/IRB-A serait laissée à un moteur IRB. **No-op en community** : la colonne
  `calculation_approach` n'existe pas dans le schéma SA/SA-CCR, donc `.get`
  renvoie None et **toutes les expositions restent traitées en SA** (comportement
  strictement inchangé). Préserve l'invariant byte-identique du module partagé.

## Versioning
- Bump package : `4.3.1` → `4.3.2`.

## Note
Édition **générée** depuis l'enterprise via `tools/build_community_edition.py`
(frontière Python + contrat SQL vérifiés, version contrôlée dynamiquement). Le
moteur IRB et l'ingestion CSV restent enterprise-only.
