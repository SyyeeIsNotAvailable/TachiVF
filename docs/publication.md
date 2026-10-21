# Publication

- Code : branche `main`.
- Catalogue : branche `repo`, mis à jour après compilation et vérification des signatures.
- Secret GitHub : `TACHIVF_SIGNING`, contenant la sauvegarde JSON de signature.
- Sans ce secret, la compilation fonctionne mais ne publie rien.
- Garder une copie privée de la clé : elle sert à toutes les mises à jour.
- Keiyoushi est vérifié toutes les six heures. Les conflits avec nos corrections bloquent la synchronisation.
- Une compilation ou une vérification échouée conserve le dernier catalogue publié.
