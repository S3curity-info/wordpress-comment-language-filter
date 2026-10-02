# Filtre de langue pour les commentaires WordPress

Script Python qui analyse les commentaires WordPress en attente et classe en indésirables ceux détectés dans une langue autre que le français, selon des règles configurables.

La détection de langue fonctionne localement avec Lingua. Aucun plugin WordPress supplémentaire n’est nécessaire.

## Fonctionnement

- Analyse uniquement les commentaires en attente.
- Nettoie le HTML, les balises de liens BBCode et les URL avant analyse.
- Conserve les commentaires français, trop courts ou incertains.
- Classe en indésirables les commentaires étrangers lorsque les seuils sont atteints.
- Classe en indésirables les commentaires composés uniquement de liens.
- Classe en indésirables certains commentaires anglais contenant des liens, même avec un score inférieur au seuil général.
- Permet de bloquer des textes exacts via `blocked_texts`.
- Fonctionne en simulation par défaut.
- Applique le classement uniquement avec `--apply`.
- Permet de cibler certains commentaires avec `--only-ids`.
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

Le rôle standard Éditeur convient, mais donne également des droits sur les articles et les pages. Utiliser un compte dédié.

Dans WordPress, ouvrir le profil du compte dédié et créer un mot de passe dans la section **Mots de passe d’application**.

Le script utilise ce mot de passe d’application, pas le mot de passe habituel de connexion à l’administration.

## Installation

Télécharger le dépôt et ouvrir un terminal dans le dossier du projet.

Créer un environnement Python et installer les dépendances :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Sur Debian, si la création de l’environnement échoue parce que `venv` est absent, installer le paquet correspondant à la version de Python, par exemple `python3.11-venv`.

Préparer la configuration :

```bash
cp config.example.json config.json
chmod 600 config.json
```

Modifier `config.json` pour renseigner :

- `api_url` : URL complète de l’API des commentaires.
- `username` : identifiant du compte WordPress dédié.
- `application_password` : mot de passe d’application WordPress.
- `minimum_score` : score minimal pour la règle générale.
- `minimum_gap` : écart minimal avec la deuxième langue détectée.
- `minimum_letters` : nombre minimal de lettres après nettoyage.
- `blocked_texts` : liste optionnelle de textes exacts à classer en indésirables.

Exemple d’URL :

```text
https://example.com/wp-json/wp/v2/comments
```

Pour WordPress installé dans un sous-dossier `/wp` :

```text
https://example.com/wp/wp-json/wp/v2/comments
```

Le fichier `config.json` contient le secret en clair : conserver des permissions restrictives et ne jamais le publier.

## Exemple de configuration

```json
{
  "api_url": "https://example.com/wp-json/wp/v2/comments",
  "username": "wordpress-bot",
  "application_password": "REMPLACER_PAR_UN_MOT_DE_PASSE_APPLICATION",
  "minimum_score": 0.90,
  "minimum_gap": 0.20,
  "minimum_letters": 40,
  "blocked_texts": [
    "METRYTRH405186MARTHHDF"
  ]
}
```

## Simulation

```bash
.venv/bin/python tri.py
```

Aucun commentaire n’est modifié.

Le journal indique les commentaires qui seraient classés indésirables et ceux qui seraient conservés.

En simulation, le compteur `classés=0` est normal, même si des commentaires sont sélectionnés.

## Classement réel

```bash
.venv/bin/python tri.py --apply
```

Les commentaires sélectionnés passent dans les indésirables.

Le script ne les place pas dans la corbeille et ne les supprime pas définitivement.

## Cibler certains commentaires

Pour tester uniquement certains commentaires précis :

```bash
.venv/bin/python tri.py --only-ids 4694 4696 4717
```

Pour appliquer réellement le classement uniquement sur ces commentaires :

```bash
.venv/bin/python tri.py --apply --only-ids 4694 4696 4717
```

Cette option est pratique pour corriger quelques commentaires restés en attente sans traiter immédiatement tous les nouveaux commentaires.

## Règles de classement

