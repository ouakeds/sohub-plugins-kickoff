---
name: validate
description: Valide l'étape courante du cadrage de projet et passe à la suivante (PRD → architecture → ADR → backlog d'US), puis fait générer les documents de l'étape suivante avec les propositions de l'agent de cadrage. Avertit s'il reste des points d'ombre bloquants dans le dernier eval, sans jamais bloquer. À utiliser uniquement sur demande explicite de l'utilisateur.
argument-hint: "[chemin du projet]"
allowed-tools: Agent, Skill, AskUserQuestion, Read, Glob, Grep, Edit, Bash(date:*), Bash(mkdir:*)
---

La validation est un **geste volontaire** de l'utilisateur. Ne lance ce skill que s'il l'a demandé (directement ou via le choix « Valider l'étape » de `/kickoff`). **Il n'y a jamais de blocage automatique** : tu avertis, l'utilisateur décide.

Argument reçu : `$ARGUMENTS` (chemin du projet ; peut être vide).

## Dossier du projet

Chaque projet cadré a **son propre dossier**, et ses documents sont dans `<projet>/docs/`. Le répertoire courant n'est pas le projet : il peut contenir plusieurs projets, et **son nom ne dit rien du projet** (ne t'en sers jamais comme information).

Pour trouver `<projet>` :
1. si un chemin de projet t'est passé en argument, utilise-le ;
2. sinon, si `docs/prd.md` existe dans le répertoire courant, le projet est le répertoire courant ;
3. sinon, cherche les `*/docs/prd.md` dans les sous-dossiers directs : un seul → c'est le projet ; plusieurs → demande lequel via `AskUserQuestion` ;
4. sinon, aucun projet n'existe : dis-le et propose de lancer `/kickoff` ; arrête-toi.

## Documents (dans `<projet>/`)

- `docs/prd.md`, `docs/architecture.md`, `docs/adr/index.md` : chacun porte en tête un champ `statut` (`brouillon` ou `validé`) et un champ `maj` (`AAAA-MM-JJ HH:MM`, dernière rédaction).
- `.sohub-plugin/backlog.md` (à la racine du projet) : même champs `statut` et `maj` ; son tableau porte en plus le statut de développement de chaque US (`à faire`, `en cours`…), qui n'est **pas** le statut de l'étape. Les stories sont dans `.sohub-plugin/stories/`.
- `docs/glossaire.md` : document transverse, sans `statut` ; il ne compte pas dans le calcul de l'étape et n'est jamais validé.
- `docs/adr/NNNN-*.md` : chaque ADR porte un champ `statut` (`proposé`, `accepté`, `rejeté`, `remplacé par ADR-XXXX`, `déprécié`).
- `docs/eval/AAAA-MM-JJ-HHMM.md` : le plus récent (plus grand nom) donne l'état actuel ; son frontmatter contient `bloquants_document_courant`.

**Étape courante** = le premier document, dans l'ordre PRD → ARCHITECTURE → ADR (`docs/adr/index.md`) → BACKLOG (`.sohub-plugin/backlog.md`), qui n'existe pas ou n'est pas `validé`.

## Procédure

