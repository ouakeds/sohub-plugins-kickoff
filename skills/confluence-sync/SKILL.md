---
name: confluence-sync
description: Synchronise la documentation d'un projet (cadré avec /create-project ou rétro-documenté avec /reverse) vers Confluence, sous une page racine « <Projet> ». Un agent layout lit les documents et l'arborescence cible du plugin (page d'arrivée avec sommaire et démarrage, Vue d'ensemble, Fonctionnel, Architecture découpée en Données, Flux, Interfaces avec une page par contrat exposé, Services externes avec une page par API tierce appelée, Décisions (ADR) pour un projet cadré, Points ouverts et dette, Glossaire), décide du contenu de chaque page et en écrit les corps ; un script vérifie son rendu, résout liens et spécifications, puis des agents publisher publient en parallèle et posent le statut natif. Diagrammes Mermaid rendus en PNG (mermaid-cli), joints et insérés en image avec leur source repliée ; chaque spécification est jointe à sa page Contrat (fichier téléchargeable) et reproduite dans un bloc repliable. Le backlog et les stories ne sont pas publiés. Proposé en fin de /validate, ou lancé à la main. À utiliser quand l'utilisateur veut publier ou mettre à jour la documentation sur Confluence.
argument-hint: "[chemin du projet] [--refaire]"
allowed-tools: Agent, AskUserQuestion, Read, Write, Glob, Grep, Bash, Skill, ToolSearch, mcp__claude_ai_Atlassian_MCP__getAccessibleAtlassianResources, mcp__claude_ai_Atlassian_MCP__getConfluenceContent, mcp__claude_ai_Atlassian_MCP__createConfluenceContent, mcp__claude_ai_Atlassian_MCP__updateConfluenceContent, mcp__claude_ai_Atlassian_MCP__discover, mcp__claude_ai_Atlassian_MCP__executeRead, mcp__claude_ai_Atlassian_MCP__executeWrite
---

Tu publies la documentation d'un projet sur Confluence. Publier sur un outil partagé est un geste volontaire : ne lance ce skill que sur demande de l'utilisateur (directement ou via le choix « Synchroniser sur Confluence » de `/validate`). Tu ne modifies **jamais** les documents du projet ; tu ne supprimes **jamais** de page ni de pièce jointe Confluence.

Tu es l'**orchestrateur** : l'agent **`layout`** décide du contenu des pages, le script `resolve.py` fait la mécanique (contrôles, liens, empreintes, lots, fusion), les agents **`publisher`** publient en parallèle. Tu es le seul à écrire `confluence.json` (par le script).

Argument reçu : `$ARGUMENTS` (chemin du projet, et `--refaire` pour forcer une nouvelle mise en page ; peut être vide).

- Gabarit de l'arborescence : `${CLAUDE_SKILL_DIR}/../../templates/confluence-tree.md`
- Script : `python3 -I ${CLAUDE_SKILL_DIR}/resolve.py <commande> <projet> …` (désigné ci-dessous par `resolve.py`)
- Dossier du plugin : `${CLAUDE_SKILL_DIR}/../..`
- Configuration de rendu des diagrammes : `${CLAUDE_SKILL_DIR}/../install/puppeteer-config.json`

## Dossier du projet

Pour trouver `<projet>` :
1. si un chemin de projet t'est passé en argument, utilise-le ;
2. sinon, si `docs/prd.md` existe dans le répertoire courant, le projet est le répertoire courant ;
3. sinon, cherche les `*/docs/prd.md` dans les sous-dossiers directs : un seul → c'est le projet ; plusieurs → demande lequel via `AskUserQuestion` ;
4. sinon, aucun projet n'existe : dis-le et propose `/create-project` (projet neuf) ou `/reverse` (projet existant) ; arrête-toi.

## Accès à Confluence

La synchro passe par le connecteur Atlassian (serveur MCP) de l'utilisateur : `getAccessibleAtlassianResources`, `getConfluenceContent`, `createConfluenceContent`, `updateConfluenceContent`, et via `discover` / `executeRead` / `executeWrite` : `listConfluenceSpaces`, `getConfluenceSpace`, `getConfluenceContentDescendants`, `setConfluenceContentStatus`, `moveConfluenceContent` (le préfixe `mcp__…__` dépend de l'installation ; pour les appels `execute…`, `cloudId` est un argument de premier niveau). S'ils sont différés, charge-les avec `ToolSearch`. S'il n'y a qu'un outil `authenticate`, lance-le et donne le lien à l'utilisateur. Si aucun connecteur Atlassian n'est disponible, dis-le (il faut connecter Atlassian dans Claude) et arrête-toi sans rien modifier.

Avant la première écriture dans un espace, lis-le une fois avec `getConfluenceSpace` et applique ses instructions d'espace s'il en a.

## Arborescence

