---
name: validate-step
description: Valide l'étape courante du cadrage de projet et passe à la suivante (PRD → architecture → ADR → backlog d'US) ; à la validation du PRD, fait fixer la stack technique (proposée par l'agent, choisie par l'utilisateur, ou laissée à l'architecture), puis fait générer les documents de l'étape suivante avec les propositions de l'agent de cadrage. Avertit s'il reste des points d'ombre bloquants dans le dernier eval, sans jamais bloquer. À utiliser uniquement sur demande explicite de l'utilisateur.
argument-hint: "[chemin du projet]"
allowed-tools: Agent, Skill, AskUserQuestion, Read, Glob, Grep, Edit, Bash(date:*), Bash(mkdir:*)
---

La validation est un **geste volontaire** de l'utilisateur. Ne lance ce skill que s'il l'a demandé (directement ou via le choix « Valider l'étape » de `/create-project`). **Il n'y a jamais de blocage automatique** : tu avertis, l'utilisateur décide.

Argument reçu : `$ARGUMENTS` (chemin du projet ; peut être vide).

## Dossier du projet

Chaque projet cadré a **son propre dossier**, et ses documents sont dans `<projet>/docs/`. Le répertoire courant n'est pas le projet : il peut contenir plusieurs projets, et **son nom ne dit rien du projet** (ne t'en sers jamais comme information).

Pour trouver `<projet>` :
1. si un chemin de projet t'est passé en argument, utilise-le ;
2. sinon, si `docs/prd.md` existe dans le répertoire courant, le projet est le répertoire courant ;
3. sinon, cherche les `*/docs/prd.md` dans les sous-dossiers directs : un seul → c'est le projet ; plusieurs → demande lequel via `AskUserQuestion` ;
4. sinon, aucun projet n'existe : dis-le et propose de lancer `/create-project` ; arrête-toi.

## Documents (dans `<projet>/`)

- `docs/prd.md`, `docs/architecture.md`, `docs/adr/index.md` : chacun porte en tête un champ `statut` (`brouillon` ou `validé`) et un champ `maj` (`AAAA-MM-JJ HH:MM`, dernière rédaction).
- `.sohub-plugin/backlog.md` (à la racine du projet) : même champs `statut` et `maj` ; son tableau porte en plus le statut de développement de chaque US (`à faire`, `en cours`…), qui n'est **pas** le statut de l'étape. Les stories sont dans `.sohub-plugin/stories/`.
- `docs/glossaire.md` : document transverse, sans `statut` ; il ne compte pas dans le calcul de l'étape et n'est jamais validé.
- `docs/adr/NNNN-*.md` : chaque ADR porte un champ `statut` (`proposé`, `accepté`, `rejeté`, `remplacé par ADR-XXXX`, `déprécié`).
- `docs/eval/AAAA-MM-JJ-HHMMSS.md` : un fichier par passe d'eval ; son frontmatter contient `etape` et `bloquants_document_courant`. **Dernier eval d'une étape** : parmi les fichiers de `docs/eval/` dont le champ `etape` vaut cette étape, celui dont le nom sans `.md` est le plus grand (noms `AAAA-MM-JJ-HHMMSS`, suffixe `-2`, `-3`… en cas de collision : cet ordre est chronologique).

**Étape courante** = le premier document, dans l'ordre PRD → ARCHITECTURE → ADR (`docs/adr/index.md`) → BACKLOG (`.sohub-plugin/backlog.md`), qui n'existe pas ou n'est pas `validé`.

## Procédure

