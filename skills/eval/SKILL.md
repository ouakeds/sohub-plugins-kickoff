---
name: eval
description: Passe d'évaluation du cadrage de projet — fait auditer PRD, architecture, ADR et backlog d'US par l'agent évaluateur, qui liste tous les points d'ombre dans un nouveau fichier horodaté de docs/eval/. Lancé automatiquement en fin d'itération de /kickoff, ou à la main pour réévaluer les documents.
argument-hint: "[chemin du projet]"
allowed-tools: Agent, AskUserQuestion, Read, Glob, Bash(date:*), Bash(mkdir:*)
---

Tu lances une passe d'évaluation des documents de cadrage. L'audit lui-même est fait par l'agent **`evaluateur`** du plugin : tu ne juges pas les documents toi-même.

Argument reçu : `$ARGUMENTS` (chemin du projet ; peut être vide).

## Dossier du projet

Chaque projet cadré a **son propre dossier**, et ses documents sont dans `<projet>/docs/`. Le répertoire courant n'est pas le projet : il peut contenir plusieurs projets, et **son nom ne dit rien du projet** (ne t'en sers jamais comme information).

Pour trouver `<projet>` :
1. si un chemin de projet t'est passé en argument, utilise-le ;
2. sinon, si `docs/prd.md` existe dans le répertoire courant, le projet est le répertoire courant ;
3. sinon, cherche les `*/docs/prd.md` dans les sous-dossiers directs : un seul → c'est le projet ; plusieurs → demande lequel via `AskUserQuestion` ;
4. sinon, aucun projet n'existe : dis-le et propose de lancer `/kickoff` ; arrête-toi.

## Documents (dans `<projet>/`)

- `docs/prd.md`, `docs/architecture.md`, `docs/adr/index.md` + `docs/adr/NNNN-*.md`
- `.sohub-plugin/backlog.md` + `.sohub-plugin/stories/US-NNN-*.md` (à la racine du projet, pas dans `docs/`) : backlog des user stories ; le tableau du backlog porte le statut de développement de chaque US.
- `docs/eval/AAAA-MM-JJ-HHMM.md` : un fichier par passe d'eval, l'historique est conservé.

**Étape courante** = le premier document, dans l'ordre PRD → ARCHITECTURE → ADR (`docs/adr/index.md`) → BACKLOG (`.sohub-plugin/backlog.md`), qui n'existe pas ou dont le champ `statut` n'est pas `validé`.

## Procédure

1. Détermine le dossier du projet. Si `<projet>/docs/` ne contient aucun document de cadrage, dis-le et propose de lancer `/kickoff` ; arrête-toi.
2. Détermine l'étape courante.
3. Obtiens l'horodatage avec `date +%Y-%m-%d-%H%M` et crée le dossier avec `mkdir -p <projet>/docs/eval`.
4. Chemin du fichier : `<projet>/docs/eval/<horodatage>.md`. S'il existe déjà, ajoute un suffixe `-2`, `-3`…
5. Invoque l'agent `evaluateur` **au premier plan** (jamais en arrière-plan), avec pour description de l'appel `Agent` `Eval — <ÉTAPE>` (titre de tâche dans `.sohub-plugin/metrics.md`), et attends son rapport, en lui passant : le chemin absolu de `<projet>/docs/`, celui de `<projet>/.sohub-plugin/`, le chemin absolu du fichier à écrire, l'étape courante et le chemin du gabarit `${CLAUDE_SKILL_DIR}/../../templates/eval.md`.
6. Rapporte sa synthèse à l'utilisateur : chemin du fichier, nombre de points d'ombre, dont bloquants (et dont bloquants sur le document courant), points principaux.
