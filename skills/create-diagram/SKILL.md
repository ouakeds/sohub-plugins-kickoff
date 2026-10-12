---
name: create-diagram
description: Construit un diagramme Mermaid avec l'utilisateur, à partir de sa demande — choix du type (séquence, processus, états, données, classes, composants, planning, chronologie, carte mentale, parcours), questions sur ce qui manque, aperçu PNG, corrections jusqu'à validation — et l'enregistre dans docs/diagrammes/, publié ensuite par /confluence-sync. Peut aussi reprendre un diagramme existant. À utiliser quand l'utilisateur veut créer, dessiner ou modifier un diagramme ou un schéma.
argument-hint: "<besoin> [chemins de documents ou de diagramme existant…]"
allowed-tools: AskUserQuestion, Skill, Read, Write, Glob, Grep, Bash(date:*), Bash(mkdir:*), Bash(mmdc:*), Bash(command:*)
---

Tu construis un diagramme **avec** l'utilisateur. Il décrit son besoin ; tu choisis avec lui le type de diagramme, tu poses seulement les questions nécessaires, tu dessines, il corrige, jusqu'à ce qu'il valide. **Tu n'inventes rien** : un acteur, une étape, une condition ou un message qu'il n'a pas donné (ni ses documents) est une question, pas une hypothèse.

Argument reçu : `$ARGUMENTS`. Il contient le **besoin** (texte libre, ex. « le parcours de connexion avec double authentification ») et éventuellement des **chemins** : sépare-les du texte et vérifie leur existence avec `Glob`. Un fichier de `docs/diagrammes/` est un **diagramme à reprendre** ; tout autre chemin est une **source** (notes, spec, capture, code…) que tu lis.

## Emplacement

- **Base** : le projet, trouvé comme dans les autres skills — chemin d'un dossier contenant `docs/prd.md` passé en argument, sinon le répertoire courant s'il contient `docs/prd.md`, sinon un seul `*/docs/prd.md` dans les sous-dossiers directs (plusieurs → demande lequel via `AskUserQuestion`). Sans projet, la base est le répertoire courant (rappelle-le à l'utilisateur).
- **Diagramme** : `<base>/docs/diagrammes/<nom>.md` (`<nom>` en kebab-case, tiré du titre). Publié par `/confluence-sync` sur la page « Diagrammes ».
- **Aperçu** : `<base>/.sohub-plugin/diagrammes/<nom>.mmd` et `<nom>.png` (fichiers de travail, jamais publiés).

Format du fichier :

````markdown
---
titre: <titre>
type: <type>
maj: AAAA-MM-JJ HH:MM
---
# <titre>

<une ou deux phrases : ce que montre le diagramme et pour qui>

```mermaid
<diagramme>
```
````

## Contexte

- Les **sources** passées en argument sont toujours lues.
- Les documents du projet (`docs/prd.md`, `docs/architecture.md`, `docs/glossaire.md`, `docs/adr/`) ne sont lus **que si la demande le demande** : elle les cite (« d'après l'architecture », « le flux du CU-03 », « nos composants »), cite un identifiant du projet (CU-xx, EF-xx, CMP-xx, FL-xx, CTR-xx…) ou demande de partir du projet. Alors, reprends leurs noms exacts (termes du glossaire, composants, entités, acteurs) et ne pose que les questions qu'ils laissent ouvertes. Sinon, ne les ouvre pas.

## Types

| Type | Pour montrer | Mermaid |
|------|--------------|---------|
| Séquence | des échanges entre acteurs ou systèmes, dans l'ordre (appel d'API, authentification) | `sequenceDiagram` |
| Processus | des étapes et des décisions (procédure, algorithme, parcours avec choix) | `flowchart` |
| États | le cycle de vie d'un objet (commande, ticket, abonnement) | `stateDiagram-v2` |
| Données | des entités et leurs relations | `erDiagram` |
| Classes | des types, attributs et méthodes | `classDiagram` |
| Composants | le découpage d'un système et ses dépendances | `flowchart` avec `subgraph` |
| Planning | des tâches dans le temps | `gantt` |
| Chronologie | des événements datés | `timeline` |
| Carte mentale | une idée et ses branches | `mindmap` |
| Parcours | le ressenti d'un utilisateur étape par étape | `journey` |

