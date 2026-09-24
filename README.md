# Filtre de langue pour les commentaires WordPress

Script Python qui analyse les commentaires WordPress en attente
et classe en indésirables ceux détectés dans une langue autre
que le français, selon des règles configurables.

La détection de langue fonctionne localement avec Lingua.
Aucun plugin WordPress supplémentaire n’est nécessaire.

## Fonctionnement

- Analyse uniquement les commentaires en attente.
- Nettoie le HTML, les balises de liens BBCode et les URL avant analyse.
- Conserve les commentaires français, trop courts ou incertains.
- Fonctionne en simulation par défaut.
- Applique le classement uniquement avec `--apply`.
- Relit chaque commentaire sélectionné avant de le modifier.
- Ne supprime définitivement aucun commentaire.
- Enregistre les actions dans `tri.log`, avec rotation des journaux.
- Empêche deux exécutions simultanées utilisant le même dossier.

## Prérequis

- Linux ou un conteneur Linux : le script utilise `fcntl`.
- Python 3.11, version utilisée pour cette installation.
- Un site WordPress accessible en HTTPS.
- Un compte WordPress autorisé à modérer les commentaires.
- Un mot de passe d’application associé à ce compte.

Le rôle standard Éditeur convient, mais donne également des droits
sur les articles et les pages. Utiliser un compte dédié.

Dans WordPress, ouvrir le profil du compte dédié et créer un mot
de passe dans la section **Mots de passe d’application**.

Le script utilise ce mot de passe d’application, pas le mot de passe
habituel de connexion à l’administration.

## Installation

Télécharger le dépôt et ouvrir un terminal dans le dossier du projet.

Créer un environnement Python et installer les dépendances :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Sur Debian, si la création de l’environnement échoue parce que
`venv` est absent, installer le paquet correspondant à la version
de Python, par exemple `python3.11-venv`.

Préparer la configuration :

```bash
cp config.example.json config.json
chmod 600 config.json
```

Modifier `config.json` pour renseigner :

- `api_url` : URL complète de l’API des commentaires.
- `username` : identifiant du compte WordPress dédié.
- `application_password` : mot de passe d’application WordPress.

Exemple d’URL :

```text
https://example.com/wp-json/wp/v2/comments
```

Pour WordPress installé dans un sous-dossier `/wp` :

```text
https://example.com/wp/wp-json/wp/v2/comments
```

Le fichier `config.json` contient le secret en clair :
conserver des permissions restrictives et ne jamais le publier.

## Simulation

```bash
.venv/bin/python tri.py
```

Aucun commentaire n’est modifié.

Le journal indique les commentaires qui seraient classés
indésirables et ceux qui seraient conservés.

En simulation, le compteur `classés=0` est normal, même si des
commentaires sont sélectionnés.

## Classement réel

```bash
.venv/bin/python tri.py --apply
```

Les commentaires sélectionnés passent dans les indésirables.

Le script ne les place pas dans la corbeille et ne les supprime
pas définitivement.

## Règles de classement

### Longueur minimale

Après nettoyage, le commentaire doit contenir au moins
`minimum_letters` lettres pour être analysé.

Sinon, il reste en attente.

### Règle générale

Le commentaire est sélectionné si toutes ces conditions sont réunies :

- la langue la plus probable n’est pas le français.
- son score atteint `minimum_score`.
- son avance sur la deuxième langue atteint `minimum_gap`.

Paramètres présents dans `config.json` :

| Paramètre | Valeur de l’exemple | Rôle |
|---|---:|---|
| minimum_score | 0.90 | Score minimal de la langue détectée |
| minimum_gap | 0.20 | Écart minimal avec la deuxième langue |
| minimum_letters | 40 | Nombre minimal de lettres après nettoyage |

### Règle complémentaire pour l’anglais

Un commentaire suffisamment long peut aussi être sélectionné
lorsque toutes ces conditions sont réunies :

- l’anglais est la langue la plus probable.
- le score anglais est supérieur ou égal à `0.55`.
- l’écart avec la deuxième langue est supérieur ou égal à `0.30`.
- le score du français est inférieur ou égal à `0.01`.

Ces quatre conditions sont actuellement définies directement
dans `tri.py`. Elles ne sont pas configurables dans `config.json`.

Cette règle complète la règle générale : elle peut donc classer
un commentaire anglais dont le score est inférieur à `minimum_score`.

Les scores du détecteur ne constituent pas une garantie de fiabilité.
Cette règle plus permissive peut produire des erreurs, notamment
sur les textes multilingues. Vérifier les résultats en simulation.

## Nettoyage des liens

Les balises de liens BBCode sont retirées avant les URL afin de
préserver le texte visible des liens.

Par exemple :

```text
[url=https://example.com]Texte du commentaire[/url]
```