1. Détermine le dossier du projet, puis l'étape courante. Si le cadrage est déjà entièrement validé, dis-le et arrête-toi. Si le document de l'étape n'existe pas : si l'étape précédente est validée (génération jamais faite ou interrompue), passe directement à l'étape 5 comme si elle venait d'être validée ; si c'est le PRD, dis-le, propose de lancer `/create-project` et arrête-toi.
2. Lis le dernier eval de l'étape courante (les evals de tickets, `etape: TICKET …`, ne comptent pas).
   - S'il n'y en a pas, ou si son horodatage (nom du fichier) est antérieur au champ `maj` du document courant, signale que l'eval n'est pas à jour (et que `/review-specs` permet de le relancer).
   - Si `bloquants_document_courant` est supérieur à 0, **avertis** l'utilisateur en listant ces points (identifiant E-xxx + titre).
   - Si le document courant contient encore des questions ouvertes marquées bloquantes, **avertis** aussi en les listant.
   - À l'étape ADR, si la section « Décisions attendues » de `docs/adr/index.md` n'est pas vide, **avertis** en listant les décisions restantes.
   - S'il reste des marqueurs `[À CLARIFIER : …]` dans le document courant (à l'étape BACKLOG : backlog et stories), **avertis** en les listant.
   - À l'étape BACKLOG, si `.sohub-plugin/tasks.md` (contrôle des plans de tâches lancé par l'eval) signale des anomalies, **avertis** en les listant : les tâches ne seraient pas prêtes à paralléliser.
   - À l'étape BACKLOG, ignore dans ces contrôles les US au statut `à cadrer` et leurs stories : elles appartiennent à un ticket en cours, validé par `/create-ticket`.
   - S'il reste des **propositions de l'agent non confirmées** dans le document courant (marqueur `*(proposé)*`, stories comprises à l'étape BACKLOG ; à l'étape ADR, ADR dont « Tranchée par l'utilisateur le » vaut « non tranchée »), **avertis** en donnant leur nombre et les sections concernées : valider les accepte en bloc.
3. S'il y a eu un avertissement à l'étape 2, demande confirmation via `AskUserQuestion` : « Valider quand même » / « Revenir au cadrage ». Sinon, la demande de validation vaut confirmation.
3 bis. **Stack technique** (étape PRD seulement, une fois la validation confirmée, avant de passer le PRD à `validé`). La stack est une donnée du PRD (§ 3.1 « Stack technique ») : elle s'impose ensuite à l'architecture et aux ADR. Si le PRD porte `origine: rétro`, ou si sa section « 3.1 Stack technique » contient déjà une ligne `CT-xx` remplie (choix écrit, sans `<…>`) ou la ligne « Non imposée … », passe à l'étape 4. Sinon (section absente, vide ou « À fixer à la validation du PRD », ancien PRD compris), demande via `AskUserQuestion` « Quelle stack technique pour ce projet ? (ou réponds librement) » :
   - **Proposer une stack** → invoque `scoping` **au premier plan** en mode `STACK` (description : `Cadrage STACK — PRD`), en lui passant le chemin absolu de `<projet>/docs/`, celui de `<projet>/.sohub-plugin/` et le chemin des gabarits. Présente ses stacks via `AskUserQuestion` : une option par stack (recommandée en premier), libellé = son nom court, description = ses briques et versions en une ligne ; l'utilisateur peut en ajuster une dans le champ libre (ex. « la B, mais avec PostgreSQL »). Si l'agent signale des manques, cite-les dans la question ;
   - **Je la choisis** → l'utilisateur écrit sa stack dans le champ libre (couches, choix, versions s'il les connaît) ; s'il choisit l'option sans texte, redemande-le une fois ;
   - **Laisser l'architecture la proposer** → la stack n'est pas imposée : l'agent la proposera avec l'architecture.

   Puis obtiens la date-heure avec `date '+%Y-%m-%d %H:%M'` et invoque `scoping` **au premier plan** en mode `RÉDACTION`, étape `PRD` (description : `Cadrage RÉDACTION — PRD`), effort `medium`, en lui passant les chemins ci-dessus, la date-heure et la décision `STACK` **telle que l'utilisateur l'a formulée**, suivie entre crochets du contenu exact de la stack acceptée (repris du rapport `STACK`) ou de « laisser l'architecture la proposer ». Il remplit uniquement la section 3.1 du PRD (et son journal). L'eval n'est pas relancé.
