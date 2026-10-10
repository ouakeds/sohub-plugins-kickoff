---
statut: brouillon
maj: AAAA-MM-JJ HH:MM
sources: Aucune
---
<!-- Gabarit PRD. Les commentaires HTML sont des consignes de rédaction : ne pas les recopier dans le document final.
Règles :
- N'écrire que ce que l'utilisateur a dit ou tranché ; tout le reste va dans « Questions ouvertes ».
- Marqueur en ligne : à l'endroit exact du texte concerné par un point non tranché, écrire [À CLARIFIER : Q-xx], en plus de la ligne Q-xx dans « Questions ouvertes ». Le marqueur est retiré quand la question est tranchée.
- Une section sans contenu tranché s'écrit « Aucun » (exclu explicitement) ou renvoie vers une question ouverte (« Voir Q-03 »). Jamais de ligne de tableau vide.
- Identifiants (CU, EF, ENF, RG, EC, Q) : jamais renumérotés ni réutilisés. Une exigence supprimée passe dans « Hors périmètre » en gardant son identifiant.
- `maj` : date et heure de la dernière rédaction, fournies par l'orchestrateur.
- Concision : une exigence = un comportement, en une à deux phrases ; un critère d'acceptation par comportement vérifiable, pas une paraphrase du code. Pas de détail technique (routes, classes, tables) : il relève de l'architecture.
- Projet existant (`origine: rétro`) : une preuve `fichier:ligne` par élément (CU, EF, RG, écran), à la fin de son bloc ou dans sa ligne de tableau — pas une par phrase. Les chemins de fichiers s'écrivent entre accents graves (`app/__init__.py:31`).
- Questions ouvertes : 10 au maximum, les bloquantes d'abord ; ne garder que celles dont la réponse changerait le produit.
- `sources` : documents existants fournis par l'utilisateur (diagrammes, specs, notes…), une liste YAML de chemins absolus (fichiers ou dossiers) ; « Aucune » s'il n'y en a pas. Un contenu repris d'une source est tracé au journal par une ligne `SOURCE`. -->

# PRD — <nom du projet>

## 1. Problème et contexte

<!-- Quel problème concret on résout, pour qui, et pourquoi maintenant. Situation actuelle de l'utilisateur sans l'application. -->

## 2. Objectifs et critères de succès

<!-- À quoi on saura que le produit remplit son rôle. Chaque objectif a un critère observable (pas « les utilisateurs sont contents »). -->

| ID | Objectif | Critère de succès observable |
|----|----------|------------------------------|
| OBJ-01 | | |

## 3. Contraintes imposées

<!-- Ce que l'utilisateur impose avant toute réflexion d'architecture : technologie, plateforme, budget, délai, taille de l'équipe, hébergement, licence… « Aucune » si l'utilisateur n'en impose pas. Ces contraintes s'imposent ensuite à l'architecture et aux ADR. -->

| ID | Contrainte | Raison donnée par l'utilisateur |
|----|------------|---------------------------------|
| CT-01 | | |

## 4. Utilisateurs cibles

<!-- Un bloc par type d'utilisateur. -->

### <type d'utilisateur>

- **Qui** :
- **Situation d'usage** : <!-- où, quand, sur quel appareil -->
- **Ce qu'il cherche à accomplir** :

## 5. Cas d'usage

<!-- Un bloc par cas d'usage. Identifiant stable CU-01, CU-02… Le cas d'usage raconte le parcours ; en cas d'écart avec une exigence fonctionnelle, c'est l'exigence (EF) qui fait foi. -->

### CU-01 — <titre>

- **Acteur** :
- **Déclencheur** :
- **Déroulé** :
  1.
- **Résultat attendu** :
- **Variantes / erreurs** :
- **Écrans concernés** : <!-- EC-xx -->

## 6. Exigences fonctionnelles

<!-- Récapitulatif puis un bloc par exigence. Identifiant stable EF-01… Chaque exigence renvoie à au moins un cas d'usage.
Priorité : « V1 » (à développer) ou « Plus tard » (ne PAS développer ; à garder en tête pour ne pas fermer la porte). Rien d'autre. -->

| ID | Exigence | Cas d'usage | Priorité |
|----|----------|-------------|----------|
| EF-01 | | CU-01 | V1 / Plus tard |

### EF-01 — <titre>

