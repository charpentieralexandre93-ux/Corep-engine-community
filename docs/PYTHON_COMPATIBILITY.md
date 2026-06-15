# Politique de compatibilité Python — v6.0.4

## Contrat d'installation

Le package déclare `requires-python = ">=3.9,<3.14"`.

| Version | Statut | Résolution des dépendances |
|---|---|---|
| Python 3.11 | **Baseline de production reproductible** | lockfiles Linux hashés `requirements-*-py311-linux.lock` |
| Python 3.9 | Compatibilité CI **best-effort** | résolution depuis `pyproject.toml`, sans promesse byte-reproductible |
| Python 3.12 | Compatibilité CI **best-effort** | résolution depuis `pyproject.toml`, sans promesse byte-reproductible |
| Python 3.13 | Compatibilité CI **best-effort** | résolution depuis `pyproject.toml`, sans promesse byte-reproductible |
| Python 3.14+ | Non supporté par cette release | installation bloquée par le metadata package |

La matrice CI exécute les tests fonctionnels sur 3.9, 3.11, 3.12 et 3.13. Les contrôles supply-chain reproductibles (`pip-audit`, SBOM, wheel smoke) utilisent Python 3.11 et les lockfiles hashés.

Cette distinction évite de présenter un environnement non verrouillé comme reproductible. Elle ne change pas les formules réglementaires ni les résultats des moteurs.
