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
## Jalons internes et archives de preuves

Les jeux de preuves d'une version publiée sont archivés sous
`releases/evidence/` (fichiers suffixés `_vX_Y_Z`). Les versions **v6.9.0** et
**v6.10.0** sont des jalons internes du cycle de durcissement, consolidés dans
la release **v6.10.1** sans publication autonome : elles n'ont volontairement
pas d'archive dédiée — la continuité des preuves archivées passe de `v6_8_1`
aux jeux `v6_10_1`. Règle : toute version *publiée* archive son jeu de preuves
complet lors de la release suivante ; un jalon interne non publié n'en produit
pas. Le rescellement des preuves de la version courante est industrialisé par
le workflow manuel `.github/workflows/reseal_metrics.yml` (toolchain
verrouillée py3.12, nom du fichier de preuves dérivé de `pyproject.toml`).