4. Si confirmé : passe le champ `statut` du document courant à `validé` avec `Edit` — uniquement ce champ, rien d'autre. **À l'étape ADR**, passe aussi le `statut` de chaque ADR `proposé` à `accepté` (dans le fichier de l'ADR et dans le tableau de l'index) et, dans un ADR dont « Tranchée par l'utilisateur le » vaut « non tranchée », écris `<date> (acceptation en bloc à la validation de l'étape ADR)` ; ne touche pas aux autres statuts. **À l'étape BACKLOG**, ne touche pas aux statuts des US (elles restent `à faire`). Si des propositions non confirmées restaient dans un document qui a un journal des décisions, ajoute-y une ligne `| <date> | VALIDATION | Propositions restantes acceptées en bloc à la validation de l'étape | <§ concernés> |`.
5. **Génération de l'étape suivante** (après validation du PRD, de l'architecture ou des ADR) :
   - **après validation de l'architecture**, si la section « Décisions attendues » de `docs/adr/index.md` est vide ou vaut « Aucune », ne lance pas l'agent : les ADR ont déjà été proposés avec l'architecture. Dis-le, compte les ADR `proposé` et indique qu'ils se confirment avec `/create-project` (étape ADR) ou qu'on peut valider l'étape ADR directement ; passe à l'étape 5 bis ;
   - après validation des ADR, crée le dossier avec `mkdir -p <projet>/.sohub-plugin/stories` ;
   - obtiens la date-heure avec `date '+%Y-%m-%d %H:%M'` ;
   - invoque l'agent `scoping` **au premier plan** en mode `PROPOSITION` (description de l'appel `Agent` : `Cadrage PROPOSITION — après <ÉTAPE validée>`, titre de tâche dans `.sohub-plugin/metrics.md`), en lui passant : l'étape qui vient d'être validée, le chemin absolu de `<projet>/docs/`, celui de `<projet>/.sohub-plugin/`, le chemin des gabarits `${CLAUDE_SKILL_DIR}/../../templates/` et la date-heure ;
   - résume à l'utilisateur : fichiers générés, propositions structurantes (une ligne chacune), questions ouvertes créées (bloquantes d'abord). Pas d'eval ici : la validation acte l'étape, et les documents générés seront évalués à la fin du prochain `/create-project`. Rappelle que tout ce qui est marqué `*(proposé)*` vient de l'agent, pas de lui, et propose de lancer `/create-project` pour confirmer ou corriger ces propositions sur l'étape suivante. Après validation de l'**architecture**, si son index des contrats (§ 5.2) contient des lignes « À produire (/create-api-specs) », rappelle que `/create-api-specs` produit les spécifications de ces API dans `docs/contrats/`.
5 bis. **Suite** : propose via `AskUserQuestion` « Continuer le cadrage » (→ invoque le skill `sohub-plugins-spec:create-project` avec le chemin absolu de `<projet>` : l'itération suivante part des propositions de l'étape) / « Arrêter là » (on reprend avec `/create-project`).
6. **Après validation du BACKLOG**, le cadrage est terminé : annonce-le, puis indique ce qui est prenable selon les « Règles de suivi » du backlog : le premier lot de « Parallélisation des US », ses US (identifiant, titre, fichier) et le nombre de tâches de leur vague 1, réalisables en parallèle. Rappelle que les agents de dev doivent suivre ces règles (un seul écrivain des statuts quand ils sont plusieurs). Rappelle que toute évolution (feature, bugfix) se cadre ensuite avec `/create-ticket`.
6 bis. **Synchronisation Confluence** (après l'étape 6 seulement : en fin de cadrage) : propose via `AskUserQuestion` « Synchroniser les documents sur Confluence ? » — « Oui » / « Non ». Si oui, invoque le skill `sohub-plugins-spec:confluence-sync` (outil `Skill`) en lui passant le chemin absolu de `<projet>` et rapporte son compte rendu (lien de la page racine, pages créées et mises à jour). Si non, rappelle que `/confluence-sync` permet de le faire plus tard. Ne synchronise jamais sans ce « Oui ».
7. Si l'utilisateur revient au cadrage : ne change rien et propose de relancer `/create-project`.

**Langue** : adresse-toi à l'utilisateur (questions, options, résumés, comptes rendus) dans la langue qu'il emploie.
