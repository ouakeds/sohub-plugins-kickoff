---
statut: brouillon
maj: AAAA-MM-JJ HH:MM
---
<!-- Gabarit du backlog (<projet>/.sohub-plugin/backlog.md). Les commentaires HTML sont des consignes de rédaction : ne pas les recopier.
Règles :
- Le `statut` en tête porte l'étape BACKLOG du cadrage (brouillon / validé), pas l'avancement du développement.
- Le statut d'une US vit UNIQUEMENT dans le tableau ci-dessous (source unique) ; les fichiers de story ne le répètent pas.
- Une US = une valeur utilisateur testable de bout en bout (découpage vertical, pas par couche technique). Chaque US renvoie à au moins un besoin PRD (EF, CU, RG) ; une US sans besoin PRD est un point à remonter, pas à écrire.
- Priorités : P1 = MVP (V1 du PRD), P2 / P3 = ensuite. Les US P1 suffisent à livrer tous les EF V1.
- Ce qui n'est pas tranché porte le marqueur en ligne [À CLARIFIER : QB-xx] à l'endroit concerné ET une ligne dans « Questions ouvertes ». Une proposition de l'agent se termine par *(proposé)*.
- Identifiants (US, QB) jamais renumérotés ni réutilisés. -->

# Backlog — <nom du projet>

## 1. User stories

<!-- Une ligne par US, dans l'ordre de réalisation conseillé. Statut initial : « à faire ». -->

| ID | Titre | Priorité | Statut | Dépend de | Besoins PRD | Fichier |
|----|-------|----------|--------|-----------|-------------|---------|
| US-001 | | P1 | à faire | aucune | EF-xx, CU-xx | [US-001](stories/US-001-<titre-kebab>.md) |

## 2. Règles de suivi

<!-- Recopier cette section telle quelle : elle s'adresse à l'IA qui développera l'application. -->

- **Statuts possibles** : `à faire` → `en cours` → `en revue` → `fait` ; `bloqué (<raison>)` à tout moment.
- **Prochaine US** : la première US P1 (puis P2, P3) au statut `à faire` dont toutes les dépendances sont `fait`.
- **En démarrant une US** : passe son statut à `en cours` dans le tableau ci-dessus. Une seule US `en cours` à la fois.
- **Pendant** : coche chaque tâche (`- [x]`) dans le fichier de la story dès qu'elle est faite, dans l'ordre indiqué.
- **En terminant** : passe l'US à `en revue` quand toutes ses tâches sont cochées, puis à `fait` seulement quand chacun de ses critères d'acceptation est vérifié.
- **Bloqué** : si un point n'est pas écrit dans les documents (PRD, architecture, ADR, story), **ne l'invente pas** : passe l'US à `bloqué (<question>)` et signale-le.
- Ne modifie rien d'autre dans ce fichier ni dans les documents de cadrage.

## 3. Couverture des exigences

<!-- Chaque EF V1 du PRD est couvert par au moins une US. -->

| EF | US |
|----|----|
| EF-01 | US-001 |

## 4. Questions ouvertes

| ID | Question | Bloquante | Origine |
|----|----------|-----------|---------|
| QB-01 | | oui / non | |

## 5. Journal des décisions

<!-- Une ligne par décision intégrée, la plus récente en bas. Ne jamais supprimer de ligne. -->

| Date | Point | Décision (mots de l'utilisateur) | Impacte |
|------|-------|----------------------------------|---------|
| AAAA-MM-JJ | B1 | | US-xxx |
