---
etape: PRD | ARCHITECTURE | ADR | BACKLOG | TICKET <ID>
eval_precedent: <!-- AAAA-MM-JJ-HHMMSS ou aucun -->
points_ouverts: <N>
bloquants: <B>
bloquants_document_courant: <BC>
---
<!-- Gabarit d'une passe d'évaluation (docs/eval/AAAA-MM-JJ-HHMMSS.md). Les commentaires HTML sont des consignes : ne pas les recopier. Une section vide s'écrit « Aucun ».
Identifiants : E-001, E-002… PERSISTANTS d'une passe à l'autre. Un point déjà présent dans l'eval précédent garde son identifiant ; un nouveau point prend le numéro suivant le plus grand jamais attribué (jamais de réutilisation, même pour un point levé).
Les compteurs du frontmatter ne comptent que les points encore ouverts. Pour un eval de ticket (`etape: TICKET <ID>`), le « document courant » désigne les éléments du ticket (tous documents confondus). -->

# Eval — AAAA-MM-JJ HH:MM

## Synthèse

- **Documents évalués** : <!-- chemin + statut (brouillon / validé) + maj -->
- **Documents attendus absents** : <!-- ou « aucun » -->
- **Points ouverts** : <N> dont <B> bloquants (<BC> sur le document courant)

## Évolution depuis l'eval précédent

<!-- « Premier eval » s'il n'y en a pas. -->

- **Points levés** : <!-- E-xxx — titre — comment il a été levé (où c'est maintenant écrit) -->
- **Nouveaux points** : <!-- E-xxx -->
- **Points toujours ouverts** : <!-- E-xxx -->

## Points bloquants

<!-- Impossible de développer correctement sans la réponse : l'IA devrait inventer quelque chose qui change le produit. -->

### E-001 — <titre court>

- **État** : nouveau | toujours ouvert
- **Type** : manque | ambiguïté | contradiction | invérifiable | traçabilité | question ouverte | proposition
- **Où** : <document> § <section> (<identifiant si applicable>)
- **Problème** : <!-- ce qui manque, est ambigu ou se contredit, avec citation si utile -->
- **Ce que l'IA devrait inventer** :
- **Question à trancher** :

## Points non bloquants

<!-- Imprécision qui mérite d'être levée mais n'empêche pas d'avancer. -->

### E-002 — <titre court>

- **État** : nouveau | toujours ouvert
- **Type** :
- **Où** :
- **Problème** :
- **Question à trancher** :

## Traçabilité

### Dans le PRD

- **Exigences fonctionnelles sans cas d'usage** :
- **Cas d'usage sans exigence fonctionnelle** :
- **Exigences V1 sans critère d'acceptation** :
- **Écrans sans exigence / exigences V1 visibles sans écran** :
- **Règles métier sans rattachement** :

### Entre documents

<!-- Uniquement quand l'architecture ou les ADR existent. -->

- **Besoins PRD non couverts par l'architecture** :
- **Éléments d'architecture / ADR sans besoin PRD associé** :
- **Contraintes imposées (CT-xx) non respectées** :
- **« À décider (ADR attendu) » sans ADR ni entrée dans les décisions attendues** :
- **Contrôles de conception en écart sans justification au « Suivi de la complexité »** :
- **Marqueurs [À CLARIFIER : …] sans question ouverte, ou question ouverte sans marqueur** :
- **Flux (§ 4) sans contrat ou appelant un service absent du § 5.1, services externes (§ 5.1) sans contrat ou infrastructure rangée parmi eux, contrats (§ 5.2) sans producteur, consommateur ou spécification, spécifications de docs/contrats/ hors index** :

### Glossaire

<!-- Sur tous les documents (PRD, architecture, ADR, backlog et stories). « Glossaire absent » si docs/glossaire.md n'existe pas. -->

- **Termes propres au projet utilisés mais absents du glossaire** :
- **Définitions contredites par un document** :
- **Synonymes interdits employés** :

### Backlog

<!-- Uniquement quand .sohub-plugin/backlog.md existe. À l'étape BACKLOG, ces points sont bloquants : c'est le contrôle « prêt à développer ». -->

- **EF V1 sans US** :
- **US sans besoin PRD** :
- **Critères d'acceptation sans EF, ou EF d'une US sans critère d'acceptation** :
- **Dépendances circulaires ou vers une US inconnue** :
- **Tâches citant un fichier hors de la structure du code (§ 7 de l'architecture)** :