### Longueur minimale

Après nettoyage, le commentaire doit contenir au moins `minimum_letters` lettres pour être analysé par le détecteur de langue.

Sinon, il reste en attente, sauf s’il correspond à une règle prioritaire comme un commentaire contenant un lien ou un texte présent dans `blocked_texts`.

### Règle générale

Le commentaire est sélectionné si toutes ces conditions sont réunies :

- la langue la plus probable n’est pas le français.
- son score atteint `minimum_score`.
- son avance sur la deuxième langue atteint `minimum_gap`.

Paramètres présents dans `config.json` :

| Paramètre | Valeur par défaut | Rôle |
|---|---:|---|
| `minimum_score` | `0.90` | Score minimal de la langue détectée |
| `minimum_gap` | `0.20` | Écart minimal avec la deuxième langue |
| `minimum_letters` | `40` | Nombre minimal de lettres après nettoyage |
| `blocked_texts` | `[]` | Liste de textes exacts à classer automatiquement en indésirables |

### Commentaires composés uniquement de liens

Un commentaire est classé en indésirable s’il contient un ou plusieurs liens et aucun vrai texte en dehors de ces liens.

Sont pris en compte :

- les URL directes ;
- les liens HTML ;
- les liens BBCode du type `[url=https://example.com]texte[/url]`.

Exemple :

```text
[url=https://example.com]boursobank parrainage[/url]
```

Ce commentaire sera considéré comme un commentaire contenant un lien et sera classé en indésirable.

### Règle complémentaire pour l’anglais

Un commentaire suffisamment long peut aussi être sélectionné lorsque toutes ces conditions sont réunies :

- l’anglais est la langue la plus probable.
- le score anglais est supérieur ou égal à `0.55`.
- l’écart avec la deuxième langue est supérieur ou égal à `0.30`.
- le score du français est inférieur ou égal à `0.01`.

Cette règle complète la règle générale : elle peut donc classer un commentaire anglais dont le score est inférieur à `minimum_score`.

### Règle complémentaire pour l’anglais avec lien

Un commentaire anglais contenant un lien peut aussi être sélectionné lorsque toutes ces conditions sont réunies :

- l’anglais est la langue la plus probable.
- le commentaire contient au moins un lien.
- le score anglais est supérieur ou égal à `0.75`.
- l’écart avec la deuxième langue est supérieur ou égal à `0.50`.
- le score du français est inférieur ou égal à `0.05`.

Cette règle permet de traiter des spams anglais avec lien lorsque le score français parasite légèrement la détection.

### Textes bloqués

Le paramètre `blocked_texts` permet de classer automatiquement certains textes exacts.

Exemple :

```json
"blocked_texts": [
  "METRYTRH405186MARTHHDF"
]
```

La comparaison ignore la casse et les espaces multiples, mais le texte doit correspondre au contenu nettoyé du commentaire.

Cette règle est utile pour bloquer des commentaires courts ou incompréhensibles que le détecteur de langue ne peut pas analyser correctement.

## Nettoyage des liens

Les balises de liens BBCode sont retirées avant les URL afin de préserver le texte visible des liens pour l’analyse de langue.

Par exemple :

```text
[url=https://example.com]Texte du commentaire[/url]
```

devient :

```text
Texte du commentaire
```

Cela évite de considérer certains commentaires comme trop courts parce que le nettoyage aurait supprimé leur texte avec le lien.

Le script garde aussi une détection séparée des liens d’origine pour appliquer les règles liées aux commentaires composés uniquement de liens ou aux commentaires anglais avec lien.

## Automatisation

Programmer la commande de classement réel avec le planificateur de la machine, en utilisant des chemins absolus.

Exemple de crontab Linux, chaque jour à 4 h :

```cron
0 4 * * * /chemin/du/projet/.venv/bin/python /chemin/du/projet/tri.py --apply
```

Adapter `/chemin/du/projet` à l’installation.

Le compte qui exécute la tâche doit pouvoir lire `config.json` et écrire les journaux dans le dossier du projet.

