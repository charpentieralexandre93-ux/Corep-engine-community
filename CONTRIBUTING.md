# Contribuer

Merci de votre intérêt ! Cette édition Community est sous licence **Apache-2.0**.

## Démarrage
```bash
git clone <repo> && cd <repo>
pip install -e ".[dev]"
pytest -q
python examples/sa_pure_functions.py     # démo sans base
```

## Flux de contribution
1. Forkez et créez une branche (`feat/...`, `fix/...`).
2. Ajoutez des tests (les fonctions de calcul pures sont testables sans base).
3. Vérifiez : `pytest -q` et `ruff check --select=E9,F63,F7,F82 src`.
4. Commits clairs (style *Conventional Commits* apprécié).
5. Ouvrez une Pull Request en remplissant le gabarit.

## Règles
- Respectez les **citations d'articles réglementaires** (CRR3/CRR2) dans les commentaires.
- Aucune donnée réelle/sensible dans le code ou les tests.
- En contribuant, vous acceptez que votre contribution soit distribuée sous Apache-2.0.
- Voir le [Code de conduite](./CODE_OF_CONDUCT.md).

> Les moteurs avancés (IRB, FRTB, CVA, titrisation, liquidité…) ne font pas
> partie de cette édition publique : les PR les concernant seront refusées ici.