1. Détermine le dossier du projet, puis l'étape courante. Si le cadrage est déjà entièrement validé, dis-le et arrête-toi. Si le document de l'étape n'existe pas : si l'étape précédente est validée (génération jamais faite ou interrompue), passe directement à l'étape 5 comme si elle venait d'être validée ; si c'est le PRD, dis-le, propose de lancer `/kickoff` et arrête-toi.
2. Lis le dernier fichier de `docs/eval/`.
   - S'il n'y en a pas, ou si son horodatage (nom du fichier) est antérieur au champ `maj` du document courant, signale que l'eval n'est pas à jour (et que `/eval` permet de le relancer).
   - Si `bloquants_document_courant` est supérieur à 0, **avertis** l'utilisateur en listant ces points (identifiant E-xxx + titre).
   - Si le document courant contient encore des questions ouvertes marquées bloquantes, **avertis** aussi en les listant.
   - À l'étape ADR, si la section « Décisions attendues » de `docs/adr/index.md` n'est pas vide, **avertis** en listant les décisions restantes.
   - S'il reste des marqueurs `[À CLARIFIER : …]` dans le document courant (à l'étape BACKLOG : backlog et stories), **avertis** en les listant.
   - S'il reste des **propositions de l'agent non confirmées** dans le document courant (marqueur `*(proposé)*`, stories comprises à l'étape BACKLOG ; à l'étape ADR, ADR dont « Tranchée par l'utilisateur le » vaut « non tranchée »), **avertis** en donnant leur nombre et les sections concernées : valider les accepte en bloc.
3. S'il y a eu un avertissement à l'étape 2, demande confirmation via `AskUserQuestion` : « Valider quand même » / « Revenir au cadrage ». Sinon, la demande de validation vaut confirmation.
4. Si confirmé : passe le champ `statut` du document courant à `validé` avec `Edit` — uniquement ce champ, rien d'autre. **À l'étape ADR**, passe aussi le `statut` de chaque ADR `proposé` à `accepté` (dans le fichier de l'ADR et dans le tableau de l'index) ; ne touche pas aux autres statuts. **À l'étape BACKLOG**, ne touche pas aux statuts des US (elles restent `à faire`). Si des propositions non confirmées restaient dans un document qui a un journal des décisions, ajoute-y une ligne `| <date> | VALIDATION | Propositions restantes acceptées en bloc à la validation de l'étape | <§ concernés> |`.
5. **Génération de l'étape suivante** (après validation du PRD, de l'architecture ou des ADR) :
   - après validation des ADR, crée le dossier avec `mkdir -p <projet>/.sohub-plugin/stories` ;
   - obtiens la date-heure avec `date '+%Y-%m-%d %H:%M'` ;
   - invoque l'agent `cadrage` **au premier plan** en mode `PROPOSITION` (description de l'appel `Agent` : `Cadrage PROPOSITION — après <ÉTAPE validée>`, titre de tâche dans `.sohub-plugin/metrics.md`), en lui passant : l'étape qui vient d'être validée, le chemin absolu de `<projet>/docs/`, celui de `<projet>/.sohub-plugin/`, le chemin des gabarits `${CLAUDE_SKILL_DIR}/../../templates/` et la date-heure ;
   - résume à l'utilisateur : fichiers générés, propositions structurantes (une ligne chacune), questions ouvertes créées (bloquantes d'abord). Pas d'eval ici : la validation acte l'étape, et les documents générés seront évalués à la fin du prochain `/kickoff`. Rappelle que tout ce qui est marqué `*(proposé)*` vient de l'agent, pas de lui, et propose de lancer `/kickoff` pour confirmer ou corriger ces propositions sur l'étape suivante. Après validation de l'**architecture**, si son index des contrats (§ 5.2) contient des lignes « À produire (/openapi) », rappelle que `/openapi` produit les spécifications de ces API dans `docs/contrats/`.
6. **Après validation du BACKLOG**, le cadrage est terminé : annonce-le, puis indique la prochaine US à développer selon les « Règles de suivi » du backlog (identifiant, titre, fichier) et rappelle que l'IA de dev doit suivre ces règles pour tenir les statuts à jour.
6 bis. **Synchronisation Confluence** (après l'étape 5 ou 6) : propose via `AskUserQuestion` « Synchroniser les documents sur Confluence ? » — « Oui » / « Non ». Si oui, invoque le skill `sohub-plugins-kickoff:sync` (outil `Skill`) en lui passant le chemin absolu de `<projet>` et rapporte son compte rendu (lien de la page racine, pages créées et mises à jour). Si non, rappelle que `/sync` permet de le faire plus tard. Ne synchronise jamais sans ce « Oui ».
7. Si l'utilisateur revient au cadrage : ne change rien et propose de relancer `/kickoff`.
