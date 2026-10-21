# TachiVF

Dépôt de développement d’extensions de lecture en français pour Mihon et Tachimanga.

## Premier lot

| Extension | Site | Base de code |
| --- | --- | --- |
| Manga-Scantrad | https://manga-scantrad.io | Keiyoushi, thème Madara |
| MangaKawaii | https://www.mangakawaii.fr | Keiyoushi |
| AnimeSama Scan | https://anime-sama.to | Keiyoushi, scans VF |
| Aniverse | https://aniverse.fr | Keiyoushi |

Seuls les sites entièrement NSFW sont exclus. Aucun filtrage supplémentaire des catégories des sites retenus n’est ajouté.

Mangakagang est exclu de ce lot : le catalogue est public, mais la fiche et le lecteur testés renvoient HTTP 401 sans connexion. Voir [le relevé](docs/mangakagang.json).

## État

Les quatre extensions, leurs icônes, leurs ressources et leurs dépendances locales sont importées. La [première compilation GitHub](https://github.com/SyyeeIsNotAvailable/TachiVF/actions/runs/39603401429) a réussi le 21 octobre 2026 : quatre APK et quatre JAR ont été produits. Les fichiers d’essai sont disponibles dans l’artefact `TachiVF-development` de cette exécution (conservation : 14 jours).

Leur fonctionnement dans Mihon et Tachimanga reste à vérifier sur appareil. Le dépôt de code privé ne constitue pas encore une adresse de dépôt installable dans ces applications.

Le code de lecture est repris sans modification de Keiyoushi à la révision `ff521c17bb3e503c01e658e8fac00b60a95829f3`. Les identifiants de sources et de paquets sont conservés. Les fichiers d’origine et leurs empreintes sont recensés dans [docs/upstream](docs/upstream). Voir [NOTICE](NOTICE) et [LICENSE](LICENSE).

## Organisation

```text
src/fr/                 Les quatre extensions
lib-multisrc/madara/     Moteur partagé utilisé par Manga-Scantrad
lib/i18n/               Traductions du moteur Madara
core/                   Utilitaires partagés Keiyoushi
compiler/               Génération des classes des sources
common/                 Manifeste et règles de compilation communes
gradle/                 Configuration et outils de compilation
scripts/                Commandes du projet
docs/                   État des validations et origine du code
.github/workflows/      Vérification et compilation sur GitHub
```

## Compiler

Installer un JDK récent (la CI utilise Temurin 25) et les outils Android avec la plateforme 37. Renseigner `ANDROID_HOME` ou un fichier `local.properties` local contenant `sdk.dir=...`.

Sous Windows :

```powershell
./scripts/build.ps1
```

Sous Linux/macOS :

```sh
sh scripts/build.sh
```

La commande vérifie les quatre extensions et Madara, puis compile les quatre modules. Les APK sont produits dans `src/fr/<module>/build/outputs/apk/release/`, les JAR dans `src/fr/<module>/build/outputs/jar/release/`.

Sans clé de signature du projet, le système amont utilise une signature de développement. Ces fichiers servent aux essais. Une clé stable sera nécessaire avant une distribution durable. Un APK signé différemment de celui déjà installé ne peut pas le mettre à jour directement.

## Validation

Suivre [docs/validation.md](docs/validation.md). Une compilation réussie ne suffit pas à confirmer la lecture ou la compatibilité iOS. Les détails et chapitres verrouillés d’un site restent soumis à ses accès habituels.

Avant de modifier le code d’une extension, lire [AGENTS.md](AGENTS.md) et [CONTRIBUTING.md](CONTRIBUTING.md), repris de l’amont.
