---
statut: brouillon
maj: AAAA-MM-JJ HH:MM
---
<!-- Gabarit architecture. Les commentaires HTML sont des consignes de rédaction : ne pas les recopier dans le document final.
Règles :
- Chaque élément renvoie à un besoin du PRD (CU-xx, EF-xx, ENF-xx, RG-xx, CT-xx) ; un élément sans besoin associé est un point à remonter, pas à écrire.
- Les contraintes imposées du PRD (CT-xx) s'appliquent telles quelles.
- Un choix technique structurant non encore tranché s'écrit « À décider (ADR attendu) » et est ajouté aux « Décisions attendues » de docs/adr/index.md. Les ADR sont rédigés à l'étape suivante.
- Document généré à la validation du PRD (mode PROPOSITION) : ce qui n'est pas tranché par le PRD ou l'utilisateur est une proposition de l'agent, terminée par le marqueur *(proposé)* ; un choix structurant renvoie à son ADR proposé. Le marqueur est retiré quand l'utilisateur confirme.
- Une section sans contenu tranché s'écrit « Aucun » ou renvoie vers une question ouverte (« Voir QA-02 »). Jamais de ligne de tableau vide.
- Marqueur en ligne : à l'endroit exact du texte concerné par un point non tranché, écrire [À CLARIFIER : QA-xx], en plus de la ligne QA-xx dans « Questions ouvertes ». Le marqueur est retiré quand la question est tranchée.
- Identifiants jamais renumérotés ni réutilisés.
- Document COURT : c'est une vue d'ensemble, pas une spécification. Tableaux plutôt que blocs de puces ; une à deux phrases par cellule. Le détail fonctionnel (déroulé des cas d'usage, écrans, règles) reste dans le PRD ; le détail des API (opérations, schémas, erreurs) va dans les spécifications de docs/contrats/ produites par /openapi. Ne recopie ni l'un ni l'autre ici.
- Projet existant (`origine: rétro`) : une preuve `fichier:ligne` par élément (ligne de tableau, entité, flux), dans la colonne « Preuve » ou en fin de cellule — pas une par phrase. Les chemins de fichiers s'écrivent entre accents graves (`app/__init__.py:31`).
- Questions ouvertes : 10 au maximum, les bloquantes d'abord ; ne garder que celles dont la réponse changerait l'architecture. Un doute mineur (valeur par défaut, détail de configuration) se signale en « Point d'attention », sans question. -->

# Architecture — <nom du projet>

## 1. Vue d'ensemble

<!-- Un paragraphe + un schéma (mermaid) des composants (§ 2), de leurs dépendances et des services externes (§ 5.1). Les échanges avec l'extérieur sont détaillés au § 4. -->

```mermaid
flowchart LR
```

## 2. Composants

<!-- Un composant = un ensemble cohérent de responsabilités, identifiable dans le code (dossiers ou fichiers) ; viser 4 à 12 composants. Une ligne par composant, même tableau pour un cadrage neuf (/create-project) et pour un projet existant (/reverse). Cadrage neuf : l'emplacement est celui prévu par la structure du code (§ 7). Projet existant : emplacement constaté, avec sa preuve. Les entités (§ 3), flux (§ 4) et contrats (§ 5.2) ne sont pas décrits ici : on y renvoie par leur identifiant. Un paragraphe d'introduction de 3 phrases au plus peut précéder le tableau (comment le code est découpé). -->

| ID | Composant | Rôle (1 à 2 phrases) | Emplacement | Dépend de | Besoins PRD | Points d'attention |
|----|-----------|----------------------|-------------|-----------|-------------|--------------------|
| CMP-01 | <nom> | | <dossiers ou fichiers principaux> | <CMP-xx, services § 5.1> | CU-xx, EF-xx | <risque, dette, couplage surprenant, code non testé sur un chemin sensible ; « Aucun »> |

## 3. Données

### 3.1 Modèle

<!-- Schéma des entités, de leurs clés et de leurs relations (cardinalités). -->

```mermaid
erDiagram
```

<!-- Puis une table par entité. -->

#### <entité>

| Champ | Type | Obligatoire | Contraintes / valeur par défaut |
|-------|------|-------------|---------------------------------|
| | | | |

### 3.2 Stockage et cycle de vie

<!-- Pour chaque entité ou groupe d'entités : où c'est stocké (local, serveur, quel moteur), durée de conservation, suppression, sauvegarde, évolution du schéma (migrations). -->

| Données | Emplacement | Conservation / suppression | Migration |
|---------|-------------|----------------------------|-----------|
| | | | |

## 4. Flux d'intégration

<!-- Les échanges de données entre l'application et l'extérieur, ou entre ses composants déployés séparément : flux entrants (appels reçus, messages consommés, fichiers déposés), sortants (appels à des API tierces, messages publiés, e-mails, exports) et internes (file de tâches, bus entre services). PAS le déroulé fonctionnel des cas d'usage : il est dans le PRD. Un appel entre deux modules du même processus n'est pas un flux. Un schéma d'ensemble, puis une ligne par flux. « Aucun » si l'application n'échange rien avec l'extérieur. -->

```mermaid
flowchart LR
```

| ID | Flux | Source → cible | Sens | Mode | Déclencheur | Données échangées | Volumétrie / fréquence | Contrat | Besoins PRD |
|----|------|----------------|------|------|-------------|-------------------|------------------------|---------|-------------|
| FL-01 | <nom> | <acteur, composant ou service> → <…> | entrant / sortant / interne | <HTTP synchrone, file (Kafka, RQ…), fichier, e-mail, SQL…> | <action utilisateur, planification, événement> | <nature des données, pas le schéma> | <valeur ou « non connu »> | CTR-xx | CU-xx / ENF-xx |

## 5. Interfaces, contrats et services

### 5.1 Services externes

<!-- Un service externe = une API extérieure au projet que le projet appelle (SaaS, service d'un fournisseur, autre application de l'organisation, moteur appelé par son API HTTP comme Elasticsearch), que l'appel parte du serveur, d'une bibliothèque cliente ou du navigateur. Chacun a son contrat au § 5.2 et sa spécification OpenAPI dans docs/contrats/. Ne sont PAS des services externes : la base de données, le cache, la file, le serveur SMTP, les processus du projet (worker…) — ils vont dans « Infrastructure requise » (§ 11) — ni un CDN de fichiers statiques (§ 6). « Rôle dans le projet » : en une phrase, ce que le service apporte et les cas d'usage qui en dépendent. « Si indisponible » : comportement constaté ou prévu quand il est absent, non configuré ou en erreur. Une colonne n'est pas remplie de « non connu » : une inconnue importante devient une question ouverte. « Aucun » si le projet n'appelle aucune API externe. -->

| Service | Rôle dans le projet | Fournisseur | Authentification | Si indisponible | Contrat | Besoin PRD |
|---------|---------------------|-------------|------------------|-----------------|---------|------------|
| | | | <mécanisme, nom de la variable> | | CTR-xx | CU-xx / EF-xx |

### 5.2 Contrats

<!-- Index des contrats : une ligne par API exposée, API tierce appelée, flux d'événements, ou format de fichier échangé. Le détail (opérations, schémas, erreurs, exemples) n'est PAS écrit ici : il vit dans une spécification machine de docs/contrats/ (OpenAPI 3.1 pour une API HTTP, AsyncAPI 3.0 pour des événements / messages, JSON Schema pour un format de fichier), produite et tenue à jour par le skill /openapi. Chaque service externe (§ 5.1) a aussi sa spécification, limitée aux opérations que le projet utilise (`x-sens: consommé`), pour être importable dans Postman. L'infrastructure (base de données, file, SMTP) n'est pas un contrat, sauf le schéma de la base (type SQL, renvoi aux migrations). « À produire (/openapi) » tant que la spécification n'existe pas. « Aucun » si sans objet. -->

| ID | Contrat | Type | Producteur → consommateurs | Spécification | Versionnement | Flux |
|----|---------|------|----------------------------|---------------|---------------|------|
| CTR-01 | <nom> | API REST / événements / fichier / API tierce / SQL | <composant ou service> → <…> | `docs/contrats/<nom>.openapi.yaml` / À produire (/openapi) / migrations (SQL) | <stratégie de compatibilité> | FL-xx |

## 6. Stack technique

<!-- Version majeure obligatoire pour chaque brique (sinon l'IA choisit). Chaque choix renvoie à une contrainte du PRD (CT-xx) ou à un ADR ; s'il n'est pas tranché : « À décider (ADR attendu) ». -->

| Couche | Choix | Version | Justification |
|--------|-------|---------|---------------|
| | | | CT-xx / ADR-NNNN / À décider (ADR attendu) |

### Choix techniques constatés (projet existant)

<!-- Rempli seulement pour un projet existant documenté par /reverse (`origine: rétro`) : un choix structurant constaté dans le code par ligne (CH-xx de la cartographie), avec sa preuve, en une phrase. C'est un constat, pas une décision : les décisions ont déjà été prises, on ne les rouvre pas et on n'en demande pas la raison (pas de question ouverte, pas d'ADR). Dans un cadrage neuf : « Aucun ». -->

| ID | Choix constaté | Preuve |
|----|----------------|--------|
| CH-01 | | <fichier:ligne> |

## 7. Structure du code

<!-- Arborescence des dossiers attendue et rôle de chaque dossier, découpage en composants (§ 2) / couches, règles de dépendance entre composants. -->

```
<racine>/
```

## 8. Conventions

<!-- Ce que l'IA doit respecter en écrivant le code. « Libre » est une réponse acceptable si l'utilisateur l'a dit. -->

- **Langue du code** (identifiants, commentaires, messages de commit) :
- **Nommage** (fichiers, classes, fonctions, variables) :
- **Style / formatage** (outil, configuration) :
- **Format des erreurs** :
- **Gestion des dépendances** (ajout de bibliothèques autorisé ou non) :

## 9. Comportements transverses

- **Gestion des erreurs** : <!-- remontée, affichage à l'utilisateur, reprise -->
- **Journalisation / observabilité** : <!-- quoi, où, niveau ; « Aucune » si sans objet -->
- **Sécurité** : <!-- authentification, autorisations, secrets, données sensibles -->
- **Configuration** : <!-- paramètres, variables d'environnement, valeurs par défaut -->

## 10. Tests

<!-- Types de tests attendus (unitaires, intégration, bout en bout), outils, ce qui doit obligatoirement être couvert, seuil de couverture éventuel. -->

| Type | Outil | Périmètre obligatoire |
|------|-------|-----------------------|
| | | |

## 11. Déploiement et environnements

<!-- Environnements (dev, test, prod…), build, distribution (store, hébergement, paquet), mise à jour. -->

### Infrastructure requise

<!-- Ce qui doit tourner à côté du code pour que le projet fonctionne : base de données, cache, file de messages, serveur SMTP, processus annexes du projet (worker…). Pas les services externes (API appelées, § 5.1). Une ligne par ressource ; « Lancer en local » donne la commande ou l'option la plus simple constatée dans le dépôt (docker-compose, Procfile…), sinon « non fourni ». « Aucune » si le projet n'a besoin de rien d'autre que lui-même. -->

| Ressource | Rôle | Configuration | Obligatoire | Lancer en local |
|-----------|------|---------------|-------------|-----------------|
| | | <variable d'environnement> | oui / non (effet si absente) | |

## 12. Couverture des exigences non fonctionnelles

| ENF | Comment l'architecture y répond |
|-----|---------------------------------|
| ENF-01 | |

## 13. Contrôles de conception

<!-- Gates à passer par l'architecture (inspirés de la « Phase -1 » de spec-kit). Résultat « passé » ou « écart » ; tout écart est justifié au § 14. -->

| Gate | Question | Résultat | Justification |
|------|----------|----------|---------------|
| Simplicité | Le nombre de composants / projets est-il le minimum nécessaire aux besoins du PRD ? Rien n'est-il anticipé « au cas où » (fonctionnalité, extensibilité, couche) sans besoin PRD ? | passé / écart | |
| Anti-abstraction | Le framework et les API de la plateforme sont-ils utilisés directement, sans couche d'enrobage maison ? Le modèle de données a-t-il une seule représentation ? | passé / écart | |
| Intégration d'abord | Les contrats (§ 5.2) sont-ils définis avant le code (spécifications de docs/contrats/) ? Les tests de contrat et d'intégration sont-ils prévus (§ 10), en environnement réaliste plutôt qu'en simulacres ? | passé / écart | |

## 14. Suivi de la complexité

<!-- Une ligne par écart du § 13. Un écart sans besoin PRD qui le justifie doit être supprimé de l'architecture, pas justifié. « Aucun » si tous les gates sont passés. -->

| Écart | Pourquoi nécessaire (besoin PRD) | Alternative plus simple rejetée car |
|-------|----------------------------------|-------------------------------------|
| | | |

## 15. Questions ouvertes

<!-- Identifiant stable QA-01… 10 questions au maximum, les bloquantes d'abord. Une question tranchée est retirée de la liste et intégrée dans le corps du document. -->

| ID | Question | Bloquante | Origine |
|----|----------|-----------|---------|
| QA-01 | | oui / non | |

## 16. Journal des décisions

<!-- Une ligne par décision de l'utilisateur intégrée au document, la plus récente en bas. Ne jamais supprimer de ligne. -->

| Date | Point | Décision (mots de l'utilisateur) | Impacte |
|------|-------|----------------------------------|---------|
| AAAA-MM-JJ | B1 | | § |
