---
maj: AAAA-MM-JJ HH:MM
---
<!-- Gabarit d'une user story (<projet>/.sohub-plugin/stories/US-NNN-<titre-kebab>.md, NNN sur 3 chiffres). Les commentaires HTML sont des consignes : ne pas les recopier.
Règles :
- La story est autonome : l'IA de dev doit pouvoir la réaliser en lisant ce fichier et les sections qu'il cite, sans rien deviner.
- Son statut d'avancement n'est PAS ici : il vit dans le tableau de ../backlog.md.
- Ce qui n'est pas tranché porte le marqueur [À CLARIFIER : QB-xx] (question ouverte du backlog). Une proposition de l'agent se termine par *(proposé)*. -->

# US-NNN — <titre>

**En tant que** <type d'utilisateur du PRD>, **je veux** <action>, **afin de** <bénéfice>.

- **Priorité** : P1 / P2 / P3
- **Besoins PRD** : <!-- EF-xx, CU-xx, RG-xx, ENF-xx -->
- **Architecture** : <!-- § de docs/architecture.md concernés -->
- **ADR** : <!-- ADR-NNNN qui s'appliquent, ou « aucun » -->
- **Dépend de** : <!-- US-xxx ou « aucune » -->

## Critères d'acceptation

<!-- Chacun vérifiable et relié à un critère d'acceptation d'un EF du PRD. -->

- **CA-NNN-01** (EF-xx) — Étant donné <contexte>, quand <action>, alors <résultat observable>.

## Tâches

<!-- Ordre : contrats / interfaces → tests (qui doivent échouer) → code qui les fait passer → intégration. [P] = réalisable en parallèle des autres tâches [P] du même bloc (fichiers distincts, pas de dépendance). Chaque tâche cite les fichiers touchés (structure du § 7 de l'architecture) et les CA qu'elle sert. -->

- [ ] **T-NNN-01** <tâche> — fichiers : `<chemin>` — CA-NNN-01
- [ ] **T-NNN-02** [P] <tâche> — fichiers : `<chemin>` — CA-NNN-01

## Définition de terminé

- Toutes les tâches sont cochées.
- Chaque critère d'acceptation est couvert par un test qui passe.
- Les conventions (§ 8 de l'architecture) et les contrôles de conception sont respectés.
- <!-- critère propre à cette US, s'il y en a -->
