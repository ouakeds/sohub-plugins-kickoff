# sohub-plugins-kickoff

Plugin Claude Code de **cadrage de projet**. On part d'une idée (ex. une app Pomodoro) et on écrit tout noir sur blanc — PRD, architecture, ADR, puis backlog de user stories — pour que l'IA qui développera l'application n'ait rien à deviner ni à inventer.

Il documente aussi un **projet existant** par reverse engineering (`/reverse`) : le code est cartographié avec [Code Review Graph](https://github.com/tirth8205/code-review-graph), trois agents de recherche l'explorent en parallèle (structure, usages, données) et proposent une structure de documentation, puis des agents rédigent en parallèle les mêmes documents (sans ADR : sur un projet existant, les décisions sont déjà prises), chaque affirmation sourcée dans le code.

## Skills

| Commande | Rôle |
|----------|------|
| `/kickoff [idée] [chemins…]` | Une itération de cadrage : questions de l'agent de cadrage → vos choix → rédaction du document courant → eval automatique → relancer / valider / arrêter. Avec des chemins de documents existants (diagrammes, specs, notes — fichiers ou dossiers), le premier lancement rédige directement le PRD à partir d'eux. |
| `/reverse [dépôt]` | Documente un projet existant. Construit (ou met à jour) le graphe du code avec Code Review Graph, en tire un digest (communautés, flux d'exécution, points d'entrée, dépendances, zones à risque), puis **trois agents de recherche explorent le code en parallèle** (Sonnet ; structure et composants ; usages, CU et glossaire ; données, contrats, contraintes et choix techniques ; le digest répartit les fichiers à lire entre eux) et un quatrième (Opus) consolide leurs résultats en une **cartographie**, un index court : identifiants des composants, cas d'utilisation, données, contrats, choix techniques constatés, glossaire, zones d'incertitude ; le détail reste dans les explorations. Après validation de cette structure par vos choix, **deux agents rédigent en parallèle** le PRD d'une part, architecture + glossaire d'autre part (composants en tableau, flux d'intégration, index des contrats), avec **exactement la même structure qu'un projet cadré avec `/kickoff`**, en `brouillon`, chaque élément suivi de sa preuve `*(déduit : fichier:ligne)*` ; ce que le code ne dit pas devient question ouverte (10 au plus par document, les autres restent dans la cartographie). **Pas d'ADR ni de décision à trancher** : les décisions sont déjà prises ; les choix techniques constatés sont décrits dans l'architecture (§ 6), sans question sur leur raison. Un ADR ne naît ensuite, avec `/kickoff`, que d'une nouvelle décision (changer un choix existant). **Pas d'eval** (les incohérences sont celles du code existant) : un script vérifie que chaque preuve `fichier:ligne` existe. Puis `/openapi` pour les spécifications des API, `/kickoff` pour affiner ou `/sync` pour publier. N'écrase jamais un document existant. |
| `/openapi [projet] [CTR-xx…]` | Produit ou met à jour les spécifications machine des contrats listés au § 5.2 de l'architecture, dans `docs/contrats/` : OpenAPI 3.1 (API HTTP exposée, et chaque API tierce appelée, limitée aux opérations utilisées), AsyncAPI 3.0 (événements, file de messages), JSON Schema (format de fichier). Extraites du code pour un projet existant (preuve `x-source` par opération), conçues d'après le PRD pour un cadrage neuf (`x-besoins`, propositions `x-propose`). Validées par `redocly` / `asyncapi` ; l'index du § 5.2 est mis à jour. Toutes les specs ont une URL de base absolue et des exemples de corps, pour être importées dans Postman telles quelles. |
| `/eval` | Relance à la main une passe d'évaluation des points d'ombre. |
| `/sync [projet] [--refaire]` | Publie la documentation sur Confluence sous une page racine `<Projet>`. Un agent **`mise-en-page`** lit les documents (PRD, architecture, glossaire, ADR, spécifications) et l'arborescence cible du plugin (`templates/confluence-arborescence.md`) : page d'arrivée (présentation, sommaire, démarrage en local, variables d'environnement, structure du code, conventions, tests), Vue d'ensemble, Fonctionnel, Architecture découpée en Données, Flux, Interfaces (une page Contrat par spécification, spécification complète dans un bloc repliable) et Services externes, Décisions (ADR) — projet cadré seulement —, Points ouverts et dette, Glossaire. Il décide du contenu de chaque page (sélection, déplacement, fusion des doublons, nettoyage des traces du processus) sans rien inventer ni perdre d'identifiant. Le script `skills/sync/resoudre.py` vérifie son rendu (aucun identifiant métier perdu, ni « § », ni titre numéroté, ni identifiant de processus), résout les liens entre pages et insère les spécifications depuis le disque, calcule les empreintes, prépare les lots et fusionne les résultats. La mise en page n'est refaite que si les sources ont changé (ou avec `--refaire`). Publication en deux temps : squelette des pages nouvelles et remise en ordre de l'arborescence, puis corps publiés **en parallèle** par des agents `publication` (6 au maximum), avec le statut natif de chaque page. Diagrammes Mermaid rendus en PNG (mermaid-cli, en parallèle) et insérés en image avec leur source repliée ; chaque spécification est jointe à sa page Contrat (fichier téléchargeable). L'envoi des fichiers exige une règle de permission pour la commande `curl` d'envoi vers Confluence (voir `skills/sync/SKILL.md`). Le backlog et les stories restent dans le dépôt. Proposé en fin de `/validate`. Nécessite le connecteur Atlassian, et mermaid-cli pour les images. |
| `/doctor` | Vérifie les dépendances (python3 et PyYAML, curl, unzip, Node.js, mermaid-cli, son navigateur headless et ses bibliothèques système, linters OpenAPI / AsyncAPI, uv et Code Review Graph, connecteur Atlassian) et installe celles qui manquent, avec votre accord. Proposé par `/sync` si le rendu des diagrammes est impossible, par `/reverse` si Code Review Graph manque, et par `/openapi` si le linter manque. |
| `/compare [projets…]` | Compare plusieurs runs du même projet (qualité, temps, coût) à partir de leurs métriques. |
| `/validate` | Valide le document courant et passe à l'étape suivante (PRD → architecture → ADR → backlog), puis génère les documents suivants (architecture + ADR + index, puis backlog + stories) avec les propositions de l'agent, marquées *(proposé)* ; ils seront évalués à la fin du `/kickoff` suivant. Avertit s'il reste des points bloquants, sans jamais bloquer. |

## Documents produits

Chaque projet cadré a son propre dossier, créé par `/kickoff` dans le répertoire courant (ex. `pomodoro/`). Le nom du répertoire courant n'est jamais utilisé comme information sur le projet.

Les documents existants passés en argument (sources) sont mémorisés dans le champ `sources:` du PRD : ils restent lus par l'agent de cadrage (analyse, génération de l'architecture et des ADR) et par l'évaluateur. Formats lus : texte, markdown, mermaid, plantuml, PDF, images ; les autres (`.docx`, `.pptx`…) sont signalés et ignorés.

```
<projet>/docs/
  prd.md               # Besoins et exigences
  architecture.md      # Vue d'architecture (composants, données, flux d'intégration, index des contrats…)
  contrats/            # Spécifications des contrats (/openapi) : *.openapi.yaml, *.asyncapi.yaml, *.schema.json
  adr/index.md         # Index des décisions
  adr/NNNN-*.md        # Une décision par fichier
  glossaire.md         # Vocabulaire du projet
  eval/AAAA-MM-JJ-HHMM.md  # Une passe d'évaluation par fichier (historique)
<projet>/.sohub-plugin/
  backlog.md           # User stories, priorités, dépendances et statut de dev de chaque US
  stories/US-NNN-*.md  # Une story autonome par fichier : critères d'acceptation, tâches ordonnées
  metrics.jsonl        # Métriques (automatique, source de vérité) : une ligne par intervention
  metrics.md           # Vue lisible des métriques, régénérée à chaque ajout
  reverse/graphe.md    # Projet existant : digest du graphe de code
  reverse/exploration/ # Projet existant : résultats des trois explorations parallèles
  reverse/cartographie.md  # Projet existant : structure de documentation proposée puis validée
  reverse/preuves.md   # Projet existant : vérification des références fichier:ligne
  sync/                # Fichiers de travail de /sync (corps de page, lots, résultats)
<projet>/.code-review-graph/  # Base du graphe (Code Review Graph, ignoré par git)
```

**Projet existant.** Pour `/reverse`, le projet est le dépôt de code lui-même : les documents sont écrits dans son `docs/`. Ils portent `origine: rétro` ; le champ `sources:` du PRD cite le dépôt avec sa branche et son commit. Les agents ne relisent pas tout le dépôt ensuite : seulement les fichiers cités par les marqueurs `*(déduit : …)*`, dont `check_refs.py` vérifie l'existence en fin de `/reverse` (et l'évaluateur par sondage, lors d'un `/kickoff`). `docs/adr/index.md` reste vide : les choix constatés sont dans la table « Choix techniques constatés » de l'architecture. Nécessite Code Review Graph (`uv tool install "code-review-graph[communities]"`, ou `/doctor`).

Le backlog est généré à la validation des ADR, affiné par `/kickoff`, puis validé. Ensuite, l'IA de dev suit ses « Règles de suivi » : elle prend la première US P1 `à faire` dont les dépendances sont `fait`, passe son statut à `en cours` → `en revue` → `fait` dans le tableau du backlog et coche les tâches de la story.

Pas de fichier d'état : l'étape courante se déduit du champ `statut` (`brouillon` / `validé`) en tête de `prd.md`, `architecture.md`, `adr/index.md` et `.sohub-plugin/backlog.md`. Le champ `maj` donne la date de dernière rédaction ; il permet de savoir si le dernier eval est à jour.

Règles communes aux documents : les identifiants (EF-xx, CU-xx, US-xxx, E-xxx…) ne sont jamais renumérotés ni réutilisés, un point non tranché porte un marqueur `[À CLARIFIER : Q-xx]` à l'endroit concerné en plus de sa question ouverte, une question tranchée est intégrée au document puis retirée, et chaque décision de l'utilisateur est tracée dans un journal des décisions. L'architecture passe trois contrôles de conception (simplicité, anti-abstraction, intégration d'abord) ; tout écart est justifié dans un « Suivi de la complexité ».

**Métriques.** Deux hooks remplissent `<projet>/.sohub-plugin/metrics.jsonl` à partir des transcripts (jamais à partir de ce que disent les agents) :
- `SubagentStop` : une ligne par intervention d'agent — acteur, modèle · effort, mode, étape, tâche, début, fin, durée, tours, outils, tokens (entrée, cache écrit, cache lu, sortie), coût d'entrée, coût de sortie, et la qualité (points d'ombre et bloquants du dernier eval) pour les evals ;
- `Stop` : le travail de l'orchestrateur (session principale) pendant le tour, découpé par itération.

`metrics.md` est régénéré à chaque ajout : résumé du run, tableau par itération (durée, coûts, points ouverts), moyennes par acteur, mode et modèle, et le détail des interventions. Les coûts sont estimés aux tarifs de l'API Anthropic (table `PRICES` de `hooks/metrics.py`, à mettre à jour si les tarifs changent).

Pour comparer la qualité, le temps et le coût, génère le même projet dans plusieurs dossiers (ex. `pomodoro-v1`, `pomodoro-v2`), puis lance `/compare pomodoro-v1 pomodoro-v2` (ou `python3 hooks/metrics.py compare …`). Nécessite `python3`.

Inspirations : [spec-kit](https://github.com/github/spec-kit) (marqueurs de clarification, gates d'architecture, tâches ordonnées tests d'abord avec `[P]`) et [BMAD](https://github.com/bmad-code-org/BMAD-METHOD) (stories autonomes, suivi de statut, contrôle « prêt à développer »).

## Conception

**Principe.** Tout ce qui est attendu doit être écrit noir sur blanc : l'IA qui développera ne doit rien avoir à deviner ni à inventer.

**Échanges.** L'utilisateur ne parle qu'à l'orchestrateur (la commande), jamais directement aux agents. L'orchestrateur invoque l'agent de cadrage, qui précise et challenge la demande, puis lui remonte ses points bloquants, ses zones de flou et ses propositions. L'orchestrateur les traduit pour l'utilisateur, avec des options, et l'utilisateur tranche. Un seul agent de cadrage porte à la fois la casquette de celui qui challenge et de celui qui propose ; un second agent « copilote » reste en réserve si, à l'usage, il mélange trop les deux.

**Agent de cadrage.** C'est un product owner sceptique, qui adopte le point de vue du client et de l'utilisateur final. Il traque les besoins réels, pas les fonctionnalités supposées : tout besoin non justifié est écarté tant qu'il n'a pas prouvé un vrai usage (à qui sert la fonctionnalité, dans quel usage concret). Il pose des questions ciblées et groupées, saute celles dont la réponse est connue, reformule pour vérifier, pointe les contradictions, et n'invente jamais une réponse à la place de l'utilisateur.

**La boucle.**
1. Avec `/kickoff`, l'agent cadre la demande, l'utilisateur tranche, et le document de l'étape courante est rédigé ou affiné.
2. L'eval se lance automatiquement en fin d'itération. C'est un regard à part : on produit, puis on audite. L'eval porte sur tous les documents qui existent déjà, et l'absence d'un document attendu est elle-même un point d'ombre.
3. L'utilisateur choisit alors entre trois suites :
   - **relancer** : une nouvelle itération part des points d'ombre du dernier eval ;
   - **valider** (`/validate`) : on passe à l'étape suivante, avec un simple avertissement s'il reste des points bloquants ;
   - **arrêter** : les documents restent en l'état, et l'on reprend plus tard.

**Ordre de génération.** On écrit d'abord le PRD, puis l'architecture, puis les ADR, puis le backlog d'US. Chaque décision d'architecture, chaque ADR et chaque US répond à un besoin écrit dans le PRD. Rien n'est jamais bloqué automatiquement : c'est toujours l'humain qui décide quand passer à l'étape suivante.

**Backlog d'US** (inspiré de spec-kit et BMAD) :
- Le découpage est vertical : une US apporte une valeur utilisateur testable de bout en bout. Les US P1 forment le MVP et couvrent tous les EF V1.
- Chaque story contient :
  - son récit ;
  - les besoins PRD, architecture et ADR auxquels elle répond ;
  - ses critères d'acceptation, reliés aux EF ;
  - ses tâches ordonnées contrats → tests → code, avec `[P]` pour celles qu'on peut paralléliser ;
  - sa définition de terminé.
- Le statut de chaque US vit uniquement dans le tableau du backlog.
- À l'étape BACKLOG, l'évaluateur fait le contrôle « prêt à développer ». Sont bloquants : un EF V1 sans US, une US sans besoin, une dépendance cassée.

## Structure du plugin

```
.claude-plugin/
  plugin.json          # Manifeste du plugin
  marketplace.json     # Marketplace locale pour tester le plugin
skills/kickoff/            # Orchestrateur : une itération de la boucle de cadrage
skills/eval/       # Passe d'évaluation (lancée aussi en fin d'itération)
skills/validate/   # Validation de l'étape courante
skills/sync/       # Synchronisation des documents vers Confluence (+ resoudre.py)
skills/doctor/     # Diagnostic et installation des dépendances (mermaid-cli, Code Review Graph, linters…)
skills/reverse/    # Rétro-documentation d'un projet existant (+ graph_digest.py, check_refs.py)
skills/openapi/    # Spécifications OpenAPI / AsyncAPI / JSON Schema des contrats
agents/cadrage.md      # Agent de cadrage : product owner sceptique (analyse, rédaction, proposition)
agents/evaluateur.md   # Auditeur : liste les points d'ombre dans docs/eval/
agents/recherche.md    # Agent de recherche : explore, cartographie un projet existant et rédige sa documentation
agents/mise-en-page.md # Agent de mise en page : transforme les documents en pages Confluence selon l'arborescence cible (lancé par /sync)
agents/publication.md  # Agent de publication : publie un lot de pages Confluence (lancé en parallèle par /sync)
templates/             # Gabarits : prd, architecture, adr, adr-index, glossaire, backlog, story, eval, confluence-arborescence, cartographie
skills/compare/   # Comparaison de runs (qualité, temps, coût)
hooks/hooks.json       # Hooks SubagentStop et Stop → hooks/metrics.py
hooks/metrics.py       # Métriques : enregistrement (hooks), rendu de metrics.md, comparaison de runs
```

## Tester en local

Lancer Claude Code avec le plugin chargé directement :

```bash
claude --plugin-dir .
```

Ou l'installer via la marketplace locale :

```
/plugin marketplace add ./
/plugin install sohub-plugins-kickoff@sohub-plugins-kickoff-dev
```
