# Politique de compatibilité Python — v6.6.0

Le package déclare `requires-python = ">=3.11,<3.14"`.

| Version | Niveau de support | Qualification |
|---|---|---|
| Python 3.11 | Baseline de production reproductible | lockfiles hashés, qualité statique, supply-chain, packaging et PostgreSQL E2E |
| Python 3.12 | Support CI best-effort | tests fonctionnels et couverture |
| Python 3.13 | Support CI best-effort | tests fonctionnels et couverture |
| Python 3.10 et antérieures | Non supporté | hors contrat v6.6.0 |

Les contrôles Ruff, Mypy et Bandit sont exécutés une seule fois sous Python 3.11 avec les dépendances verrouillées. La matrice runtime reste limitée aux tests sous Python 3.11, 3.12 et 3.13, ce qui évite les divergences de versions d'outils entre interpréteurs.
