# Le Grand Cinéma

Application de réservation de places réalisée en Python pour le Bloc 3.

## Branches

- `main` contient la dernière version intégrée.
- `develop` reçoit la fusion des fonctionnalités.
- `feature/us-xx-sujet` identifie une user story du backlog. Les noms sont en minuscules,
  sans accents et séparés par des tirets. Exemple : `feature/us-03-reservation-en-ligne`.
- `fix/sujet` sert aux correctifs indépendants.

Chaque demande de fusion vise `develop`. Elle doit indiquer la carte Trello,
les changements, les tests et les éventuelles migrations.

## Lancer la démonstration

Sur Mac, ouvre `Demarrer.command` ou lance `./Demarrer.command` dans un terminal.
La première exécution installe les dépendances Python 3.12, applique les migrations
et charge un programme fictif. Ouvre ensuite http://127.0.0.1:8000.

Pour démarrer manuellement sous macOS ou Linux :

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export CINEMA_DEBUG=1
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```



L’identifiant d’équipe réunit les quatre groupes métier pour la démonstration.
L’écran **Espace équipe** ouvre les outils de guichet, de contrôle, de programmation
et de pilotage. Choisir une date future pour tester la vente ou la réservation.
Le contrôle à l’entrée travaille sur les séances du jour.

## Vérifier le projet

```sh
ruff check .
python manage.py makemigrations --check --dry-run
coverage run manage.py test cinema.tests
coverage report
coverage html
```

En mode local, SQLite démarre sans serveur externe. Pour exécuter aussi les tests
parallèles, définir `DATABASE_URL` avec un PostgreSQL de test et un rôle pouvant
créer la base de test. La vérification CI lance tous les tests sur PostgreSQL 16,
puis exporte la couverture en XML.

- [Correspondance entre Trello, les branches et l’application](docs/stories.md)
- [Modèle de données et règles de réservation](docs/modele.md)
- [Préparation du déploiement et de la revue US-03](docs/deploiement.md)
- [Swagger UI](http://127.0.0.1:8000/api/docs) et [OpenAPI JSON](http://127.0.0.1:8000/api/openapi.json)

Les quatre films, leur programmation, les comptes et les images sont des
données de démonstration. Le paiement est encaissé puis enregistré au guichet.
Les salles sont configurées avec une capacité totale de 1 700 places. Chaque
séance définit sa propre jauge de vente, dans la limite de la capacité de sa salle.