L'arborescence cible (pages, ordre, parentes, question de chaque page, contenu attendu, règles communes) est décrite dans le **gabarit** ; c'est l'agent `layout` qui en tire le plan réel du projet (`.sohub-plugin/sync/plan.json`) : une page sans contenu n'est pas créée, `Décisions (ADR)` n'existe que pour un projet cadré. **L'ordre des pages sœurs est celui du plan.** Les titres ne portent pas le nom du projet ; si Confluence refuse un titre déjà pris dans l'espace, ou le renomme d'office (« Titre (2) »), le titre retenu est `<Titre> (<Projet>)` : enregistre-le, il est gardé aux synchros suivantes.

**Ce qui est publié : tout le dossier `docs/`, et lui seul.** Chaque document de `docs/` (récursif, fichiers cachés exclus) est publié, sauf `docs/eval/` (historique du processus). Rien d'autre n'est lu dans une page ni joint : ni le code, ni `.sohub-plugin/` (backlog, stories, métriques, rétro-documentation, fichiers de travail), ni aucun fichier hors de `docs/`. `resolve.py documents <projet>` donne la liste ; `verifier` refuse un document non publié, une spécification sans page Contrat et tout marqueur `{{spec:…}}` hors de `docs/`.

**Diagrammes** : chaque bloc ```` ```mermaid ```` est rendu en PNG par mermaid-cli (`resolve.py rendre`, en parallèle, seulement pour les pages à publier et les images manquantes ou périmées), joint à la page et inséré en image à la place de son bloc de code, avec sa source repliée dessous. Un diagramme dont le rendu échoue reste en bloc de code ; le compte rendu donne sa ligne d'erreur et propose de corriger la source. Si `mmdc` manque, propose une fois `/install` (sinon les diagrammes restent en code). **Spécifications** : chaque fichier de `docs/contrats/` donne une page Contrat en HTML : le fichier est **joint** (téléchargeable, importable dans Swagger UI, Postman, Insomnia…) et reproduit dans un bloc repliable.

**Envoi des fichiers.** `createConfluenceAttachment` renvoie une commande `curl` qui porte un jeton d'envoi de courte durée. Les agents `publisher` ne l'exécutent jamais eux-mêmes : ils la passent à `resolve.py upload <projet> <fichier> '<commande>'`, qui vérifie le fichier (sous `docs/`, ou PNG d'un diagramme extrait, et cité par un lot), l'adresse (https vers le site de `confluence.json` ou `api.atlassian.com`) et les options (aucune écriture de fichier local, aucun autre fichier envoyé), puis l'exécute. Le mode auto de Claude Code refuse ces commandes tant que l'utilisateur ne les a pas autorisées : avant la première publication de fichiers, vérifie que `permissions.allow` de `~/.claude/settings.json` (ou des réglages du projet) contient `Bash(python3 -I <chemin absolu de resolve.py> upload:*)`. Sinon, donne cette règle à l'utilisateur (avec le chemin réel) et demande-lui de l'ajouter ; ne propose jamais d'autoriser `curl` directement et ne contourne jamais un refus. Sans elle, publie les corps et signale images et fichiers non joints.

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

Le statut est porté par le **statut natif** de la page (étiquette de couleur près du titre), en plus de la ligne « Statut : … » du corps. Le script calcule le statut natif de chaque page (`Brouillon` #FF8B00, `Proposé` #0065FF, `Validé` #36B37E, `Rejeté` / `Remplacé` / `Déprécié` #6B778C ; la racine et le glossaire prennent le statut du cadrage : `Cadrage validé` #36B37E quand PRD, architecture, index des ADR et backlog sont `validé`, sinon `Rétro-documenté` #6554C0 pour un projet rétro-documenté (PRD à `origine: rétro`), `En cadrage` #FF8B00 pour les autres). Si `setConfluenceContentStatus` est refusé (statuts personnalisés désactivés, droits), continue sans statut natif, signale-le une fois et ne réessaie pas : la fusion enregistre `statut_natif_refuse: true` dans `confluence.json`, et dès lors le manifest et les lots portent `statut_natif_refuse: true`, aucune page n'est classée « statut seul » et tu ne poses plus de statut (dis aux agents `publisher` de sauter l'étape du statut natif, `statut_natif` = `non tenté`). Pour réessayer (statuts réactivés), l'utilisateur retire cette clé de `confluence.json`.

## Procédure

1. **Projet.** Détermine `<projet>`, lis `confluence.json` s'il existe, obtiens la date-heure (`date '+%Y-%m-%d %H:%M'`). **Reprise** : s'il reste des `.sohub-plugin/sync/resultats-*.json`, lance d'abord `resolve.py fusionner <projet> <empreinte enregistrée>` (une page « page absente » se traite comme à l'étape 9 : `forget`, puis le squelette la recrée).
2. **Première synchro** (pas de `confluence.json`) : récupère les sites accessibles (plusieurs → demande lequel) ; demande via `AskUserQuestion` où publier (URL d'une page parente ou clé d'espace via « Other », espaces accessibles en option) ; écris `confluence.json` avec `cloudId`, `site`, `spaceId`, `"parent": {"spaceId": …, "parentContentId": …}` (emplacement de la racine) et `"pages": {}`. Si la page racine connue n'existe plus, elle sera recréée au même endroit (sinon demande où).
3. **Faut-il refaire la mise en page ?** `resolve.py sources <projet> <dossier du plugin>` donne l'empreinte des sources (documents, définition de l'agent, gabarit). Identique à `transformation.empreinte`, sans `--refaire`, et `plan.json` + `corps/` présents → passe à l'étape 6 avec les corps existants.
4. **Mise en page.** Invoque l'agent **`layout`** (description `Mise en page Confluence`), au premier plan, en lui passant : le chemin du projet, celui du gabarit, la liste des documents à publier (`resolve.py documents <projet>`) et leur origine (`origine:` du frontmatter), les titres déjà publiés par clé (`confluence.json`, après migration par `resolve.py squelette`).
5. **Contrôle.** `resolve.py verifier <projet>`. En cas d'erreurs, relance l'agent **une fois** en lui passant la liste des erreurs à corriger ; si `verifier` échoue encore, arrête la synchro sans rien publier et montre les erreurs.
6. **Squelette et arborescence.**
   - `resolve.py squelette <projet>` liste les pages du plan dans l'ordre, avec leur id s'il est connu et celui de leur parente, et les pages orphelines.
   - Crée les pages inconnues (corps « Publication en cours. ») par groupe de pages sœurs, dans l'ordre du plan, de haut en bas (racine, enfants de la racine, sous-pages, pages Contrat) ; les groupes indépendants avancent en parallèle. Après chaque création, `resolve.py enregistrer <projet> <clé> <id> "<titre retenu>" <url complète>`.
   - **Contrôle de l'arborescence** : liste les enfants directs de la racine et de chaque parente du plan (`getConfluenceContentDescendants`, profondeur 1), écris-les dans `.sohub-plugin/sync/enfants.json` (`{"<id parent>": [ids dans l'ordre affiché]}`), puis `resolve.py ordre <projet> <enfants.json>` donne les déplacements à faire (`moveConfluenceContent`, dans l'ordre donné).
   - Une page connue que Confluence ne liste plus (supprimée à la main) n'est ni déplacée ni prise comme cible par `ordre` : lance `resolve.py forget <projet> <clé>` puis relance `squelette` pour la recréer (et `enregistrer`).
   - Les **orphelines** (pages connues absentes du plan, ex. anciennes pages `Index` ou `Onboarding`) ne sont ni supprimées ni déplacées : signale-les avec leur lien et propose à l'utilisateur de les supprimer lui-même.
7. **Résolution et rendu.** `resolve.py resoudre <projet> "<date-heure>"` : liens `page:` → URL, `{{spec:…}}` → spécification lue sur le disque, `{{date_synchro}}` → date-heure ; écrit les corps finaux, calcule les empreintes, classe chaque page (`inconnue`, `à publier`, `statut seul`, `inchangée` ; la racine suit dès qu'une autre page est publiée), extrait les diagrammes (`.sohub-plugin/diagrammes/<clé>-<n>.mmd`) et liste les fichiers à joindre. Puis `resolve.py rendre <projet> <configuration de rendu>` rend les PNG en parallèle.
8. **Publication.** `resolve.py lots <projet>` écrit jusqu'à 6 fichiers `lot-<n>.json`. Invoque **dans un même message** un agent `publisher` par lot (description `Publication — LOT <n>`), au premier plan, avec le chemin de son lot, celui de ses résultats (`.sohub-plugin/sync/resultats-<n>.json`) et la commande d'envoi `python3 -I ${CLAUDE_SKILL_DIR}/resolve.py upload <projet>` (chemins absolus). Pour les pages **à statut seul**, pose le statut natif toi-même (appels en parallèle).
9. **Fusion.** `resolve.py fusionner <projet> <empreinte des sources>` : met à jour `confluence.json` (et `transformation.empreinte`), supprime lots et résultats. La liste des pages en échec ou **incomplètes** (diagramme rendu non inséré, fichier non joint) est écrite dans `.sohub-plugin/sync/failed.json` ; `resolve.py lots <projet> --failed` en refait des lots (elles seules), publiés une fois de plus comme à l'étape 8, puis fusionnés de nouveau ; un nouvel échec est signalé, et la page garde `empreinte: null` pour être republiée à la synchro suivante. **Page absente** (résultat `« page absente »` d'un `publisher` : page supprimée à la main dans Confluence) : lance `resolve.py forget <projet> <clé>` (l'id est retiré de `confluence.json`), puis reprends à l'étape 6 : le squelette recrée la page, `resoudre` la classe `inconnue` et elle est publiée (les pages qui la citent suivent, leur lien ayant changé). Une page publiée sans images faute de `mmdc` repasse « à publier » dès que `mmdc` est disponible.
10. **Compte rendu** : lien de la page racine ; mise en page refaite ou réutilisée (et, si refaite, les 5 lignes de l'agent : identifiants retirés, doublons fusionnés) ; pages créées, mises à jour, inchangées ; diagrammes insérés en image ou restés en code (avec la raison) ; fichiers joints ; déplacements ; statuts natifs posés ou refusés ; pages orphelines ; erreurs (page et message).

**Langue** : adresse-toi à l'utilisateur (questions, options, résumés, comptes rendus) dans la langue qu'il emploie.