devient :

```text
Texte du commentaire
```

Cela évite de considérer certains commentaires comme trop courts
parce que le nettoyage aurait supprimé leur texte avec le lien.

## Automatisation

Programmer la commande de classement réel avec le planificateur
de la machine, en utilisant des chemins absolus.

Exemple de crontab Linux, chaque jour à 4 h :

```cron
0 4 * * * /chemin/du/projet/.venv/bin/python /chemin/du/projet/tri.py --apply
```

Adapter `/chemin/du/projet` à l’installation.

Le compte qui exécute la tâche doit pouvoir lire `config.json`
et écrire les journaux dans le dossier du projet.

### Exemple avec Unraid et User Scripts

Pour une installation dans `/debian/scripts/wordpress-comments`,
utiliser ce script dans User Scripts :

```bash
#!/bin/bash

CONTAINER="NOM_DU_CONTENEUR"

/usr/bin/docker exec --user 0 "$CONTAINER" \
    /debian/scripts/wordpress-comments/.venv/bin/python \
    /debian/scripts/wordpress-comments/tri.py --apply

RESULT=$?

if [ "$RESULT" -ne 0 ]; then
    echo "ERREUR : traitement échoué. Vérifier le conteneur et les journaux."
    exit "$RESULT"
fi

echo "OK : traitement WordPress terminé."
```

Remplacer `NOM_DU_CONTENEUR` par le nom exact du conteneur.

Le conteneur doit être démarré lors de l’exécution.
Activer son démarrage automatique dans Unraid.

Dans User Scripts, choisir une fréquence et enregistrer le réglage.
Exemples de planification personnalisée :

| Expression | Fréquence |
|---|---|
| `0 4 * * *` | Tous les jours à 4 h |
| `0 * * * *` | Toutes les heures, à la minute 0 |

L’horaire dépend du fuseau horaire du serveur.

Conserver le script, la configuration et les journaux dans un
dossier persistant du conteneur.

Après une mise à jour de l’image modifiant Python, vérifier
l’environnement `.venv` et le recréer si nécessaire.

## Journaux

Le fichier `tri.log` se trouve à côté de `tri.py`.

Consulter les dernières lignes :

```bash
tail -n 30 tri.log
```

Le journal indique :

- le mode : simulation ou réel.
- le nombre de commentaires récupérés.
- les décisions et les scores.
- pour les textes analysés mais conservés, les trois premières
  langues, le score français et l’écart entre les deux premières.
- les classements confirmés.
- le bilan final.

Les commentaires trop courts sont signalés sans analyse de langue.

Le journal est limité à environ 1 Mo par fichier, avec trois
archives de rotation.

## Dépannage : aucun commentaire récupéré

Si le script affiche `Commentaires récupérés : 0` alors que
WordPress contient des commentaires en attente, une réponse
ancienne de l’API REST peut être servie par un cache.

Avec LiteSpeed Cache :

1. Ouvrir **LiteSpeed Cache → Cache**.
2. Désactiver **Mettre en cache l’API REST**.
3. Enregistrer les modifications.
4. Ouvrir **LiteSpeed Cache → Boîte à outils → Purger**,
   puis cliquer sur **Tout purger**.
5. Relancer le script et vérifier le nombre de commentaires récupérés.

Pour un autre système de cache ou CDN, vérifier que les requêtes
authentifiées de modération ne sont pas mises en cache.

Ce problème relève de la configuration du site, pas des seuils
de détection de langue.

## Dépannage : un commentaire reste en attente

Lancer une simulation :

```bash
.venv/bin/python tri.py
```

Interpréter le résultat :

- `texte court` : longueur inférieure à `minimum_letters` après nettoyage.
- `conservé` avec des scores : les règles de classement ne sont pas remplies.
- `serait indésirable` : le commentaire est sélectionné, mais la simulation
  ne modifie rien.

Pour appliquer réellement le classement :

```bash
.venv/bin/python tri.py --apply
```

Éviter d’abaisser les seuils sans examiner les scores et le contenu.

## Limites

- Ce filtre détecte la langue, pas le caractère indésirable du contenu.
- Un commentaire légitime dans une autre langue peut être classé.
- Les spams français restent en attente.
- Certains commentaires étrangers restent en attente si les critères
  ne sont pas remplis.
- Les textes courts ou multilingues peuvent être mal identifiés.
- La relecture avant modification réduit les conflits avec une
  modération manuelle, sans garantir une opération atomique.
- Une erreur peut interrompre un traitement après plusieurs
  classements déjà effectués : consulter le journal avant de relancer.

Commencer par une simulation et vérifier régulièrement les indésirables.

## Licence

Distribué sous licence MIT. Voir le fichier `LICENSE`.

PhOeNiX — S3curity.info