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
- Identifiants (US, QB) jamais renumérotés ni réutilisés.
- Les US d'un ticket (/create-ticket) sont ajoutées à la fin du tableau au statut « à cadrer » ; elles passent à « à faire » à la validation du ticket. Le ticket est indiqué dans la story (champ « Ticket »).
- Chaque story porte un « Plan de tâches » découpé en vagues parallélisables ; le statut des tâches vit dans la story. -->

# Backlog — <nom du projet>

## 1. User stories

<!-- Une ligne par US, dans l'ordre de réalisation conseillé. Statut initial : « à faire » (« à cadrer » pour une US de ticket non validé). -->

| ID | Titre | Priorité | Statut | Dépend de | Besoins PRD | Fichier |
|----|-------|----------|--------|-----------|-------------|---------|
| US-001 | | P1 | à faire | aucune | EF-xx, CU-xx | [US-001](stories/US-001-<titre-kebab>.md) |

## 2. Parallélisation des US

<!-- Lots d'US développables en même temps : dans un lot, aucune US ne dépend d'une autre et aucun fichier n'est écrit par deux US (colonnes « Fichiers écrits » des plans de tâches). Deux US qui écrivent le même fichier sont dans des lots successifs ou dépendantes. Un lot ne démarre que lorsque les dépendances de ses US sont « fait ». Les US « à cadrer » n'entrent dans aucun lot avant la validation de leur ticket. -->

| Lot | US | Après |
|-----|----|-------|
| L1 | US-001, US-002 | — |
| L2 | US-003 | L1 |

## 3. Règles de suivi

<!-- Recopier cette section telle quelle : elle s'adresse à l'IA (ou aux agents) qui développeront l'application. -->

- **Statuts d'une US** : `à cadrer` → `à faire` → `en cours` → `en revue` → `fait` ; `bloqué (<raison>)` à tout moment. Une US `à cadrer` est en cours de spécification : **ne la développe pas** et ne change pas son statut.
- **Statuts d'une tâche** (« Plan de tâches » de la story) : `à faire` → `en cours` → `fait` ; `bloqué (<question>)` à tout moment.
- **US prenables** : celles du premier lot de « Parallélisation des US » qui n'est pas entièrement `fait`, au statut `à faire` ou `en cours`, dont toutes les dépendances sont `fait`. Plusieurs US d'un même lot peuvent être développées en même temps.
- **Tâche prenable** : son US est prenable, son statut est `à faire`, toutes ses dépendances sont `fait`, et toutes les tâches des vagues précédentes de la story sont `fait`.
- **En prenant une tâche** : inscris ton nom dans « Agent » et passe-la `en cours` **avant** d'écrire du code. La première tâche démarrée passe l'US à `en cours` dans le tableau ci-dessus.
- **Périmètre** : n'écris que dans les « Fichiers écrits » de ta tâche (tu peux lire tout le reste). S'il faut en modifier un autre, n'y touche pas : passe la tâche à `bloqué (fichier hors périmètre : <chemin>)`.
- **En terminant une tâche** : vérifie son « Terminé quand », puis passe-la à `fait`. Quand toutes les tâches de l'US sont `fait`, passe l'US à `en revue`, puis à `fait` seulement quand chacun de ses critères d'acceptation est vérifié.
- **Un seul écrivain des statuts** : quand plusieurs agents travaillent en parallèle, seul l'orchestrateur du développement modifie ce fichier et les plans de tâches ; chaque agent lui rend son résultat (tâche, fichiers écrits, vérification, blocage éventuel).
- **Bloqué** : si un point n'est pas écrit dans les documents (PRD, architecture, ADR, story), **ne l'invente pas** : passe la tâche (et l'US) à `bloqué (<question>)` et signale-le.
- Ne modifie rien d'autre dans ce fichier, dans les stories ni dans les documents de cadrage.

## 4. Couverture des exigences

<!-- Chaque EF V1 du PRD est couvert par au moins une US. Projet rétro (origine: rétro) : seuls les EF créés ou modifiés par un ticket figurent ici ; les EF existants, déjà implémentés dans le code, n'ont pas d'US. -->

| EF | US |
|----|----|
| EF-01 | US-001 |

## 5. Questions ouvertes

| ID | Question | Bloquante | Origine |
|----|----------|-----------|---------|
| QB-01 | | oui / non | |

## 6. Journal des décisions

<!-- Une ligne par décision intégrée, la plus récente en bas. Ne jamais supprimer de ligne. -->

| Date | Point | Décision (mots de l'utilisateur) | Impacte |
|------|-------|----------------------------------|---------|
| AAAA-MM-JJ | B1 | | US-xxx |
