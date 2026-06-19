# Changelog — v6.1.0

## P0
- Correction du bootstrap PostgreSQL et renforcement des preuves E2E publiées même en cas d'échec.
- Audit supply-chain séparé : dépendances runtime bloquantes, toolchain de développement auditée avec rapport distinct.
- Manifeste cryptographique régénéré après normalisation Git des fins de ligne.

## P1
- Contrat Python relevé à 3.11–3.13 ; suppression de Python 3.9 de la matrice CI.
- Ruff, Mypy et Bandit déplacés dans un job qualité Python 3.11 verrouillé.
- Workflows de release rendus reproductibles sans installation d'outils non épinglés.

## Non-régression
- Périmètre public inchangé : SA et SA-CCR uniquement.
- Seuil global de couverture et contrôles de frontière conservés.
