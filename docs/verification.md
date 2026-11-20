# Résultats des tests locaux

Les 23 tests passent sur PostgreSQL 16.11 avec Python 3.12 et Django 5.2.
Les trois tests de concurrence ouvrent deux connexions indépendantes. Ils
vérifient deux réservations simultanées, une réservation face à une vente au
guichet et deux contrôles sur le même billet. Dans chaque scénario, une seule
opération est acceptée.

La couverture mesurée sur le package `cinema`, avec mesure des branches et
hors migrations et fichiers de tests, est de **90 %**. Le rapport HTML
détaille les lignes exécutées par module.

Les autres vérifications couvrent notamment la réservation par navigateur,
l’expiration, l’accès aux PDF, la protection CSRF de l’API, la publication
sans chevauchement, la mise à jour de la jauge et le seuil de 90 %.
Ruff et la vérification de cohérence des migrations passent.
