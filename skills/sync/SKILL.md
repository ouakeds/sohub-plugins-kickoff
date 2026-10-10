---
name: sync
description: Synchronise la documentation d'un projet (cadré avec /kickoff ou rétro-documenté avec /reverse) vers Confluence, sous une page racine « <Projet> ». Un agent mise-en-page lit les documents et l'arborescence cible du plugin (page d'arrivée avec sommaire et démarrage, Vue d'ensemble, Fonctionnel, Architecture découpée en Données, Flux, Interfaces avec une page par contrat exposé, Services externes avec une page par API tierce appelée, Décisions (ADR) pour un projet cadré, Points ouverts et dette, Glossaire), décide du contenu de chaque page et en écrit les corps ; un script vérifie son rendu, résout liens et spécifications, puis des agents publication publient en parallèle et posent le statut natif. Diagrammes Mermaid rendus en PNG (mermaid-cli), joints et insérés en image avec leur source repliée ; chaque spécification est jointe à sa page Contrat (fichier téléchargeable) et reproduite dans un bloc repliable. Le backlog et les stories ne sont pas publiés. Proposé en fin de /validate, ou lancé à la main. À utiliser quand l'utilisateur veut publier ou mettre à jour la documentation sur Confluence.
argument-hint: "[chemin du projet] [--refaire]"
allowed-tools: Agent, AskUserQuestion, Read, Write, Glob, Grep, Bash, Skill
---

Tu publies la documentation d'un projet sur Confluence. Publier sur un outil partagé est un geste volontaire : ne lance ce skill que sur demande de l'utilisateur (directement ou via le choix « Synchroniser sur Confluence » de `/validate`). Tu ne modifies **jamais** les documents du projet ; tu ne supprimes **jamais** de page ni de pièce jointe Confluence.

Tu es l'**orchestrateur** : l'agent **`mise-en-page`** décide du contenu des pages, le script `resoudre.py` fait la mécanique (contrôles, liens, empreintes, lots, fusion), les agents **`publication`** publient en parallèle. Tu es le seul à écrire `confluence.json` (par le script).

Argument reçu : `$ARGUMENTS` (chemin du projet, et `--refaire` pour forcer une nouvelle mise en page ; peut être vide).

- Gabarit de l'arborescence : `${CLAUDE_SKILL_DIR}/../../templates/confluence-arborescence.md`
- Script : `python3 -I ${CLAUDE_SKILL_DIR}/resoudre.py <commande> <projet> …` (désigné ci-dessous par `resoudre.py`)
- Dossier du plugin : `${CLAUDE_SKILL_DIR}/../..`
- Configuration de rendu des diagrammes : `${CLAUDE_SKILL_DIR}/../doctor/puppeteer-config.json`

## Dossier du projet

Pour trouver `<projet>` :
1. si un chemin de projet t'est passé en argument, utilise-le ;
2. sinon, si `docs/prd.md` existe dans le répertoire courant, le projet est le répertoire courant ;
3. sinon, cherche les `*/docs/prd.md` dans les sous-dossiers directs : un seul → c'est le projet ; plusieurs → demande lequel via `AskUserQuestion` ;
4. sinon, aucun projet n'existe : dis-le et propose `/kickoff` (projet neuf) ou `/reverse` (projet existant) ; arrête-toi.

## Accès à Confluence

La synchro passe par le connecteur Atlassian (serveur MCP) de l'utilisateur : `getAccessibleAtlassianResources`, `getConfluenceContent`, `createConfluenceContent`, `updateConfluenceContent`, et via `discover` / `executeRead` / `executeWrite` : `listConfluenceSpaces`, `getConfluenceSpace`, `getConfluenceContentDescendants`, `setConfluenceContentStatus`, `moveConfluenceContent` (le préfixe `mcp__…__` dépend de l'installation ; pour les appels `execute…`, `cloudId` est un argument de premier niveau). S'ils sont différés, charge-les avec `ToolSearch`. S'il n'y a qu'un outil `authenticate`, lance-le et donne le lien à l'utilisateur. Si aucun connecteur Atlassian n'est disponible, dis-le (il faut connecter Atlassian dans Claude) et arrête-toi sans rien modifier.

Avant la première écriture dans un espace, lis-le une fois avec `getConfluenceSpace` et applique ses instructions d'espace s'il en a.

## Arborescence

