# Processus de release

Versionnage sémantique (`MAJOR.MINOR.PATCH`).

## 1. Préparer la version
Mettre à jour : `src/corep_crr3/__init__.py` (`__version__`), `pyproject.toml`
(`version`), en-têtes `VERSION :`, manifeste, assertion du smoke test, CHANGELOG.

## 2. Vérifier en local
```bash
pip install -e ".[dev]"
pytest -q
ruff check --select=E9,F63,F7,F82 src
```

## 3. Tag signé
```bash
git tag -s v4.3.0 -m "Community v4.3.0"   # signé GPG (recommandé)
# ou, sans clé GPG :
git tag -a v4.3.0 -m "Community v4.3.0"
git push origin v4.3.0
```

## 4. Automatique
Le push du tag déclenche `.github/workflows/release.yml` : build (wheel+sdist),
SBOM CycloneDX, **attestation de provenance** (Sigstore), et création de la
**Release GitHub** avec artefacts et notes générées.

## 5. PyPI (optionnel)
Pour publier sur PyPI, configurer le *Trusted Publishing* (OIDC) côté PyPI puis
ajouter un job `pypa/gh-action-pypi-publish`. Aucun secret à stocker.
