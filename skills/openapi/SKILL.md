---
name: openapi
description: Produit ou met à jour les spécifications machine des contrats d'un projet dans docs/contrats/ — OpenAPI 3.1 pour une API HTTP exposée ou pour une API tierce appelée par le projet (limitée aux opérations utilisées, importable dans Postman), AsyncAPI 3.0 pour des événements ou une file de messages, JSON Schema pour un format de fichier — à partir de l'index des contrats de l'architecture (§ 5.2) : extraites du code pour un projet existant (/reverse), conçues d'après le PRD et l'architecture pour un cadrage neuf (/kickoff). Valide chaque spécification avec un linter et met à jour l'index. À utiliser quand l'utilisateur veut générer, régénérer ou mettre à jour un contrat OpenAPI / AsyncAPI, ou documenter les API d'un projet, y compris les services externes qu'il appelle.
argument-hint: "[chemin du projet] [CTR-xx…]"
allowed-tools: Agent, AskUserQuestion, Read, Write, Edit, Glob, Grep, Bash, Skill
---

Tu produis les **spécifications des contrats** d'un projet : des fichiers machine, importables dans Swagger UI, Postman ou un générateur de code, qui remplacent toute description d'API en prose. L'architecture n'en garde qu'un index (§ 5.2) ; `/sync` publie chaque spécification sur Confluence (résumé des opérations + fichier joint).

Argument reçu : `$ARGUMENTS` (chemin du projet, puis éventuellement des identifiants `CTR-xx` pour se limiter à ces contrats ; peut être vide).

## Dossier du projet

Comme `/sync` : chemin passé en argument ; sinon le répertoire courant s'il contient `docs/prd.md` ; sinon les `*/docs/prd.md` des sous-dossiers directs (plusieurs → demande lequel via `AskUserQuestion`). Il faut `docs/architecture.md` : s'il manque, dis-le, propose `/kickoff` (projet neuf) ou `/reverse` (projet existant) et arrête-toi.

## Contrats à spécifier

Lis l'index du § 5.2 de l'architecture. Un contrat est à spécifier s'il est **produit par le projet** (API exposée, événements publiés, fichier produit), s'il s'agit d'une file ou d'un bus **interne** au projet, ou d'un **service externe**, c'est-à-dire une API extérieure au projet qu'il appelle (§ 5.1 : SaaS, service d'un fournisseur, autre application de l'organisation, y compris quand l'appel passe par une bibliothèque cliente ou part du navigateur) : un développeur doit pouvoir importer chaque API appelée dans Postman. L'infrastructure (base de données, cache, SMTP… : « Infrastructure requise » du § 11) n'est pas spécifiée. Avec des `CTR-xx` en argument, ne traite que ceux-là.

| Type de contrat | Spécification | Fichier |
|---|---|---|
| API HTTP (REST, JSON) | OpenAPI 3.1 | `docs/contrats/<nom>.openapi.yaml` |
| Événements, messages, file de tâches | AsyncAPI 3.0 | `docs/contrats/<nom>.asyncapi.yaml` |
| Format de fichier échangé (export, import) | JSON Schema 2020-12 | `docs/contrats/<nom>.schema.json` |

`<nom>` = nom du contrat en kebab-case, sans accents (`api-utilisateurs`) ; pour une API tierce, le nom du service (`microsoft-translator`, `elasticsearch`). Une API exposée découpée en plusieurs contrats dans l'index (ex. jetons et utilisateurs) forme **une seule** spécification par API publiée sous un même préfixe et une même authentification : regroupe ses contrats (une étiquette `tags` par contrat) et dis-le dans le compte rendu.

Présente la liste à l'utilisateur (contrat → fichier, création ou mise à jour, contrats ignorés et pourquoi) et demande confirmation via `AskUserQuestion` (« Produire ces spécifications » / « Arrêter »), sauf si des `CTR-xx` ont été passés en argument.

## Contenu d'une spécification

- **En-tête** : `info.title` (nom du contrat, sans le nom du projet), `info.version` (version constatée dans le code ou la configuration, sinon `0.1.0`), `info.description` (un paragraphe : rôle, consommateurs, renvoi au `CTR-xx` et aux `FL-xx` de l'architecture), et les extensions `x-statut` (`brouillon`), `x-maj` (date-heure, `date '+%Y-%m-%d %H:%M'`), `x-origine` (`rétro` ou `cadrage`), `x-sens` (`exposé` pour ce que le projet produit ou une file interne, `consommé` pour une API tierce appelée).
- **OpenAPI** : `servers` (URL de base **absolue** pour qu'un import dans Postman soit utilisable tel quel : l'URL constatée ou prévue ; pour une API exposée sans hôte connu, l'URL locale constatée — port du serveur de développement, du `Dockerfile` ou du `Procfile` — avec des `variables` pour le schéma, l'hôte et le port ; sinon `/` et une question dans `x-questions`), `components.securitySchemes` (Basic, Bearer, clé d'API… tels qu'ils sont), puis chaque opération avec `operationId`, `summary` (une phrase), `tags`, `security`, `parameters`, `requestBody` et `responses` — **toutes** les réponses possibles, erreurs comprises, avec un schéma d'erreur commun dans `components.responses`. Les corps de requête et de réponse référencent des schémas de `components.schemas` (`$ref`), un par représentation, avec types, formats, champs obligatoires, contraintes (longueur, motif, énumérations) et `readOnly` / `writeOnly`. Chaque `requestBody` porte un `example` au niveau du type de média (Postman s'en sert pour pré-remplir le corps), fait de valeurs plausibles et sans secret ; ailleurs, un exemple seulement quand il éclaire un format (date, pagination, liens). Quand l'authentification passe par plusieurs appels (obtenir un jeton, puis l'utiliser), `info.description` donne cet enchaînement en étapes numérotées.
- **AsyncAPI** : `servers` (protocole et hôte : Kafka, AMQP, Redis…), `channels` (nom réel de la file ou du topic), `operations` (`send` / `receive`, avec le composant producteur ou consommateur dans la description) et `components.messages` avec leur `payload` (schéma) et leurs en-têtes.
- **JSON Schema** : `$schema`, `title`, `description`, propriétés typées, `required`, contraintes.
- **Rien d'inventé.** Ce qui n'est ni dans le code (projet existant) ni dans le PRD et l'architecture (cadrage neuf) s'écrit dans la liste `x-questions` de `info` (une question par entrée), jamais comblé par une hypothèse. Pas de valeur de secret, jamais : seulement le nom du mécanisme d'authentification.