L'arborescence cible (pages, ordre, parentes, question de chaque page, contenu attendu, règles communes) est décrite dans le **gabarit** ; c'est l'agent `mise-en-page` qui en tire le plan réel du projet (`.sohub-plugin/sync/plan.json`) : une page sans contenu n'est pas créée, `Décisions (ADR)` n'existe que pour un projet cadré. **L'ordre des pages sœurs est celui du plan.** Les titres ne portent pas le nom du projet ; si Confluence refuse un titre déjà pris dans l'espace, ou le renomme d'office (« Titre (2) »), le titre retenu est `<Titre> (<Projet>)` : enregistre-le, il est gardé aux synchros suivantes.

**Jamais synchronisés** : `.sohub-plugin/backlog.md` et `.sohub-plugin/stories/`, `docs/eval/`, `.sohub-plugin/metrics.*`, `.sohub-plugin/reverse/`, et les fichiers de travail de `.sohub-plugin/sync/`.

**Diagrammes** : chaque bloc ```` ```mermaid ```` est rendu en PNG par mermaid-cli (`resoudre.py rendre`, en parallèle, seulement pour les pages à publier et les images manquantes ou périmées), joint à la page et inséré en image à la place de son bloc de code, avec sa source repliée dessous. Un diagramme dont le rendu échoue reste en bloc de code ; le compte rendu donne sa ligne d'erreur et propose de corriger la source. Si `mmdc` manque, propose une fois `/doctor` (sinon les diagrammes restent en code). **Spécifications** : chaque fichier de `docs/contrats/` donne une page Contrat en HTML : le fichier est **joint** (téléchargeable, importable dans Swagger UI, Postman, Insomnia…) et reproduit dans un bloc repliable.

**Envoi des fichiers.** `createConfluenceAttachment` renvoie une commande `curl` qui porte un jeton d'envoi de courte durée ; les agents `publication` l'exécutent telle quelle. Le mode auto de Claude Code refuse ces commandes tant que l'utilisateur ne les a pas autorisées : avant la première publication de fichiers, vérifie que `permissions.allow` de `~/.claude/settings.json` (ou des réglages du projet) contient `Bash(curl --location 'https://<site>/wiki/api/v2/content/*)` (`<site>` = hôte de `confluence.json`). Sinon, donne cette règle à l'utilisateur et demande-lui de l'ajouter (ou de t'y autoriser) ; ne contourne jamais un refus. Sans elle, publie les corps et signale images et fichiers non joints.

## Correspondance : `<projet>/.sohub-plugin/confluence.json`

```json
{
  "cloudId": "<id du site>", "site": "<url du site>", "spaceId": "<id de l'espace>",
  "racine": { "id": "…", "url": "…", "titre": "<Projet>", "statut": "<statut natif publié>", "empreinte": "…" },
  "pages": { "<clé du plan>": { "id": "…", "titre": "<titre publié>", "maj": "…", "statut": "…", "empreinte": "<sha256 du corps publié>", "url": "<url complète>", "format": "markdown | html" } },
  "transformation": { "empreinte": "<empreinte des sources lors de la dernière mise en page>" }
}
```

C'est la seule source de vérité de la correspondance clé ↔ page : une page connue est **mise à jour**, jamais recréée. Les clés d'une ancienne version du plugin (`docs/prd.md`, `docs/architecture.md#flux`, `docs/contrats/<fichier>`…) sont migrées par le script. `empreinte: null` = page créée (squelette) ou publication interrompue : elle sera publiée à la prochaine synchro.

## Statut de page

