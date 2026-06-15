# Corep Engine Community v6.0.0

## Distribution publique industrialisée

- périmètre inchangé : SA et SA-CCR uniquement ;
- manifeste SHA-256 vérifiable du code, du SQL, de la CI et de la documentation ;
- commande `corep-community-health` pour les contrôles runtime ;
- commande `corep-community-release-verify` pour la vérification de release ;
- wheel et sdist contrôlés, build reproductible et provenance de release ;
- image Docker multi-stage, installation depuis wheel et utilisateur non-root ;
- actions GitHub épinglées par SHA complet ;
- audit de dépendances et SBOM bloquants dans la CI de référence ;
- absence explicite des composants DPM/xBRL-CSV et des moteurs Enterprise.

## Qualification locale

- 140 tests réussis, 1 test PostgreSQL conditionnel ignoré ;
- couverture globale avec branches supérieure au seuil de 64 % ;
- Ruff, Mypy et Bandit Medium/High réussis ;
- contrat public et frontière SA/SA-CCR validés.
