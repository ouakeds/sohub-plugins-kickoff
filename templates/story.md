---
maj: AAAA-MM-JJ HH:MM
---
<!-- Gabarit d'une user story (<projet>/.sohub-plugin/stories/US-NNN-<titre-kebab>.md, NNN sur 3 chiffres). Les commentaires HTML sont des consignes : ne pas les recopier.
Règles :
- La story est autonome : l'IA de dev doit pouvoir la réaliser en lisant ce fichier et les sections qu'il cite, sans rien deviner.
- Le statut de l'US n'est PAS ici : il vit dans le tableau de ../backlog.md. Le statut de chaque TÂCHE vit ici, dans le « Plan de tâches » (source unique), tenu par un seul écrivain (l'IA de dev, ou l'orchestrateur de développement quand plusieurs agents travaillent en parallèle).
- Le plan de tâches prépare un développement parallèle : plusieurs agents doivent pouvoir réaliser les tâches d'une même vague en même temps, sans conflit.
- Ce qui n'est pas tranché porte le marqueur [À CLARIFIER : QB-xx] (question ouverte du backlog). Une proposition de l'agent se termine par *(proposé)*. -->

# US-NNN — <titre>

**En tant que** <type d'utilisateur du PRD>, **je veux** <action>, **afin de** <bénéfice>.

- **Type** : feature / bug <!-- bug : US issue d'un ticket /create-ticket qui corrige un écart à la spec ou un cas non spécifié -->
- **Ticket** : <!-- identifiant du ticket /create-ticket (clé Jira ou TK-NNN), ou « aucun » pour une US du cadrage initial -->
- **Priorité** : P1 / P2 / P3
- **Besoins PRD** : <!-- EF-xx, CU-xx, RG-xx, ENF-xx -->
- **Architecture** : <!-- § de docs/architecture.md concernés -->
- **ADR** : <!-- ADR-NNNN qui s'appliquent, ou « aucun » -->
- **Dépend de** : <!-- US-xxx ou « aucune » -->

## Critères d'acceptation

<!-- Chacun vérifiable et relié à un critère d'acceptation d'un EF du PRD. -->

- **CA-NNN-01** (EF-xx) — Étant donné <contexte>, quand <action>, alors <résultat observable>.

## Plan de tâches

<!-- Une ligne par tâche (ou sous-tâche). Règles :
- Vagues : une tâche ne dépend que de tâches de vagues ANTÉRIEURES. Toutes les tâches d'une vague sont réalisables en même temps.
- Vague 1 = contrats : interfaces, types, signatures, schémas, figés avant le reste ; les vagues suivantes codent contre eux.
- Exception bug : pour une US de type bug, la vague 1 est le test de non-régression, qui échoue tant que le bug existe ; les contrats viennent ensuite, s'il en faut.
- Tests d'abord : le test d'un CA est une tâche distincte (il doit échouer tant que le code n'existe pas), dans la même vague que le code qui le fait passer, avec des fichiers différents.
- Dernière vague = intégration : les fichiers partagés (registre de routes, index, injection de dépendances, configuration) ne sont écrits que par une seule tâche, à la fin.
- Anti-conflit : deux tâches d'une même vague n'écrivent JAMAIS le même fichier. « Lit » est libre.
- Fichiers écrits : chemins exacts, entre accents graves, séparés par des virgules, conformes à la structure du code (§ 7 de l'architecture).
- Sous-tâches : un seul niveau (T-NNN-03a, T-NNN-03b). Une tâche découpée a « — » en vague, fichiers écrits et « Terminé quand » (chaque sous-tâche porte le sien) ; elle est « fait » quand toutes ses sous-tâches le sont. Découper dès qu'une tâche écrit plus de 3 fichiers ou sert plus d'un CA, sauf les tâches de contrat (vague 1) et d'intégration (dernière vague), qui peuvent servir plusieurs CA.
- Autonomie : « Lit » liste ce que l'agent doit lire en plus de cette story (§ d'architecture, contrats, ADR, fichiers existants) ; « Terminé quand » est une vérification observable (commande, test, comportement).
- Statut : à faire → en cours → fait ; bloqué (<question>) à tout moment. Agent : « — » tant que personne n'a pris la tâche. À la rédaction, toutes les tâches sont « à faire » avec « — ». -->

| ID | Tâche | Vague | Dépend de | Fichiers écrits | Lit | CA | Terminé quand | Statut | Agent |
|----|-------|-------|-----------|-----------------|-----|----|---------------|--------|-------|
| T-NNN-01 | <contrat / interface> | 1 | — | `<chemin>` | <§ archi, contrat> | CA-NNN-01 | <vérification> | à faire | — |
| T-NNN-02 | <test qui échoue> | 2 | T-NNN-01 | `<chemin>` | | CA-NNN-01 | <vérification> | à faire | — |
| T-NNN-03 | <code> | 2 | T-NNN-01 | `<chemin>` | | CA-NNN-01 | <vérification> | à faire | — |
| T-NNN-04 | <intégration> | 3 | T-NNN-02, T-NNN-03 | `<chemin>` | | CA-NNN-01 | <vérification> | à faire | — |

## Parallélisation

- **Vagues** : <N>
- **Tâches en parallèle (max)** : <N> (vague <n>)
- **Chemin critique** : <T-NNN-01 → T-NNN-03 → T-NNN-04>

## Définition de terminé

- Toutes les tâches sont `fait`.
- Chaque critère d'acceptation est couvert par un test qui passe.
- Les conventions (§ 8 de l'architecture) et les contrôles de conception sont respectés.
- <!-- critère propre à cette US, s'il y en a -->
