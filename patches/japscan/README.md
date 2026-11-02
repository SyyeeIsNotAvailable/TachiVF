# Patchs Japscan

Le code dans `src/fr/japscan` reste synchronisé avec Keiyoushi.
Ajouter les correctifs en fichiers `.patch`, puis leurs noms dans `series`.
Ils sont appliqués avant chaque compilation. Un conflit bloque la publication.

`0001-reader-session.patch` : lecteur dans la session WebView, sans rechargements HTTP pendant le captcha du site ; injection des hooks avant les scripts de la page.
`0002-lazy-pages.patch` : ouverture rapide des mangas paginés, puis capture et cache par lots de quatre pages. Sans attente du chargement complet du chapitre.
Version locale : version Keiyoushi + 2. Validation sur appareils en cours.
