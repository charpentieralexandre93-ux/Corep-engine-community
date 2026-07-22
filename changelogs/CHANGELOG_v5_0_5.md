# Changelog v5.0.5 — Community GUI Control Center

## Objet

Ajout d'un cockpit graphique propre à l'édition Community, strictement limité
aux moteurs publics SA et SA-CCR.

## Évolutions

- vue d'ensemble du périmètre open-core et du contrat SQL public ;
- éditeur `.env` PostgreSQL avec sauvegarde automatique et secret masqué ;
- test de connexion non bloquant ;
- commandes de listing des moteurs, plan SQL, génération du manifeste,
  bootstrap et smoke tests ;
- verrouillage anti-double lancement, progression, arrêt et export des logs ;
- nouveaux points d'entrée `corep-community-gui`,
  `scripts/launch_community_gui.py` et `launch_community_gui.bat` ;
- tests dédiés garantissant l'absence d'import Enterprise.

## Frontière open-core

Le GUI n'importe et n'expose que `SA` et `SA_CCR`. Aucun moteur Enterprise,
aucun orchestrateur propriétaire et aucun fichier SQL privé n'est ajouté.
