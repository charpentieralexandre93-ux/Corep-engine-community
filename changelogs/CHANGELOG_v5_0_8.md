# Corep Engine Community v5.0.8 — contrat moteur public et profiling

## Évolutions

- ajout de `EngineContext`, `EngineResult` et du `Protocol RegulatoryEngine` ;
- ajout de `FunctionEngineAdapter` pour encapsuler SA et SA-CCR sans changer
  leurs fonctions historiques ;
- ajout de `EngineProfiler` avec mesures durée, volume, débit et statut ;
- export JSON/CSV atomique des profils ;
- ajout de `get_regulatory_engine()` et `run_engine()` au registre public.

## Compatibilité et frontière open-core

- `get_engine("SA")` retourne toujours `run_standard_engine` ;
- `get_engine("SA-CCR")` retourne toujours `run_saccr_engine` ;
- aucun moteur Enterprise, SQL privé ou orchestration multi-moteurs n'est publié ;
- aucun calcul SA, CRM ou SA-CCR n'est modifié.

## Couverture

Le GUI Tkinter est exclu du dénominateur de couverture unitaire, comme le GUI Enterprise ; il reste couvert par les smoke tests et la recette manuelle. Le seuil CI de 64 % est conservé.
