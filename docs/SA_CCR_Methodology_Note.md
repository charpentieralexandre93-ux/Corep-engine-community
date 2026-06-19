# Note méthodologique — SA-CCR

**Version moteur : 6.2.0**  
**Implémentation :** `src/corep_crr3/saccr_engine.py`

## 1. Périmètre

Le moteur calcule l'exposition de contrepartie des dérivés au niveau du netting set, en distinguant les ensembles margés et non margés et les cinq classes SA-CCR : taux, change, crédit, actions et matières premières.

## 2. Formule centrale

`EAD = α × (RC + PFE)`, avec `α = 1,40`.

- `RC` : coût de remplacement, calculé à partir de la valeur de marché, de la variation margin, du seuil, du MTA et du NICA selon l'état de marge.
- `PFE = multiplier × Σ AddOn_classe`.
- `multiplier` est plafonné à 1 et utilise un plancher de 5 %.
- Le notionnel effectif intègre le delta prudentiel, la supervisory duration et le maturity factor.

| Classe | Agrégation principale |
|---|---|
| Taux | buckets de maturité et corrélations inter-buckets par devise |
| Change | somme absolue par paire de devises, facteur superviseur 4 % |
| Crédit | agrégation systématique/idiosyncratique par entité de référence |
| Actions | séparation single-name / index avec corrélations et facteurs distincts |
| Matières premières | agrégation par hedging set/type |

Références d'implémentation : art. 273–282 CRR, notamment art. 274–275, 277–280.

## 3. Contrôles de marge

Le moteur calcule l'état margé et non margé puis applique le cap réglementaire lorsque nécessaire. Les collatéraux non éligibles sont isolés et ne réduisent pas artificiellement le coût de remplacement.

## 4. Valeurs de référence automatisées

- `tests/test_saccr_v4_4_5_final.py` : RC margé, cap non margé, collatéral inéligible et méthode finale.
- `tests/test_saccr_native.py` : add-ons natifs et agrégations par classe.
- Les tests vérifient notamment `RC = 10`, la conservation d'un RC de `100` avec collatéral inéligible de `80`, et la sélection du cap Art. 274(3).

## 5. Limites de validation

Les facteurs superviseurs et paramètres de marge sont versionnés et doivent être réconciliés avec la population de contrats, les accords de compensation et la taxonomie réglementaire active.
