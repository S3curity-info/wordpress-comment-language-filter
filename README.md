# Filtre de langue pour les commentaires WordPress

Script Python qui analyse les commentaires WordPress en attente
et classe en indésirables ceux détectés dans une langue autre
que le français, selon des seuils configurables.

La détection de langue fonctionne localement avec Lingua.
Aucun plugin WordPress supplémentaire n’est nécessaire.

## Fonctionnement

- Analyse uniquement les commentaires en attente
- Conserve les commentaires français, trop courts ou incertains
- Fonctionne en simulation par défaut
- Applique le classement uniquement avec `--apply`
- Relit chaque commentaire sélectionné avant de le modifier
- Ne supprime définitivement aucun commentaire
- Enregistre les actions dans `tri.log`, avec rotation des journaux
- Empêche deux exécutions simultanées utilisant le même dossier

## Prérequis

- Linux ou un conteneur Linux : le script utilise `fcntl`
- Python 3.11, version utilisée pour cette installation
- Un site WordPress accessible en HTTPS
- Un compte WordPress autorisé à modérer les commentaires
- Un mot de passe d’application associé à ce compte

Le rôle standard Éditeur convient, mais donne également des droits
sur les articles et les pages. Utiliser un compte dédié.

## Installation

Dans le dossier du projet :

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

- `api_url` : URL complète de l’API des commentaires
- `username` : identifiant du compte WordPress dédié
- `application_password` : mot de passe d’application WordPress

Ne jamais publier `config.json`.

## Simulation

```bash
.venv/bin/python tri.py
```

Aucun commentaire n’est modifié.

## Classement réel

```bash
.venv/bin/python tri.py --apply
```

Les commentaires sélectionnés passent dans les indésirables.

## Réglages

| Paramètre | Valeur par défaut | Rôle |
|---|---:|---|
| minimum_score | 0.90 | Score minimal de la langue détectée |
| minimum_gap | 0.20 | Écart minimal avec la deuxième langue |
| minimum_letters | 40 | Nombre minimal de lettres après nettoyage |

Un score de 0.90 ne garantit pas une fiabilité de 90 %.
Abaisser les seuils rend le filtre plus permissif et peut augmenter
les erreurs de classement.

## Automatisation

Programmer la commande de classement réel avec le planificateur
de la machine, en utilisant des chemins absolus.

Exemple de crontab Linux, chaque jour à 4 h :

```cron
0 4 * * * /chemin/du/projet/.venv/bin/python /chemin/du/projet/tri.py --apply
```

Le compte qui exécute la tâche doit pouvoir lire `config.json`
et écrire les journaux dans le dossier du projet.

Sur Unraid, User Scripts peut lancer cette commande dans un
conteneur existant avec `docker exec`.

## Limites

- Ce filtre détecte la langue, pas le caractère indésirable du contenu.
- Un commentaire légitime dans une autre langue peut être classé.
- Les spams français restent en attente.
- Les textes courts ou multilingues peuvent être mal identifiés.
- La relecture avant modification réduit les conflits avec une
  modération manuelle, sans garantir une opération atomique.
- Une erreur peut interrompre un traitement après plusieurs
  classements déjà effectués : consulter le journal avant de relancer

Commencer par une simulation et vérifier régulièrement les indésirables.

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