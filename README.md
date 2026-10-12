<div align="center">

# 🧭 sohub-plugins-spec

**De l'idée au backlog prêt à coder, ou du code existant à une doc Confluence sourcée ligne par ligne.**

*Plugin Claude Code de cadrage de projet : PRD, architecture, ADR, user stories, contrats OpenAPI et publication Confluence, pour que l'IA qui développera n'ait rien à deviner ni à inventer.*

[![Version](https://img.shields.io/badge/version-0.16.0-blue)](.claude-plugin/plugin.json)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-green)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-D97757)](https://docs.claude.com/en/docs/claude-code/plugins)
[![Python 3](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](#-stack--technos)
[![OpenAPI 3.1](https://img.shields.io/badge/OpenAPI-3.1-6BA539?logo=openapiinitiative&logoColor=white)](#-stack--technos)
[![AsyncAPI 3.0](https://img.shields.io/badge/AsyncAPI-3.0-000000?logo=asyncapi&logoColor=white)](#-stack--technos)
[![Confluence](https://img.shields.io/badge/Confluence-sync-0052CC?logo=confluence&logoColor=white)](#-skills)
[![Langue](https://img.shields.io/badge/langue-français-lightgrey)](#)

[Démarrage rapide](#-démarrage-rapide) · [Skills](#-skills) · [Stack](#-stack--technos) · [Documents produits](#-documents-produits) · [Conception](#-conception) · [Scénarios ticket](#-scénarios-create-ticket) · [Licence](#-licence)

</div>

---

## ✨ En bref

Plugin Claude Code de **cadrage de projet**. On part d'une idée (ex. une app Pomodoro) et on écrit tout noir sur blanc — PRD, architecture, ADR, puis backlog de user stories — pour que l'IA qui développera l'application n'ait rien à deviner ni à inventer.

Il documente aussi un **projet existant** par reverse engineering (`/reverse-engineer`) : le code est cartographié avec [Code Review Graph](https://github.com/tirth8205/code-review-graph), trois agents de recherche l'explorent en parallèle (structure, usages, données) et proposent une structure de documentation, puis des agents rédigent en parallèle les mêmes documents (sans ADR : sur un projet existant, les décisions sont déjà prises), chaque affirmation sourcée dans le code.

| | Projet neuf — `/create-project` | Projet existant — `/reverse-engineer` |
|---|---|---|
| **Point de départ** | Une idée, éventuellement des documents (diagrammes, specs, notes) | Un dépôt de code |
| **Méthode** | Boucle questions → choix → rédaction → eval | Graphe du code → 3 explorations parallèles → cartographie → rédaction parallèle |
| **Documents** | PRD, architecture, ADR, glossaire, backlog et stories | PRD, architecture, glossaire (mêmes structures, sans ADR) |
| **Garantie** | Chaque décision répond à un besoin écrit du PRD | Chaque affirmation porte sa preuve `fichier:ligne`, vérifiée par script |
| **Ensuite** | `/create-api-specs` · `/confluence-sync` vers Confluence · `/create-ticket` pour chaque évolution | `/create-api-specs` · `/create-project` pour affiner · `/create-ticket` · `/confluence-sync` vers Confluence |

```mermaid
flowchart LR
    I([💡 Idée]) --> K["/create-project"]
    C([📦 Code existant]) --> R["/reverse-engineer"]
    K <--> E["/review-specs"]
    K --> V["/validate-step"]
    V -->|PRD → archi → ADR → backlog| K
    R --> DR[(docs/ rétro<br/>PRD · architecture<br/>glossaire, sans ADR)]
    V --> D[(docs/<br/>PRD · architecture<br/>ADR · glossaire)]
    D --> O["/create-api-specs"]
    DR --> O
    O --> S["/confluence-sync"]
    D --> S
    DR --> S
    S --> CF([📘 Confluence])
    V --> B[(backlog + stories)]
    D --> T["/create-ticket"]
    DR --> T
    T -->|mise à jour en place| D
    T --> B
    B --> DEV([🤖 IA de dev])
```

## 🚀 Démarrage rapide

Installer depuis GitHub, via la marketplace du dépôt :

```
/plugin marketplace add ouakeds/sohub-plugins-spec
/plugin install sohub-plugins-spec@sohub-plugins-spec-dev
```

Puis, dans Claude Code :

```
/install-deps                        # vérifie et installe les dépendances
/create-project une app Pomodoro     # cadrer un projet neuf
/reverse-engineer ./mon-depot        # documenter un projet existant
```

Pour développer le plugin, voir [Tester en local](#-tester-en-local).

## 🧩 Skills

| Commande | Rôle |
|----------|------|
| `/create-project [idée] [chemins…]` | Une itération de cadrage : questions de l'agent de cadrage → vos choix → rédaction du document courant → eval automatique → relancer / valider / arrêter. Avec des chemins de documents existants (diagrammes, specs, notes — fichiers ou dossiers), le premier lancement rédige directement le PRD à partir d'eux. |
| `/reverse-engineer [dépôt]` | Documente un projet existant. Construit (ou met à jour) le graphe du code avec Code Review Graph, en tire un digest (communautés, flux d'exécution, points d'entrée, dépendances, zones à risque), puis **trois agents de recherche explorent le code en parallèle** (un seul sous 50 fichiers ; Sonnet ; structure et composants ; usages, CU et glossaire ; données, contrats, contraintes et choix techniques ; le digest répartit les fichiers à lire entre eux) et un quatrième (Opus) consolide leurs résultats en une **cartographie**, un index court : identifiants des composants, cas d'utilisation, données, contrats, choix techniques constatés, glossaire, zones d'incertitude ; le détail reste dans les explorations. Après validation de cette structure par vos choix, **deux agents rédigent en parallèle** le PRD d'une part, architecture + glossaire d'autre part (composants en tableau, flux d'intégration, index des contrats), avec **exactement la même structure qu'un projet cadré avec `/create-project`**, en `brouillon`, chaque élément suivi de sa preuve `*(déduit : fichier:ligne)*` ; ce que le code ne dit pas devient question ouverte (10 au plus par document, les autres restent dans la cartographie). **Pas d'ADR ni de décision à trancher** : les décisions sont déjà prises ; les choix techniques constatés sont décrits dans l'architecture (§ 6), sans question sur leur raison. Un ADR ne naît ensuite, avec `/create-project`, que d'une nouvelle décision (changer un choix existant). **Pas d'eval** (les incohérences sont celles du code existant) : un script vérifie que chaque preuve `fichier:ligne` existe. Puis `/create-api-specs` pour les spécifications des API, `/create-project` pour affiner ou `/confluence-sync` pour publier. N'écrase jamais un document existant. |
| `/create-api-specs [projet] [CTR-xx…]` | Produit ou met à jour les spécifications machine des contrats listés au § 5.2 de l'architecture, dans `docs/contrats/` : OpenAPI 3.1 (API HTTP exposée, et chaque API tierce appelée, limitée aux opérations utilisées), AsyncAPI 3.0 (événements, file de messages), JSON Schema (format de fichier). Extraites du code pour un projet existant (preuve `x-source` par opération), conçues d'après le PRD pour un cadrage neuf (`x-besoins`, propositions `x-propose`). Validées par `redocly` / `asyncapi` ; l'index du § 5.2 est mis à jour. Toutes les specs ont une URL de base absolue et des exemples de corps, pour être importées dans Postman telles quelles. |
| `/review-specs [projet]` | Fait relire **les documents de spec** (PRD, architecture, ADR, glossaire, backlog et stories) par l'agent `evaluator`, qui liste tout ce qu'une IA de dev devrait deviner ou inventer : manques, contradictions, exigences invérifiables, traçabilité cassée. Résultat dans `docs/eval/`. Lancé automatiquement à la fin de chaque itération de `/create-project` et de `/create-ticket` ; à la main, il sert à relire de nouveau après une modification. |
| `/confluence-sync [projet] [--refaire]` | Publie la documentation sur Confluence sous une page racine `<Projet>`. **Tout le dossier `docs/` est publié, et lui seul** (sauf `docs/eval/`) : ni le code, ni le backlog, ni aucun fichier hors de `docs/`. Un agent **`layout`** lit ces documents (PRD, architecture, glossaire, ADR, spécifications, et tout autre document de `docs/`) et l'arborescence cible du plugin (`templates/confluence-tree.md`) : page d'arrivée (présentation, sommaire, démarrage en local, variables d'environnement, structure du code, conventions, tests), Vue d'ensemble, Fonctionnel, Architecture découpée en Données, Flux, Interfaces (une page Contrat par spécification, spécification complète dans un bloc repliable) et Services externes, Décisions (ADR) — projet cadré seulement —, Points ouverts et dette, Glossaire. Il décide du contenu de chaque page (sélection, déplacement, fusion des doublons, nettoyage des traces du processus) sans rien inventer ni perdre d'identifiant. Le script `skills/confluence-sync/resolve.py` vérifie son rendu (aucun identifiant métier perdu, ni « § », ni titre numéroté, ni identifiant de processus), résout les liens entre pages et insère les spécifications depuis le disque, calcule les empreintes, prépare les lots et fusionne les résultats. La mise en page n'est refaite que si les sources ont changé (ou avec `--refaire`). Publication en deux temps : squelette des pages nouvelles et remise en ordre de l'arborescence, puis corps publiés **en parallèle** par des agents `publisher` (6 au maximum), avec le statut natif de chaque page. Diagrammes Mermaid rendus en PNG (mermaid-cli, en parallèle) et insérés en image avec leur source repliée ; chaque spécification est jointe à sa page Contrat (fichier téléchargeable). L'envoi des fichiers passe par `resolve.py upload`, qui contrôle chaque commande d'envoi (fichier de `docs/`, adresse du site, options) avant de l'exécuter ; il exige une règle de permission pour cette seule commande (voir `skills/confluence-sync/SKILL.md`). Le backlog et les stories restent dans le dépôt. Proposé à la fin du cadrage (validation du backlog). Nécessite le connecteur Atlassian, et mermaid-cli pour les images. |
| `/install-deps` | Vérifie les dépendances (python3, PyYAML pour relire les specs de contrats, curl, unzip, Node.js, mermaid-cli, son navigateur headless et ses bibliothèques système, linters OpenAPI / AsyncAPI, uv et Code Review Graph, connecteur Atlassian) et installe celles qui manquent, avec votre accord. Proposé par `/confluence-sync` si le rendu des diagrammes est impossible, par `/reverse-engineer` si Code Review Graph manque, et par `/create-api-specs` si le linter manque. |
| `/compare-runs [projets…]` | Compare **plusieurs runs du même cadrage** (ex. `pomodoro-v1`, `pomodoro-v2`, générés à partir de la même idée) sur la qualité (points d'ombre), le temps et le coût, à partir de leurs métriques. Sert à mesurer l'effet d'un changement du plugin. |
| `/validate-step [projet]` | Valide **l'étape de cadrage en cours** : le document courant et passe à l'étape suivante (PRD → architecture → ADR → backlog), puis génère les documents suivants (architecture + ADR + index, puis backlog + stories) avec les propositions de l'agent, marquées *(proposé)* ; ils seront évalués à la fin du `/create-project` suivant. Avertit s'il reste des points bloquants, sans jamais bloquer. |
| `/create-ticket <description \| clé Jira> [chemins…]` | Cadre une **évolution** (feature ou bugfix) sur un projet déjà documenté (cadré avec `/create-project` ou rétro-documenté avec `/reverse-engineer`), en spec-driven. La demande vient d'une description libre ou d'un ticket Jira (lu avec le connecteur Atlassian, sans le modifier). Même boucle que `/create-project` : analyse d'impact par l'agent de cadrage (type feature / bug ; pour un bug, écart à la spec ou cas non spécifié ; documents et identifiants touchés) → vos choix → mise à jour **en place** des documents touchés (PRD, architecture, nouvel ADR si une décision est prise, glossaire) et création des US du ticket au statut `à cadrer` → eval du ticket → relancer / valider le ticket (US `à faire`, ADR `accepté`, ADR remplacé déclassé) / arrêter / abandonner (les documents reviennent à l'instantané pris au début du ticket, evals conservés ; l'abandon est tracé `ABANDON <ID>` et refusé si un autre ticket a écrit depuis). Une US existante touchée par le ticket repasse `à cadrer` jusqu'à la validation. |

## 🛠 Stack / technos

| Domaine | Technologies | Où |
|---|---|---|
| **Plateforme** | [Claude Code](https://docs.claude.com/en/docs/claude-code) — plugin : 9 skills (slash commands), 5 agents, 2 hooks (`SubagentStop`, `Stop`), marketplace | `.claude-plugin/`, `skills/`, `agents/`, `hooks/` |
| **Modèles** | Claude Opus : cadrage (`scoping`), évaluation (`evaluator`), cartographie et rédaction rétro (`researcher`), mise en page Confluence (`layout`) · Claude Sonnet : explorations du code (`researcher`), publication (`publisher`) | `agents/` |
| **Scripts** | Python 3 (bibliothèque standard) | `hooks/metrics.py` (métriques, coûts, comparaison de runs), `skills/reverse-engineer/graph_digest.py` (digest du graphe), `skills/reverse-engineer/check_refs.py` (vérification des preuves `fichier:ligne`), `skills/review-specs/check_tasks.py` (contrôle des plans de tâches), `skills/confluence-sync/resolve.py` (contrôle du rendu, liens, empreintes, lots) |
| **Analyse de code** | [Code Review Graph](https://github.com/tirth8205/code-review-graph) (installé avec `uv`) | `/reverse-engineer` |
| **Contrats** | OpenAPI 3.1, AsyncAPI 3.0, JSON Schema — validés par `redocly` et `asyncapi` | `/create-api-specs` → `docs/contrats/` |
| **Diagrammes** | Mermaid, rendus en PNG par mermaid-cli (Node.js, Chrome headless via puppeteer) | `/confluence-sync` |
| **Publication** | Confluence, via le connecteur Atlassian (MCP) ; pièces jointes envoyées par `curl` à travers `resolve.py upload`, qui contrôle chaque envoi | `/confluence-sync` |
| **Formats lus** | Texte, Markdown, Mermaid, PlantUML, PDF, images | `/create-project [chemins…]` |

## 📂 Documents produits

Chaque projet cadré a son propre dossier, créé par `/create-project` dans le répertoire courant (ex. `pomodoro/`). Le nom du répertoire courant n'est jamais utilisé comme information sur le projet.

Les documents existants passés en argument (sources) sont mémorisés dans le champ `sources:` du PRD : ils restent lus par l'agent de cadrage (analyse, génération de l'architecture et des ADR) et par l'évaluateur. Formats lus : texte, markdown, mermaid, plantuml, PDF, images ; les autres (`.docx`, `.pptx`…) sont signalés et ignorés.

```
<projet>/docs/
  prd.md               # Besoins et exigences
  architecture.md      # Vue d'architecture (composants, données, flux d'intégration, index des contrats…)
  contrats/            # Spécifications des contrats (/create-api-specs) : *.openapi.yaml, *.asyncapi.yaml, *.schema.json
  adr/index.md         # Index des décisions
  adr/NNNN-*.md        # Une décision par fichier
  glossaire.md         # Vocabulaire du projet
  eval/AAAA-MM-JJ-HHMMSS.md  # Une passe d'évaluation par fichier (historique)
<projet>/.sohub-plugin/
  backlog.md           # User stories, priorités, dépendances et statut de dev de chaque US
  stories/US-NNN-*.md  # Une story autonome par fichier : critères d'acceptation, plan de tâches en vagues parallélisables
  tasks.md             # Contrôle mécanique des plans de tâches (check_tasks.py, lancé par l'eval ; tasks-<ID>.md pour un ticket)
  tickets/<ID>/        # Instantané des documents au début d'un ticket (abandon possible), supprimé à la validation
  metrics.jsonl        # Métriques (automatique, source de vérité) : une ligne par intervention
  metrics.md           # Vue lisible des métriques, régénérée à chaque ajout
  reverse/graphe.md    # Projet existant : digest du graphe de code
  reverse/exploration/ # Projet existant : résultats des trois explorations parallèles
  reverse/cartographie.md  # Projet existant : structure de documentation proposée puis validée
  reverse/preuves.md   # Projet existant : vérification des références fichier:ligne
  sync/                # Fichiers de travail de /confluence-sync (corps de page, lots, résultats)
<projet>/.code-review-graph/  # Base du graphe (Code Review Graph, ignoré par git)
```

**Projet existant.** Pour `/reverse-engineer`, le projet est le dépôt de code lui-même : les documents sont écrits dans son `docs/`. Ils portent `origine: rétro` ; le champ `sources:` du PRD cite le dépôt avec sa branche et son commit. Les agents ne relisent pas tout le dépôt ensuite : seulement les fichiers cités par les marqueurs `*(déduit : …)*`, dont `check_refs.py` vérifie l'existence en fin de `/reverse-engineer` (et l'évaluateur par sondage, lors d'un `/create-project`). `docs/adr/index.md` reste vide : les choix constatés sont dans la table « Choix techniques constatés » de l'architecture. Nécessite Code Review Graph (`uv tool install "code-review-graph[communities]"`, ou `/install-deps`).

**Backlog.** Le backlog est généré à la validation des ADR, affiné par `/create-project`, puis validé. Chaque story porte un **plan de tâches** découpé en **vagues** pour préparer un développement parallèle : vague 1 = contrats, puis tests et code en parallèle, dernière vague = intégration ; deux tâches d'une même vague n'écrivent jamais le même fichier. Le backlog regroupe les US en **lots** développables en même temps. Ensuite, les agents de dev suivent ses « Règles de suivi » : une tâche est prenable quand son US est dans le lot courant et que ses dépendances sont `fait` ; l'agent n'écrit que ses « Fichiers écrits » ; quand plusieurs agents travaillent en parallèle, un seul (l'orchestrateur du développement) tient les statuts. Le découpage ne concerne que le nouveau : backlog du cadrage initial et US de `/create-ticket` (`/reverse-engineer` décrit l'existant, sans backlog).

**Évolutions (spec-driven).** Une fois le projet documenté, chaque nouvelle demande passe par `/create-ticket` : la spec est mise à jour avant le code. Il n'y a pas de document de ticket à part : PRD, architecture, ADR et glossaire sont modifiés en place (les statuts `validé` ne changent pas), chaque modification est tracée dans les journaux avec l'identifiant du ticket (clé Jira ou `TK-NNN`, ex. `PROJ-123/B1`), et les US du ticket portent `Ticket : <ID>`. Tant que le ticket n'est pas validé, ses US restent `à cadrer` et l'IA de dev ne les prend pas. Un bug qui viole un EF ou un critère existant ne change pas le PRD : il donne une US `bug` qui cite l'exigence et commence par un test de non-régression ; un bug sur un cas non spécifié ajoute d'abord la règle ou le critère au PRD.

**Pas de fichier d'état** : l'étape courante se déduit du champ `statut` (`brouillon` / `validé`) en tête de `prd.md`, `architecture.md`, `adr/index.md` et `.sohub-plugin/backlog.md`. Le champ `maj` donne la date de dernière rédaction ; il permet de savoir si le dernier eval est à jour.

**Règles communes** aux documents : les identifiants (EF-xx, CU-xx, US-xxx, E-xxx…) ne sont jamais renumérotés ni réutilisés, un point non tranché porte un marqueur `[À CLARIFIER : Q-xx]` à l'endroit concerné en plus de sa question ouverte, une question tranchée est intégrée au document puis retirée, et chaque décision de l'utilisateur est tracée dans un journal des décisions. L'architecture passe trois contrôles de conception (simplicité, anti-abstraction, intégration d'abord) ; tout écart est justifié dans un « Suivi de la complexité ».

### 📊 Métriques

Deux hooks remplissent `<projet>/.sohub-plugin/metrics.jsonl` à partir des transcripts (jamais à partir de ce que disent les agents) :
- `SubagentStop` : une ligne par intervention d'un agent du plugin — acteur, modèle · effort, mode, étape, tâche, début, fin, durée, tours, outils, tokens (entrée, cache écrit, cache lu, sortie), coût d'entrée, coût de sortie, et la qualité (points d'ombre et bloquants du dernier eval) pour les evals ;
- `Stop` : le travail de l'orchestrateur (session principale) pendant le tour, découpé par itération.

`metrics.md` est régénéré à chaque ajout : résumé du run, tableau par itération (durée, coûts, points ouverts), moyennes par acteur, mode et modèle, et le détail des interventions. Les coûts sont estimés aux tarifs de l'API Anthropic (table `PRICES` de `hooks/metrics.py`, à mettre à jour si les tarifs changent).

Pour comparer la qualité, le temps et le coût, génère le même projet dans plusieurs dossiers (ex. `pomodoro-v1`, `pomodoro-v2`), puis lance `/compare-runs pomodoro-v1 pomodoro-v2` (ou `python3 hooks/metrics.py compare …`). Nécessite `python3`.

## 🧠 Conception

> **Principe.** Tout ce qui est attendu doit être écrit noir sur blanc : l'IA qui développera ne doit rien avoir à deviner ni à inventer.

**Échanges.** L'utilisateur ne parle qu'à l'orchestrateur (la commande), jamais directement aux agents. L'orchestrateur invoque l'agent de cadrage, qui précise et challenge la demande, puis lui remonte ses points bloquants, ses zones de flou et ses propositions. L'orchestrateur les traduit pour l'utilisateur, avec des options, et l'utilisateur tranche. Un seul agent de cadrage porte à la fois la casquette de celui qui challenge et de celui qui propose ; un second agent « copilote » reste en réserve si, à l'usage, il mélange trop les deux.

**Agent de cadrage.** C'est un product owner sceptique, qui adopte le point de vue du client et de l'utilisateur final. Il traque les besoins réels, pas les fonctionnalités supposées : tout besoin non justifié est écarté tant qu'il n'a pas prouvé un vrai usage (à qui sert la fonctionnalité, dans quel usage concret). Il pose des questions ciblées et groupées, saute celles dont la réponse est connue, reformule pour vérifier, pointe les contradictions, et n'invente jamais une réponse à la place de l'utilisateur.

**La boucle.**
1. Avec `/create-project`, l'agent cadre la demande, l'utilisateur tranche, et le document de l'étape courante est rédigé ou affiné.
2. L'eval se lance automatiquement en fin d'itération. C'est un regard à part : on produit, puis on audite. L'eval porte sur tous les documents qui existent déjà, et l'absence d'un document attendu est elle-même un point d'ombre.
3. L'utilisateur choisit alors entre trois suites :
   - **relancer** : une nouvelle itération part des points d'ombre du dernier eval ;
   - **valider** (`/validate-step`) : on passe à l'étape suivante, avec un simple avertissement s'il reste des points bloquants ;
   - **arrêter** : les documents restent en l'état, et l'on reprend plus tard.

**Ordre de génération.** On écrit d'abord le PRD, puis l'architecture, puis les ADR, puis le backlog d'US. Chaque décision d'architecture, chaque ADR et chaque US répond à un besoin écrit dans le PRD. Rien n'est jamais bloqué automatiquement : c'est toujours l'humain qui décide quand passer à l'étape suivante.

**Backlog d'US** (inspiré de spec-kit et BMAD) :
- Le découpage est vertical : une US apporte une valeur utilisateur testable de bout en bout. Les US P1 forment le MVP et couvrent tous les EF V1.
- Chaque story contient :
  - son récit ;
  - les besoins PRD, architecture et ADR auxquels elle répond ;
  - ses critères d'acceptation, reliés aux EF ;
  - son plan de tâches : un tableau (ID, tâche, vague, dépendances, fichiers écrits, à lire, CA, « terminé quand », statut, agent), sous-tâches sur un seul niveau, et sa parallélisation (vagues, parallélisme maximal, chemin critique) ;
  - sa définition de terminé.
- Le statut de chaque US vit uniquement dans le tableau du backlog ; celui de chaque tâche, dans le plan de tâches de sa story.
- `skills/review-specs/check_tasks.py` vérifie mécaniquement les plans (dépendances sans cycle et vers des vagues antérieures, fichiers écrits deux fois dans une vague, CA sans tâche, sous-tâches, lots d'US) avant l'évaluateur ; ses anomalies sont bloquantes à l'étape BACKLOG et pour un ticket (contrôle « prêt à paralléliser »).
- À l'étape BACKLOG, l'évaluateur fait le contrôle « prêt à développer ». Sont bloquants : un EF V1 sans US, une US sans besoin, une dépendance cassée.

## 🎫 Scénarios `/create-ticket`

Tous les chemins possibles d'un ticket, tels que les décrit `skills/create-ticket/SKILL.md`. Dans les diagrammes, `TK-001` représente l'identifiant du ticket, qui peut aussi être une clé Jira.

| # | Scénario | Déclencheur | Issue |
|---|----------|-------------|-------|
| 1 | Refus ou avertissement au démarrage | pas de projet, cadrage en cours, ticket validé ou abandonné, demande vide, autre ticket ouvert | arrêt, question ou avertissement |
| 2 | Entrée par Jira | clé `PROJ-123` dans l'argument | demande lue telle quelle, ou texte collé, ou arrêt |
| 3 | Itération nominale (feature, bug écart à la spec, bug cas non spécifié) | description ou ticket Jira | documents mis à jour, US `à cadrer`, eval |
| 4 | Relancer, arrêter, reprendre | choix de fin de tour, puis `/create-ticket TK-001` | nouvelle itération, à partir du dernier eval du ticket |
| 5 | Validation (avec ou sans avertissement) | « Valider le ticket » | US `à faire`, lots, ADR `accepté`, instantané supprimé |
| 6 | Abandon (restauration possible ou non) | « Abandonner le ticket » | documents restaurés (evals conservés, ligne `ABANDON`), ou ticket d'annulation proposé |

**1. Démarrage : refus et avertissements**

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant O as /create-ticket
    participant D as Projet (docs/, .sohub-plugin/)
    U->>O: /create-ticket demande [chemins…]
    O->>D: cherche docs/prd.md (argument, répertoire courant, sous-dossiers directs)
    alt Aucun projet
        O-->>U: propose /create-project ou /reverse-engineer, puis s'arrête
    else Plusieurs projets
        O->>U: lequel ?
    end
    O->>D: lit statut et origine des documents
    opt Cadrage en cours (ni rétro, ni tout validé)
        O-->>U: propose de finir le cadrage avec /create-project, puis s'arrête
    end
    O->>D: identifiant : reprise, clé Jira ou TK-NNN suivant
    alt Ticket déjà validé (VALIDATION TK-001 au journal)
        O-->>U: ticket clos, propose d'en ouvrir un nouveau, puis s'arrête
    else Demande vide
        O->>U: décrire la feature ou le bug, ou donner une clé Jira
    end
    opt Plusieurs demandes sans lien
        O->>U: propose des tickets séparés
    end
    opt Ticket abandonné (ABANDON TK-001 au journal)
        O-->>U: clé Jira : propose de le recommencer. TK-NNN : propose un nouveau ticket
    end
    opt Un autre ticket est ouvert (tickets/TK-000/)
        O->>U: l'abandon par restauration deviendra impossible. Continuer / Arrêter
    end
    O->>D: réserve tickets/TK-001/ (mkdir sans -p, numéro suivant si pris)
    O->>D: instantané docs/, backlog.md, stories/ dans tickets/TK-001/
```

**2. Entrée par un ticket Jira**

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant O as /create-ticket
    participant J as Jira (connecteur Atlassian)
    U->>O: /create-ticket PROJ-123
    O->>U: Lire le ticket Jira PROJ-123 / Ce n'est pas une clé Jira
    alt Ce n'est pas une clé
        Note over O: le texte reste une description, identifiant TK-NNN
    else Clé confirmée
        O->>O: ToolSearch « atlassian jira »
        alt Connecteur absent ou non authentifié
            O->>U: Coller le texte du ticket / Connecter Atlassian / Arrêter
        else Connecteur disponible
            O->>J: cloudId (confluence.json, sinon getAccessibleAtlassianResources)
            O->>J: getJiraIssue PROJ-123
            alt Lecture réussie
                J-->>O: titre, type, description, critères, commentaires
                Note over O: demande = texte Jira recopié tel quel, ticket jamais modifié
            else Échec (introuvable, accès refusé, mauvais site)
                J-->>O: erreur
                O->>U: message d'erreur, puis Coller le texte / Connecter Atlassian / Arrêter
            end
        end
    end
```

**3. Itération nominale : feature ou bug**

```mermaid
sequenceDiagram
    autonumber
    actor U as Utilisateur
    participant O as /create-ticket
    participant S as Agent scoping
    participant D as Projet (docs/, .sohub-plugin/)
    participant R as /review-specs
    O->>S: ANALYSE — TICKET (ticket-rules.md, demande, chemins, sources)
    S-->>O: reformulation, type, qualification, impact, points B / F / C / X
    O->>U: reformulation et impact à confirmer, type feature / bug
    opt Bug
        O->>U: qualification : écart à la spec / cas non spécifié
    end
    O->>U: points bloquants, puis zones de flou (4 questions par appel)
    U-->>O: décisions, ou « non tranché »
    O->>S: RÉDACTION — TICKET (décisions + contenu accepté, impact confirmé)
    alt Feature
        S->>D: PRD (CU, EF, RG, ENF), architecture, ADR « proposé », glossaire
    else Bug, écart à la spec
        S->>D: PRD inchangé, l'US cite l'EF ou le critère violé
    else Bug, cas non spécifié
        S->>D: PRD complété par la RG ou le critère tranché
    end
    S->>D: US du ticket « à cadrer » + stories (Ticket : TK-001)
    S->>D: US existantes « à faire » impactées → « à cadrer »
    Note over S,D: US bug : vague 1 = test de non-régression qui échoue tant que le bug existe
    S-->>O: compte rendu (15 lignes au plus)
    O->>R: projet --ticket TK-001
    R->>D: check_tasks.py --ticket → tasks-TK-001.md
    R->>D: evaluator → docs/eval/horodatage.md (étape TICKET TK-001)
    R-->>O: synthèse : points d'ombre, bloquants du ticket
    O->>U: résumé, puis Relancer / Valider / Arrêter / Abandonner
```

**4. Relancer, arrêter, reprendre**

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant O as /create-ticket
    participant S as Agent scoping
    participant R as /review-specs
    loop Tant que l'utilisateur choisit « Relancer la boucle »
        O->>S: ANALYSE, à partir du dernier eval TICKET TK-001
        S-->>O: points restants
        O->>U: questions
        U-->>O: décisions
        O->>S: RÉDACTION
        O->>R: eval --ticket TK-001
        O->>U: Relancer / Valider / Arrêter / Abandonner
    end
    U-->>O: Arrêter là
    O-->>U: les US restent « à cadrer », reprise avec /create-ticket TK-001
    Note over U,O: plus tard, dans une autre session
    U->>O: /create-ticket TK-001 [réponses]
    O->>O: reprise détectée (tickets/TK-001/ ou lignes TK-001 aux journaux)
    alt Interrompu avant la rédaction, et le message répond aux points
        O->>S: RÉDACTION directement
    else Sinon
        O->>S: ANALYSE à partir du dernier eval TICKET TK-001
    end
```

**5. Validation du ticket**

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant O as /create-ticket
    participant D as Projet (docs/, .sohub-plugin/)
    U-->>O: Valider le ticket
    O->>D: lit le dernier eval TICKET TK-001, tasks-TK-001.md, les marqueurs du ticket
    opt Eval absent ou périmé, bloquants, questions bloquantes, [À CLARIFIER], *(proposé)*, anomalies de tâches
        O->>U: avertissement : Valider quand même / Revenir au cadrage
        opt Revenir au cadrage
            Note over O: retour au choix de fin de tour, rien n'est modifié
        end
    end
    O->>D: backlog : US du ticket et US impactées « à cadrer » → « à faire »
    O->>D: backlog : lots du ticket ajoutés à « Parallélisation des US »
    O->>D: ADR du ticket « proposé » → « accepté », ADR remplacé → « remplacé par »
    O->>D: journaux modifiés : ligne VALIDATION TK-001
    O->>D: check_tasks.py (contrôle des lots ajoutés)
    O->>D: supprime tickets/TK-001/
    O-->>U: lot et tâches de vague 1 prenables, rappel /create-api-specs et /confluence-sync
```

**6. Abandon du ticket**

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant O as /create-ticket
    participant D as Projet (docs/, .sohub-plugin/)
    U-->>O: Abandonner le ticket
    O->>D: instantané présent ? autre dossier tickets/ ? autre ticket aux journaux, absent de l'instantané ?
    alt Instantané absent, autre ticket ouvert, ou autre ticket écrit depuis l'instantané
        O-->>U: restauration impossible. Liste des éléments TK-001, propose un ticket d'annulation
    else Instantané utilisable
        O->>U: ce qui sera perdu (evals conservés). Abandonner et restaurer / Garder le ticket
        alt Abandonner et restaurer
            O->>D: docs/ (sauf docs/eval/), backlog.md, stories/ remplacés par tickets/TK-001/
            O->>D: supprime tasks-TK-001.md et tickets/TK-001/
            O->>D: journal : ligne ABANDON TK-001
            O-->>U: documents revenus à leur état d'avant le ticket
        else Garder le ticket
            Note over O: retour au choix de fin de tour
        end
    end
```

## 🗂 Structure du plugin

```
.claude-plugin/
  plugin.json          # Manifeste du plugin
  marketplace.json     # Marketplace locale pour tester le plugin
skills/create-project/     # Orchestrateur : une itération de la boucle de cadrage
skills/review-specs/       # Passe d'évaluation (lancée aussi en fin d'itération) (+ check_tasks.py)
skills/validate-step/      # Validation de l'étape courante
skills/create-ticket/      # Cadrage d'une évolution (feature, bugfix) sur un projet documenté  (+ ticket-rules.md, règles de l'agent pour un ticket)
skills/confluence-sync/    # Synchronisation des documents vers Confluence (+ resolve.py)
skills/install-deps/       # Diagnostic et installation des dépendances (mermaid-cli, Code Review Graph, linters…)
skills/reverse-engineer/   # Rétro-documentation d'un projet existant (+ graph_digest.py, check_refs.py)
skills/create-api-specs/   # Spécifications OpenAPI / AsyncAPI / JSON Schema des contrats
skills/compare-runs/       # Comparaison de runs (qualité, temps, coût)
agents/scoping.md          # Agent de cadrage : product owner sceptique (analyse, rédaction, proposition)
agents/evaluator.md        # Auditeur : liste les points d'ombre dans docs/eval/
agents/researcher.md       # Agent de recherche : explore, cartographie un projet existant et rédige sa documentation
agents/layout.md           # Agent de mise en page : transforme les documents en pages Confluence selon l'arborescence cible (lancé par /confluence-sync)
agents/publisher.md        # Agent de publication : publie un lot de pages Confluence (lancé en parallèle par /confluence-sync)
templates/                 # Gabarits : prd, architecture, adr, adr-index, glossary, backlog, story, eval, confluence-tree, mapping
hooks/hooks.json           # Hooks SubagentStop et Stop → hooks/metrics.py
hooks/metrics.py           # Métriques : enregistrement (hooks), rendu de metrics.md, comparaison de runs
tests/                     # Tests de non-régression des scripts (bash tests/run.sh)
```

## 🧪 Tester en local

Tests des scripts (Python 3, bibliothèque standard, sans réseau) :

```bash
bash tests/run.sh
```

Lancer Claude Code avec le plugin chargé directement :

```bash
claude --plugin-dir .
```

Ou l'installer via la marketplace locale :

```
/plugin marketplace add ./
/plugin install sohub-plugins-spec@sohub-plugins-spec-dev
```

## 🙏 Inspirations

- [spec-kit](https://github.com/github/spec-kit) — marqueurs de clarification, gates d'architecture, tâches ordonnées tests d'abord avec `[P]`.
- [BMAD](https://github.com/bmad-code-org/BMAD-METHOD) — stories autonomes, suivi de statut, contrôle « prêt à développer ».
- [Code Review Graph](https://github.com/tirth8205/code-review-graph) — graphe du code pour la rétro-documentation.

## 📄 Licence

Distribué sous licence [MIT](LICENSE) — © 2026 Sabri Ouaked.

---

<div align="center">
Fait par <a href="https://github.com/ouakeds">Sabri</a> avec Claude Code.
</div>