Le statut est porté par le **statut natif** de la page (étiquette de couleur près du titre), en plus de la ligne « Statut : … » du corps. Le script calcule le statut natif de chaque page (`Brouillon` #FF8B00, `Proposé` #0065FF, `Validé` #36B37E, `Rejeté` / `Remplacé` / `Déprécié` #6B778C ; la racine et le glossaire prennent le statut du cadrage : `Cadrage validé` #36B37E quand PRD, architecture, index des ADR et backlog sont `validé`, sinon `En cadrage` #FF8B00). Si `setConfluenceContentStatus` est refusé (statuts personnalisés désactivés, droits), continue sans statut natif, signale-le une fois et ne réessaie pas.

## Procédure

1. **Projet.** Détermine `<projet>`, lis `confluence.json` s'il existe, obtiens la date-heure (`date '+%Y-%m-%d %H:%M'`). **Reprise** : s'il reste des `.sohub-plugin/sync/resultats-*.json`, lance d'abord `resoudre.py fusionner <projet> <empreinte enregistrée>`.
2. **Première synchro** (pas de `confluence.json`) : récupère les sites accessibles (plusieurs → demande lequel) ; demande via `AskUserQuestion` où publier (URL d'une page parente ou clé d'espace via « Other », espaces accessibles en option) ; écris `confluence.json` avec `cloudId`, `site`, `spaceId`, `"parent": {"spaceId": …, "parentContentId": …}` (emplacement de la racine) et `"pages": {}`. Si la page racine connue n'existe plus, elle sera recréée au même endroit (sinon demande où).
3. **Faut-il refaire la mise en page ?** `resoudre.py sources <projet> <dossier du plugin>` donne l'empreinte des sources (documents, définition de l'agent, gabarit). Identique à `transformation.empreinte`, sans `--refaire`, et `plan.json` + `corps/` présents → passe à l'étape 6 avec les corps existants.
4. **Mise en page.** Invoque l'agent **`mise-en-page`** (description `Mise en page Confluence`), au premier plan, en lui passant : le chemin du projet, celui du gabarit, la liste des documents présents et leur origine (`origine:` du frontmatter), les titres déjà publiés par clé (`confluence.json`, après migration par `resoudre.py squelette`).
5. **Contrôle.** `resoudre.py verifier <projet>`. En cas d'erreurs, relance l'agent **une fois** en lui passant la liste des erreurs à corriger ; si `verifier` échoue encore, arrête la synchro sans rien publier et montre les erreurs.
6. **Squelette et arborescence.**
   - `resoudre.py squelette <projet>` liste les pages du plan dans l'ordre, avec leur id s'il est connu et celui de leur parente, et les pages orphelines.
   - Crée les pages inconnues (corps « Publication en cours. ») par groupe de pages sœurs, dans l'ordre du plan, de haut en bas (racine, enfants de la racine, sous-pages, pages Contrat) ; les groupes indépendants avancent en parallèle. Après chaque création, `resoudre.py enregistrer <projet> <clé> <id> "<titre retenu>" <url complète>`.
   - **Contrôle de l'arborescence** : liste les enfants directs de la racine et de chaque parente du plan (`getConfluenceContentDescendants`, profondeur 1), écris-les dans `.sohub-plugin/sync/enfants.json` (`{"<id parent>": [ids dans l'ordre affiché]}`), puis `resoudre.py ordre <projet> <enfants.json>` donne les déplacements à faire (`moveConfluenceContent`, dans l'ordre donné).
   - Les **orphelines** (pages connues absentes du plan, ex. anciennes pages `Index` ou `Onboarding`) ne sont ni supprimées ni déplacées : signale-les avec leur lien et propose à l'utilisateur de les supprimer lui-même.
7. **Résolution et rendu.** `resoudre.py resoudre <projet> "<date-heure>"` : liens `page:` → URL, `{{spec:…}}` → spécification lue sur le disque, `{{date_synchro}}` → date-heure ; écrit les corps finaux, calcule les empreintes, classe chaque page (`inconnue`, `à publier`, `statut seul`, `inchangée` ; la racine suit dès qu'une autre page est publiée), extrait les diagrammes (`.sohub-plugin/diagrammes/<clé>-<n>.mmd`) et liste les fichiers à joindre. Puis `resoudre.py rendre <projet> <configuration de rendu>` rend les PNG en parallèle.
8. **Publication.** `resoudre.py lots <projet>` écrit jusqu'à 6 fichiers `lot-<n>.json`. Invoque **dans un même message** un agent `publication` par lot (description `Publication — LOT <n>`), au premier plan, avec le chemin de son lot et celui de ses résultats (`.sohub-plugin/sync/resultats-<n>.json`). Pour les pages **à statut seul**, pose le statut natif toi-même (appels en parallèle).
9. **Fusion.** `resoudre.py fusionner <projet> <empreinte des sources>` : met à jour `confluence.json` (et `transformation.empreinte`), supprime lots et résultats. Une page en échec ou **incomplète** (diagramme rendu non inséré, fichier non joint) est relancée une fois, seule, dans un nouveau lot ; un nouvel échec est signalé, et la page garde `empreinte: null` pour être republiée à la synchro suivante.
10. **Compte rendu** : lien de la page racine ; mise en page refaite ou réutilisée (et, si refaite, les 5 lignes de l'agent : identifiants retirés, doublons fusionnés) ; pages créées, mises à jour, inchangées ; diagrammes insérés en image ou restés en code (avec la raison) ; fichiers joints ; déplacements ; statuts natifs posés ou refusés ; pages orphelines ; erreurs (page et message).
