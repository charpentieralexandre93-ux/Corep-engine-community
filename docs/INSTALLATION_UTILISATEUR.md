# Installation utilisateur — COREP Engine Community v6.10.1

Ce guide est destiné à un utilisateur final. Il ne nécessite pas de lancer les tests, la CI, le SBOM ou le build wheel.

## Parcours le plus simple sous Windows

1. Dézipper le projet dans un dossier local, par exemple `C:\corep\community`.
2. Double-cliquer sur `INSTALL_WINDOWS.bat`.
3. Double-cliquer sur `RUN_GUI_WINDOWS.bat`.
4. Dans le GUI, renseigner la connexion PostgreSQL si la base est utilisée.
5. Utiliser les boutons du GUI pour lister ou lancer le bootstrap SQL Community.

## Scripts disponibles

| Script | Rôle |
|---|---|
| `INSTALL_WINDOWS.bat` | Crée `.venv`, installe le projet et prépare les dossiers `logs/` et `output/`. |
| `RUN_GUI_WINDOWS.bat` | Lance le GUI Community. |
| `BOOTSTRAP_SQL_WINDOWS.bat` | Liste ou génère le manifeste SQL Community sans ouvrir le GUI. |
| `launch_community_gui.bat` | Alias historique conservé pour compatibilité. |

## Périmètre Community

Community reste strictement limité au périmètre public :

- `run_sa`
- `run_saccr`

## Commandes équivalentes en terminal

```bat
INSTALL_WINDOWS.bat
RUN_GUI_WINDOWS.bat
BOOTSTRAP_SQL_WINDOWS.bat
```

Pour vérifier uniquement le plan SA :

```bat
.venv\Scripts\python.exe -m corep_crr3.community_bootstrap --engine run_sa --list
```

Pour vérifier uniquement le plan SA-CCR :

```bat
.venv\Scripts\python.exe -m corep_crr3.community_bootstrap --engine run_saccr --list
```
