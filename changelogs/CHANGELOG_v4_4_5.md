# Corep Engine Enterprise v4.4.5 — SA-CCR Final Standard

## Objectif

Finalisation du moteur SA-CCR standard pour les éditions Enterprise et Community.

## Correctifs réglementaires

- Correction du RC margé : `max(CMV - VM - NICA, TH + MTA - NICA, 0)`.
- Ajout du cap Art.274(3) : double calcul `EAD_margined` / `EAD_unmargined` et conservation du minimum.
- Ajout d'une reconnaissance minimale du collatéral Art.276 : exclusion du collatéral/VM/IM non éligible.
- Ajout de buckets FX explicites via `currency_pair`, `pay_currency`, `receive_currency`.
- Ajout d'un référentiel SQL `ref.ref_saccr_supervisory_parameters` pour alpha, multiplier floor, supervisory factors, corrélations et epsilons IRD.

## Traçabilité

`core.core_saccr_results` conserve désormais :

- add-ons par classe : IRD, FX, Credit, Equity, Commodity ;
- EAD margée et EAD non margée cap ;
- RC/PFE margé et non margé ;
- méthode finale retenue ;
- flag `cap_applied` ;
- collatéral éligible / inéligible.

## Tests

- Enterprise : `798 passed, 8 skipped`.
- Community : `114 passed, 1 skipped`.
