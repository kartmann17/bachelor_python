# Déploiement de la démonstration

Le projet se déploie comme un monolithe Django sur Scalingo. Gunicorn exécute le
serveur Python. WhiteNoise sert les fichiers statiques collectés pendant la
construction. Le hook du `Procfile` applique les migrations avant l’ouverture
de la nouvelle version aux requêtes. L’extension PostgreSQL fournit
`SCALINGO_POSTGRESQL_URL`.

## Paramètres à renseigner dans l’hébergeur

- `SECRET_KEY` contient une clé aléatoire réservée à l’application.
- `ALLOWED_HOSTS` contient le nom d’hôte public autorisé.
- `CSRF_TRUSTED_ORIGINS` contient l’origine HTTPS publique.
- `DEMO_SPECTATOR_PASSWORD` et `DEMO_STAFF_PASSWORD` contiennent deux mots
  de passe de démonstration distincts pour l’initialisation.

Dans un conteneur ponctuel, exécuter `python manage.py seed_demo --days 60`.
Pour écrire l’état des réservations expirées en base, planifier
`python manage.py expire_reservations`. Le stock et les contrôles tiennent déjà
compte de l’heure limite à chaque requête.

Vérifier la connexion des deux rôles, télécharger un billet, contrôler son statut
et ouvrir Swagger. Inscrire les identifiants de démonstration actifs dans la
copie transmise au jury. L’application de démonstration utilise uniquement des
données fictives.

## Revue de la réservation en ligne

Carte [US-03 Réserver des places en ligne](https://trello.com/c/uTEbH9U8).
Titre de la demande de fusion vers `develop` :
**US-03 Réserver des places en ligne sur le stock partagé**.

Le changement introduit la réservation atomique, une clé d’idempotence,
la génération des billets et la documentation de
`POST /api/reservations/` dans Swagger. Les tests couvrent le refus d’un
stock insuffisant, l’accès au billet et la concurrence entre opérations.

[Guide officiel Django sur Scalingo](https://doc.scalingo.com/languages/python/django/start)

Le dépôt local contient déjà les fusions. Pour ouvrir une vraie demande de
fusion US-03 lors de la première publication sur une forge, initialiser la
branche distante `develop` sur le parent de la branche US-03 avant de publier
l’état intégré. Sur un dépôt distant neuf, depuis le dépôt source :

```sh
git push origin main
git push origin feature/us-03-reservation-en-ligne
git push origin feature/us-03-reservation-en-ligne^:refs/heads/develop
```

Ouvrir la demande de fusion dans la forge de
`feature/us-03-reservation-en-ligne` vers `develop`, avec le descriptif
ci-dessus. L’historique local intégré permet ensuite d’avancer `develop` vers
la version terminée et de publier les autres branches. Cette initialisation
concerne un dépôt distant neuf.