- **Description** :
- **Critères d'acceptation** : <!-- vérifiables, un par ligne, au format Étant donné / Quand / Alors. Pas de « rapide », « simple », « intuitif ». -->
  - Étant donné … Quand … Alors …

## 7. Interface et écrans

<!-- Ce que l'utilisateur voit. Sans cette section, l'IA invente tout le rendu. « Aucune interface » si le produit n'en a pas (API, CLI…) — préciser alors le format des entrées/sorties. -->

### 7.1 Navigation

<!-- Écran de départ, enchaînement des écrans (schéma mermaid si utile). -->

### 7.2 Écrans

<!-- Un bloc par écran. Identifiant stable EC-01… -->

#### EC-01 — <nom de l'écran>

- **But** :
- **Contenu affiché** : <!-- informations, éléments, ordre -->
- **Actions possibles** : <!-- chaque action → EF-xx et écran ou effet résultant -->
- **États** :
  - Vide :
  - Chargement :
  - Erreur :
  - Nominal :
- **Exigences couvertes** : <!-- EF-xx -->

### 7.3 Textes et messages

<!-- Textes exacts imposés par l'utilisateur (libellés, messages d'erreur, notifications), ton général, langue(s). Ce qui n'est pas imposé : le dire explicitement (« libellés libres sauf ci-dessous »). -->

| Contexte | Texte exact |
|----------|-------------|
| | |

### 7.4 Charte visuelle

<!-- Exigences visuelles tranchées (thème clair/sombre, couleurs, maquettes de référence…) ou « libre ». -->

## 8. Exigences non fonctionnelles

<!-- Identifiant ENF-01… Toujours une valeur précise : un chiffre quand c'est mesurable (« démarrage < 2 s sur <appareil> »), une liste fermée sinon (« iOS 17+ et Android 13+ »).
Thèmes à couvrir : plateformes et versions, distribution (stores, web, installation), performance, disponibilité / hors ligne, données et persistance, comptes et authentification, sécurité et confidentialité, RGPD et aspects légaux, analytics / télémétrie, accessibilité, langues, notifications.
Un thème explicitement sans objet s'écrit avec la valeur « Aucun ». Un thème non tranché va dans « Questions ouvertes ». -->

| ID | Thème | Exigence | Valeur précise |
|----|-------|----------|----------------|
| ENF-01 | | | |

## 9. Règles métier et cas limites

<!-- Règles de gestion, valeurs par défaut explicites, comportements aux limites (vide, maximum, interruption, erreur réseau…). Identifiant RG-01… Chaque règle indique où elle s'applique. -->

| ID | Règle | S'applique à |
|----|-------|--------------|
| RG-01 | | CU-xx / EF-xx |

## 10. Hors périmètre

<!-- Ce qui est explicitement exclu (y compris les fonctionnalités écartées pendant le cadrage et les exigences supprimées, avec leur identifiant d'origine), et pourquoi. -->

| Élément exclu | Identifiant d'origine | Raison |
|---------------|-----------------------|--------|
| | | |

## 11. Glossaire

<!-- Le vocabulaire du projet est tenu dans un document unique, docs/glossaire.md (gabarit glossaire.md) : chaque terme métier utilisé ici y est défini. Ne pas recopier de définition dans le PRD. -->

Voir [Glossaire](glossaire.md).

## 12. Questions ouvertes

<!-- Tout ce qui n'est pas encore tranché, 10 questions au maximum, les bloquantes d'abord. Identifiant stable Q-01… Une question tranchée est RETIRÉE de cette liste : sa réponse est intégrée dans le corps du document et tracée dans le journal des décisions. -->

| ID | Question | Bloquante | Origine |
|----|----------|-----------|---------|
| Q-01 | | oui / non | <!-- point de cadrage (B2, F1…) ou d'eval (E-007) --> |

## 13. Journal des décisions

<!-- Une ligne par décision de l'utilisateur intégrée au document, la plus récente en bas. Ne jamais supprimer de ligne. Permet de vérifier que rien n'a été inventé. Un contenu repris d'un document source s'inscrit avec le point `SOURCE` : « Repris de <fichier> ». -->

| Date | Point | Décision (mots de l'utilisateur) | Impacte |
|------|-------|----------------------------------|---------|
| AAAA-MM-JJ | B1 | | EF-xx, RG-xx |
