# Note méthodologique — Risque de crédit en approche standard (SA)

**Version moteur : 6.0.4**  
**Implémentation :** `src/corep_crr3/standard_engine.py`

## 1. Périmètre

Le moteur traite les expositions routées en approche standard et exclut explicitement les approches `IRB-F` et `IRB-A`. La séquence calculatoire est : exposition nette, CCF, EAD pré-CRM, protections financées (FCP), protections non financées (UFCP), pondération de risque, facteurs de soutien et exigence de fonds propres.

## 2. Formules contrôlées

| Étape | Formule implémentée | Référence réglementaire utilisée par le moteur |
|---|---|---|
| Exposition nette | `net = max(exposure_amount - provision_amount, 0)` | CRR, valeur exposée au risque |
| Hors bilan | `EAD_pre_CRM = net × CCF` | Art. 111 et annexe I |
| FCP | réduction de l'EAD après décotes de volatilité/change et ajustement de maturité | Art. 223–224 et 239 |
| UFCP | substitution partielle du RW du débiteur par celui du garant sur la part reconnue | Art. 235 et 239 |
| RWA pré-facteurs | `RWA = RWA_substituée + EAD_résiduelle × RW_débiteur` | Approche standard, art. 113–134 |
| Facteurs de soutien | `RWA_final = RWA_pre_SF × multiplicateur` | Art. 501 et 501a |
| Fonds propres | `capital = 8 % × RWA_final` | Art. 92(1)(c) |

Le moteur applique un multiplicateur de mismatch de devise plafonné à 150 % du RW initial et journalise les fallbacks CCF/RW. Le mode strict peut transformer tout fallback de règle en échec bloquant.

## 3. Données et traçabilité

Entrées principales : `stg.stg_exposures`, protections classées, règles CCF/RW, haircuts CRM et règles de supporting factors. Sorties : `core.core_standard_results`, `core.core_protection_allocation`, traces de décisions et de facteurs de soutien.

## 4. Valeurs de référence automatisées

- `tests/test_credit_sa_final_standard_v4_4_9.py` : buckets CCF 100 %, 50 %, 40 %, 20 %, 10 % ; pondérations equity 250 % / 400 %.
- `tests/test_standard_engine_formulas.py` : EAD, CRM, maturité et RWA.
- `tests/test_standard_refactor.py` : parité fonctionnelle de l'orchestrateur refactoré.
- `tests/test_p0_complexity.py` : chaque unité issue du refactoring reste sous CC 20.

## 5. Limites de validation

Les tables de règles et le mapping produit/classe d'actif restent des données réglementaires versionnées à valider pour chaque taxonomie et date d'arrêté. La note décrit l'implémentation ; elle ne remplace pas une opinion juridique ou une validation indépendante du dispositif prudentiel.
