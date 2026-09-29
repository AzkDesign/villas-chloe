# Villas de Chloé · Bot Discord

Bot en Python (discord.py) pour le serveur roleplay de la Villa Haussmann et de la Villa Jaurès.

## Fonctionnalités

| Module | Contenu |
|---|---|
| Installation | `/installer` crée ou répare rôles, catégories, salons, permissions et panneaux. Relançable à volonté. |
| Accueil | Message de bienvenue, règlement à valider par bouton (rôle Visiteur), préférences de notifications, hiérarchie mise à jour en direct. |
| Entretiens | Panneau Villa Haussmann / Villa Jaurès / Direction, formulaire, salon privé, décision Accepter (rôles donnés automatiquement) ou Refuser (motif envoyé en MP), archive `.txt` à la fermeture. |
| Modération | Avertissements (sanction auto au 3e), exclusion temporaire, expulsion, bannissement, purge, anti-spam, anti-invitations, anti-raid. |
| Journal | Arrivées, départs, messages supprimés/modifiés, changements de rôles. |
| Niveaux | XP par message, montée de niveau, `/rang`, `/classement`. |
| Économie | Louis d'or : `/solde`, `/quotidien`, `/travailler` (textes selon la villa), `/donner`, `/fortune`, `/crediter`. |
| Communauté | `/annonce`, `/sondage` (sondages natifs Discord), `/giveaway lancer|terminer|relancer`, `/aide`. |

### Rangs et pouvoirs

| Rang | Rôle | Peut… |
|---|---|---|
| 5 | Fondation | tout, dont `/installer` |
| 4 | Responsable | bannir, créditer, verrouiller, décider tous les entretiens |
| 3 | Responsable Haussmann / Jaurès | expulser, annonces, giveaways, décider les entretiens de sa villa |
| 2 | Gérant | avertir, exclure temporairement, purger, sondages |
| 0 | Membre | commandes de niveaux et d'économie |

## 1. Portail développeur Discord

1. <https://discord.com/developers/applications> → votre application → **Bot**.
2. **Reset Token** et copiez le nouveau token (l'ancien a été exposé).
3. Activez **Server Members Intent** et **Message Content Intent**, puis enregistrez.
4. **OAuth2 → URL Generator** : cochez `bot` et `applications.commands`, puis la permission **Administrator**. Ouvrez l'URL générée pour inviter le bot.

## 2. Test en local (facultatif)

```bash
copy .env.example .env
```

Remplissez `DISCORD_TOKEN` et `GUILD_ID` dans `.env`, puis :

```bash
.venv\Scripts\python -m bot.main
```

## 3. GitHub

Créez un dépôt **privé** sur GitHub (par exemple `villas-chloe`), puis dans ce dossier :

```bash
git init
git add .
git commit -m "Bot des villas"
git branch -M main
git remote add origin https://github.com/VOTRE-COMPTE/villas-chloe.git
git push -u origin main
```

Le fichier `.env` est exclu par `.gitignore` : le token ne part jamais sur GitHub.

## 4. Railway

1. **New Project → Deploy from GitHub repo** → `villas-chloe`.
2. **Variables** :
   - `DISCORD_TOKEN` = le token
   - `GUILD_ID` = l'identifiant du serveur
   - `DATA_DIR` = `/data`
3. **Settings → Volumes → Add volume**, point de montage `/data` (sans cela, les niveaux, l'argent et les avertissements sont perdus à chaque redéploiement).
4. Chaque `git push` redéploie automatiquement.

## 5. Dans Discord

1. **Paramètres du serveur → Rôles** : glissez le rôle du bot **tout en haut**.
2. Tapez `/installer` (propriétaire du serveur ou rôle Fondation).
3. Donnez-vous le rôle **Fondation** et attribuez les autres rangs à votre équipe.

## Personnaliser

Tout se règle dans `bot/config.py` : noms et couleurs des rôles, noms des salons, gains d'XP et d'argent, seuils anti-spam et anti-raid. Relancez `/installer` après modification des rôles ou salons.