## Déroulé

Chaque question passe par `AskUserQuestion` (4 questions au plus par appel), avec ta recommandation en premier ; termine chaque question par « (ou réponds librement) » : la réponse libre arrive via « Other » et se reprend mot pour mot.

1. **Besoin.** Si la demande est vide, demande ce que le diagramme doit montrer et à qui il sert. **Diagramme à reprendre** : lis-le, résume-le en deux lignes et passe à l'étape 5.
2. **Type.** Propose le ou les types qui conviennent au besoin (2 à 4 options, le plus adapté en premier, avec en description ce qu'il montrera). Si le besoin mélange deux vues (ex. les étapes **et** les échanges entre systèmes), propose de faire deux diagrammes, l'un après l'autre.
3. **Contenu.** Liste ce que le type exige (séquence : participants, messages dans l'ordre, réponses, cas alternatifs ou d'erreur ; processus : début, étapes, décisions et leurs branches, fin ; états : états, transitions et leurs déclencheurs, état initial et final ; données : entités, attributs clés, cardinalités ; etc.), retire ce que la demande, les sources ou les documents lus disent déjà, et pose le reste en **deux appels `AskUserQuestion` au plus** : d'abord le périmètre et les éléments (acteurs, entités, états…), puis le déroulé, les cas alternatifs et le **niveau de détail** (vue d'ensemble ou détaillée). Propose des options concrètes tirées de la demande quand c'est possible.
4. **Brouillon.** Écris le diagramme. Lisibilité d'abord : libellés courts dans la langue de l'utilisateur, 15 éléments environ au plus (au-delà, propose de découper), pas de couleur ni de style sauf demande. Ce qui reste non tranché n'est pas dessiné : signale-le.
5. **Aperçu.** Crée `<base>/.sohub-plugin/diagrammes/` avec `mkdir -p`, écris le diagramme seul dans `<nom>.mmd`, puis rends-le : `mmdc -p ${CLAUDE_SKILL_DIR}/../install-deps/puppeteer-config.json -i <nom>.mmd -o <nom>.png` (chemins absolus). Si le rendu échoue sur la syntaxe, corrige et relance (3 essais au plus) ; s'il échoue encore, montre l'erreur. Si `mmdc` est absent (`command -v mmdc`), dis-le, propose `/install-deps` (→ invoque le skill `sohub-plugins-spec:install-deps`) et continue sans aperçu. Montre à l'utilisateur : le chemin du PNG (à ouvrir), la source Mermaid dans un bloc de code, et en une ou deux lignes ce que tu as dessiné et ce que tu as laissé de côté.
6. **Corrections.** Demande via `AskUserQuestion` : « C'est bon, enregistrer » / « Modifier » (description : « écris tes corrections dans le champ libre ») / « Changer de type » / « Abandonner ». « Modifier » → applique exactement ses corrections (s'il choisit l'option sans texte, redemande-le une fois), puis retour à l'étape 5 ; « Changer de type » → étape 2, en gardant ce qui est déjà tranché ; « Abandonner » → rien n'est écrit dans `docs/`, arrête-toi.
7. **Enregistrement.** Obtiens la date-heure avec `date '+%Y-%m-%d %H:%M'`, crée `<base>/docs/diagrammes/` avec `mkdir -p` et écris le fichier au format ci-dessus. Pour un nouveau diagramme, si `<nom>.md` existe déjà, demande « Remplacer » / « Garder les deux » (suffixe `-2`, `-3`…). Pour un diagramme repris, mets à jour le fichier existant (diagramme, contexte s'il a changé, `maj`). Annonce le chemin, puis rappelle que `/confluence-sync` le publiera sur la page « Diagrammes » et que `/create-diagram <chemin>` permet de le reprendre.

## Règles

- Un diagramme = une vue. Plusieurs besoins sans lien → plusieurs diagrammes, l'un après l'autre.
- Ne modifie aucun autre document du projet : le diagramme vit dans son propre fichier.
- Garde les échanges courts : l'utilisateur doit voir ce qu'on lui demande de trancher.

**Langue** : adresse-toi à l'utilisateur (questions, options, résumés) et écris les libellés du diagramme dans la langue qu'il emploie.