### API tierce appelée (`x-sens: consommé`)

La spécification décrit l'API **telle que le projet l'utilise**, pas tout le catalogue du fournisseur :

- `info.description` commence par **à quoi sert le service dans le projet** (deux phrases : ce qu'il apporte, quels cas d'usage en dépendent, ce qui se passe s'il est indisponible ou non configuré), puis le fournisseur et le composant appelant (`CMP-xx`). `info.x-fournisseur` porte le nom du fournisseur. `externalDocs.url` pointe vers la documentation officielle du fournisseur seulement si l'URL est certaine (citée dans le code, la configuration ou un manifeste, ou page de référence officielle connue) ; sinon une entrée de `x-questions`.
- `servers` : l'URL réellement appelée (constante, configuration — avec une `variables` quand elle vient d'une variable d'environnement, sa valeur par défaut constatée en `default`).
- `components.securitySchemes` : le mécanisme tel qu'il est envoyé (en-tête de clé d'API et son nom exact, Bearer, Basic, paramètre de requête…), avec le nom de la variable d'environnement qui porte le secret dans la description, jamais sa valeur. Un en-tête fixe envoyé à chaque appel (région, version) est un paramètre d'en-tête de l'opération, avec sa valeur constatée.
- Une opération par appel **effectivement fait** (rétro) ou **prévu par une exigence** (cadrage) — y compris ceux qu'une bibliothèque cliente fait pour le projet (ex. `es.search(index=…)` → `POST /{index}/_search`) : méthode et chemin réels, paramètres et corps tels qu'ils sont envoyés, réponses traitées par le code. Le schéma de réponse décrit les champs **lus** par le projet et porte `additionalProperties: true` (la réponse réelle en contient d'autres). Les codes d'erreur que le code distingue sont listés ; les autres réponses sont regroupées sous `default`.
- `x-source` sur chaque opération : la ligne du code qui fait l'appel (`app/translate.py:14`). En cadrage neuf, ce qui n'est pas dans la documentation déjà fournie par l'utilisateur est `x-propose: true` ou une question.
- Un appel fait par le **navigateur** (URL construite par le serveur, ex. image d'avatar) est spécifié de la même façon ; la description indique que l'appelant est le navigateur.

### Projet existant (`origine: rétro` dans l'architecture)

Les opérations sont **extraites du code**, pas reconstituées. Pour une API exposée : routes et méthodes HTTP, paramètres de chemin et de requête, corps lus (`request.get_json()`, sérialiseurs, formulaires, DTO…), représentations renvoyées (`to_dict`, sérialiseurs, modèles de réponse), codes d'erreur (gestionnaires d'erreurs, `abort`, exceptions) et authentification (décorateurs, middlewares). Pour une API tierce : appels HTTP (`requests`, `fetch`, `axios`, `HttpClient`…) et appels de la bibliothèque cliente, URL et en-têtes envoyés, champs lus dans la réponse, statuts testés. Pars des fichiers que l'architecture cite pour le contrat (§ 2 et § 5.2) ; lis-les de façon ciblée (`Grep`, puis `Read` sur les lignes utiles). Chaque opération et chaque schéma porte sa preuve dans l'extension `x-source` (`app/api/users.py:10`). Si un framework génère déjà une spécification (FastAPI, springdoc, NestJS Swagger, drf-spectacular…), récupère-la plutôt que de la réécrire (commande ou fichier existant), puis complète seulement ce qui manque, en le signalant.

### Cadrage neuf

Les opérations sont **conçues** à partir des exigences du PRD (EF-xx, RG-xx, ENF-xx) et de l'architecture (entités du § 3, flux du § 4, conventions et format des erreurs des § 8-9). Chaque opération cite les exigences qu'elle sert dans `x-besoins` (`[EF-03, RG-02]`) ; une opération sans exigence n'est pas écrite. Ce qui n'est pas tranché par le PRD ou l'architecture est une proposition, marquée `x-propose: true` sur l'opération ou le schéma concerné (le marqueur est retiré quand l'utilisateur confirme).

### Mise à jour

Une spécification existante n'est pas réécrite en bloc : mets-la à jour (`Edit`) en gardant ce qui n'est pas contredit par le code ou les exigences, ajoute ce qui manque, retire ce qui n'existe plus, et mets `x-maj` à jour. Signale dans le compte rendu les opérations ajoutées, modifiées et retirées.

## Procédure

1. Détermine le projet et la liste des contrats (sections ci-dessus) ; `mkdir -p <projet>/docs/contrats`.
2. **Rédaction.** Une ou deux spécifications : rédige-les toi-même. Au-delà, invoque **dans un même message** un agent `general-purpose` par spécification, au premier plan (description `OpenAPI — <nom>`), en lui passant : le chemin du projet et du dépôt, le contrat (ligne de l'index), le fichier à écrire, le type de spécification, l'origine, la date-heure, et le texte des sections « Contenu d'une spécification » et « Mise à jour » de ce skill ; chacun n'écrit que son fichier.
3. **Validation.** Pour chaque fichier, avec nvm rechargé si `~/.nvm/nvm.sh` existe (`source ~/.nvm/nvm.sh && …`) :
   - OpenAPI : `redocly lint <fichier> --format stylish` (ou `npx --yes @redocly/cli lint …`) ;
   - AsyncAPI : `asyncapi validate <fichier>` (ou `npx --yes @asyncapi/cli validate …`) ;
   - JSON Schema : vérifie au moins qu'il se lit (`python3 -c "import json,sys; json.load(open(sys.argv[1]))" <fichier>`).
   Corrige les **erreurs** et relance, trois passes au plus ; les avertissements de style sont seulement comptés. Si l'outil n'est pas disponible (Node absent, pas de réseau), propose une fois via `AskUserQuestion` « Installer avec /doctor » (→ invoque le skill `sohub-plugins-kickoff:doctor`, puis relance la validation) / « Continuer sans validation » ; vérifie alors au moins que le YAML se lit (`python3 -c "import yaml…"`) et signale les fichiers non validés.
4. **Index.** Dans le § 5.2 de l'architecture, remplace pour chaque contrat traité la cellule « Spécification » par le chemin du fichier (`docs/contrats/<fichier>`), sans toucher au reste ; mets à jour son champ `maj` et ajoute au journal des décisions une ligne `| <date> | OPENAPI | Spécification produite (ou mise à jour) par /openapi | CTR-xx |`. Un fichier de `docs/contrats/` absent de l'index est signalé, pas supprimé.
   **Cohérence du reste du document** : cherche (`Grep` sur « /openapi », « spécification », « À produire ») toute mention d'une spécification manquante pour un contrat désormais spécifié — contrôles de conception (§ 13, gate « Intégration d'abord » : le manque de spécification n'y est plus un écart ; s'il ne reste d'autre écart que l'absence de tests de contrat ou d'intégration, la justification ne cite plus que celle-ci), suivi de la complexité (§ 14 : la ligne ou la partie de ligne sur les contrats sans spécification est retirée), points d'attention des composants (§ 2) — et mets-la à jour avec `Edit`, sans toucher au reste. Liste ces corrections dans le compte rendu.
5. **Compte rendu** : fichiers écrits ou mis à jour, exposés puis consommés (avec le nombre d'opérations, canaux ou propriétés), contrats ignorés et pourquoi, résultat de la validation (erreurs restantes, avertissements), questions `x-questions` relevées (les plus importantes d'abord) et, pour un cadrage neuf, nombre de propositions `x-propose` à confirmer. Puis propose via `AskUserQuestion` « Publier sur Confluence » (→ invoque le skill `sohub-plugins-kickoff:sync` avec le chemin du projet) / « Arrêter là ».

## Règles

- Tu n'écris que dans `docs/contrats/` et, dans `docs/architecture.md`, dans le § 5.2, les mentions de spécification manquante (§ 2, 13, 14), le champ `maj` et le journal. Tu ne modifies jamais le code du dépôt.
- Le code n'est lu qu'en local ; aucun extrait n'est envoyé ailleurs que dans `docs/contrats/` (et sur Confluence seulement si l'utilisateur lance `/sync`).
