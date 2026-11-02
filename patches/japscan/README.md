# Patchs Japscan

Le code dans `src/fr/japscan` reste synchronisé avec Keiyoushi.
Ajouter les correctifs en fichiers `.patch`, puis leurs noms dans `series`.
Ils sont appliqués avant chaque compilation. Un conflit bloque la publication.

Aucun patch TachiVF pour l'instant : la version Keiyoushi contient déjà des mesures anti-adblock.
Tout correctif publié doit aussi augmenter le `versionCode` de l'extension.