### Exemple avec Unraid et User Scripts

Pour une installation dans `/debian/scripts/wordpress-comments`, utiliser ce script dans User Scripts :

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

Le conteneur doit être démarré lors de l’exécution. Activer son démarrage automatique dans Unraid.

Dans User Scripts, choisir une fréquence et enregistrer le réglage.

Exemples de planification personnalisée :

| Expression | Fréquence |
|---|---|
| `0 4 * * *` | Tous les jours à 4 h |
| `0 * * * *` | Toutes les heures, à la minute 0 |

L’horaire dépend du fuseau horaire du serveur.

Conserver le script, la configuration et les journaux dans un dossier persistant du conteneur.

Après une mise à jour de l’image modifiant Python, vérifier l’environnement `.venv` et le recréer si nécessaire.

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
- les règles appliquées.
- pour les textes analysés mais conservés, les trois premières langues, le score français et l’écart entre les deux premières.
- les classements confirmés.
- le bilan final.

Les commentaires trop courts sont signalés sans analyse de langue.

Le journal est limité à environ 1 Mo par fichier, avec trois archives de rotation.

## Dépannage : aucun commentaire récupéré

Si le script affiche `Commentaires récupérés : 0` alors que WordPress contient des commentaires en attente, une réponse ancienne de l’API REST peut être servie par un cache.

Avec LiteSpeed Cache :

1. Ouvrir **LiteSpeed Cache → Cache**.
2. Désactiver **Mettre en cache l’API REST**.
3. Enregistrer les modifications.
4. Ouvrir **LiteSpeed Cache → Boîte à outils → Purger**, puis cliquer sur **Tout purger**.
5. Relancer le script et vérifier le nombre de commentaires récupérés.

Pour un autre système de cache ou CDN, vérifier que les requêtes authentifiées de modération ne sont pas mises en cache.

Ce problème relève de la configuration du site, pas des seuils de détection de langue.

## Dépannage : un commentaire reste en attente

Lancer une simulation :

```bash
.venv/bin/python tri.py
```

Interpréter le résultat :

- `texte court` : longueur inférieure à `minimum_letters` après nettoyage.
- `conservé` avec des scores : les règles de classement ne sont pas remplies.
- `serait indésirable` : le commentaire est sélectionné, mais la simulation ne modifie rien.
- `règle=commentaire contenant un lien` : le commentaire sera classé car il ne contient que des liens.
- `règle=texte bloqué` : le commentaire correspond à un texte présent dans `blocked_texts`.

Pour appliquer réellement le classement :

```bash
.venv/bin/python tri.py --apply
```

Pour appliquer uniquement sur certains commentaires :

```bash
.venv/bin/python tri.py --apply --only-ids 4694 4696 4717
```

Éviter d’abaisser les seuils sans examiner les scores et le contenu.

## Limites

- Ce filtre détecte principalement la langue, pas le caractère indésirable du contenu.
- Un commentaire légitime dans une autre langue peut être classé.
- Les spams français restent en attente, sauf s’ils correspondent à une règle de lien ou à `blocked_texts`.
- Certains commentaires étrangers restent en attente si les critères ne sont pas remplis.
- Les textes courts ou multilingues peuvent être mal identifiés.
- Les règles spécifiques à l’anglais sont plus permissives et peuvent produire des erreurs sur des textes ambigus.
- La relecture avant modification réduit les conflits avec une modération manuelle, sans garantir une opération atomique.
- Une erreur peut interrompre un traitement après plusieurs classements déjà effectués : consulter le journal avant de relancer.

Commencer par une simulation et vérifier régulièrement les indésirables.

## Fichiers à ne pas publier

Ne jamais publier :

- `config.json`
- `tri.log`
- `tri.lock`
- les fichiers `*.bak-*`
- le dossier `.venv`

Publier uniquement le code, la configuration d’exemple, la documentation, la licence et les dépendances.

## Licence

Distribué sous licence MIT. Voir le fichier `LICENSE`.

PhOeNiX — S3curity.info
