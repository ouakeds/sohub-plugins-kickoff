---
name: eval
description: Passe d'évaluation du cadrage de projet — fait auditer PRD, architecture, ADR et backlog d'US par l'agent évaluateur, qui liste tous les points d'ombre dans un nouveau fichier horodaté de docs/eval/. Lancé automatiquement en fin d'itération de /create-project et de /create-ticket (--ticket <ID>), ou à la main pour réévaluer les documents.
argument-hint: "[chemin du projet] [--ticket <ID>]"
allowed-tools: Agent, AskUserQuestion, Read, Glob, Bash(date:*), Bash(mkdir:*), Bash(python3:*)
---

Tu lances une passe d'évaluation des documents de cadrage. L'audit lui-même est fait par l'agent **`evaluator`** du plugin : tu ne juges pas les documents toi-même.

Argument reçu : `$ARGUMENTS` (chemin du projet ; peut être vide ; éventuellement suivi de `--ticket <ID>`, passé par `/create-ticket`).

## Dossier du projet

Chaque projet cadré a **son propre dossier**, et ses documents sont dans `<projet>/docs/`. Le répertoire courant n'est pas le projet : il peut contenir plusieurs projets, et **son nom ne dit rien du projet** (ne t'en sers jamais comme information).

Pour trouver `<projet>` :
1. si un chemin de projet t'est passé en argument, utilise-le ;
2. sinon, si `docs/prd.md` existe dans le répertoire courant, le projet est le répertoire courant ;
3. sinon, cherche les `*/docs/prd.md` dans les sous-dossiers directs : un seul → c'est le projet ; plusieurs → demande lequel via `AskUserQuestion` ;
4. sinon, aucun projet n'existe : dis-le et propose de lancer `/create-project` ; arrête-toi.

## Documents (dans `<projet>/`)

- `docs/prd.md`, `docs/architecture.md`, `docs/adr/index.md` + `docs/adr/NNNN-*.md`
- `.sohub-plugin/backlog.md` + `.sohub-plugin/stories/US-NNN-*.md` (à la racine du projet, pas dans `docs/`) : backlog des user stories ; le tableau du backlog porte le statut de développement de chaque US.
- `docs/eval/AAAA-MM-JJ-HHMMSS.md` : un fichier par passe d'eval, l'historique est conservé.

**Étape courante** = le premier document, dans l'ordre PRD → ARCHITECTURE → ADR (`docs/adr/index.md`) → BACKLOG (`.sohub-plugin/backlog.md`), qui n'existe pas ou dont le champ `statut` n'est pas `validé`.

## Procédure

1. Détermine le dossier du projet. Si `<projet>/docs/` ne contient aucun document de cadrage, dis-le et propose de lancer `/create-project` ; arrête-toi.
2. Détermine l'étape courante. Avec `--ticket <ID>`, l'étape est `TICKET <ID>` (le calcul ci-dessus ne s'applique pas).
3. Obtiens l'horodatage avec `date +%Y-%m-%d-%H%M%S` et crée le dossier avec `mkdir -p <projet>/docs/eval`.
4. Chemin du fichier : `<projet>/docs/eval/<horodatage>.md`. S'il existe déjà, ajoute un suffixe `-2`, `-3`…
4 bis. **Contrôle des plans de tâches** (étape BACKLOG, ou `TICKET <ID>`, dès que `.sohub-plugin/stories/` existe) : lance `python3 -I ${CLAUDE_SKILL_DIR}/check_tasks.py <projet>` (ajoute `--ticket <ID>` pour un ticket). Il vérifie mécaniquement que les stories sont prêtes à paralléliser (vagues, dépendances, fichiers écrits deux fois dans une vague, CA sans tâche, sous-tâches, lots d'US) et écrit `<projet>/.sohub-plugin/tasks.md` (`tasks-<ID>.md` pour un ticket). Il ne bloque jamais.
5. Invoque l'agent `evaluator` **au premier plan** (jamais en arrière-plan), avec pour description de l'appel `Agent` `Eval — <ÉTAPE>` (titre de tâche dans `.sohub-plugin/metrics.md`), et attends son rapport, en lui passant : le chemin absolu de `<projet>/docs/`, celui de `<projet>/.sohub-plugin/`, le chemin absolu du fichier à écrire, l'étape courante, le chemin du gabarit `${CLAUDE_SKILL_DIR}/../../templates/eval.md` et, s'il a été produit à l'étape 4 bis, le chemin du rapport (`tasks.md` ou `tasks-<ID>.md`).
6. Rapporte sa synthèse à l'utilisateur : chemin du fichier, nombre de points d'ombre, dont bloquants (et dont bloquants sur le document courant), points principaux.

**Langue** : adresse-toi à l'utilisateur (questions, options, résumés, comptes rendus) dans la langue qu'il emploie.
