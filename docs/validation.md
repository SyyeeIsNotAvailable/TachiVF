# Validation du premier lot

Les sources sont importées ; aucune validation sur appareil n’a encore été effectuée.

| Contrôle | Manga-Scantrad | MangaKawaii | AnimeSama Scan | Aniverse |
| --- | --- | --- | --- | --- |
| Import des sources et ressources | Vérifié | Vérifié | Vérifié | Vérifié |
| Lint et compilation | CI à exécuter | CI à exécuter | CI à exécuter | CI à exécuter |
| Catalogue et pagination dans l’application | À tester | À tester | À tester | À tester |
| Recherche et fiche | À tester | À tester | À tester | À tester |
| Liste des chapitres | À tester | À tester | À tester | À tester |
| Images et ordre des pages | À tester | À tester | À tester | À tester |
| Mihon Android | À tester | À tester | À tester | À tester |
| Tachimanga iOS | À tester | À tester | À tester | À tester |

Pour chaque source, essayer plusieurs œuvres et au moins un chapitre ancien et un chapitre récent. Contrôler les premières et dernières pages, la pagination du catalogue, une recherche par titre et une recherche par URL. Pour les sites proposant des webtoons, contrôler aussi le défilement vertical.

Aniverse ne propose pas de liste de nouveautés séparée dans son adaptateur actuel. Les chapitres verrouillés sont écartés par le code amont.

Les versions exactes de Mihon, Tachimanga, Android et iOS seront inscrites avec les résultats des essais. Les sondes HTTP conservées dans le dossier de recherche ne remplacent pas ces tests.

Le 21 octobre 2026, Gradle 9.8.1 et les outils de compilation du projet ont été téléchargés et construits localement. Le lancement du lint des quatre extensions et de Madara s’est arrêté avant leur analyse : les composants Android `platforms;android-37.0` et `build-tools;36.0.0` ne sont pas installés et leurs licences ne sont pas acceptées sur ce PC. La CI prépare ces composants sur un environnement séparé.
