---
depot: <chemin absolu du dépôt>
commit: <branche> / <sha court>
maj: AAAA-MM-JJ HH:MM
structure: proposée
---
<!-- Gabarit de la cartographie d'un projet existant (<dépôt>/.sohub-plugin/reverse/cartographie.md), écrite par l'agent `recherche` en mode CARTOGRAPHIE, qui consolide les trois explorations parallèles (`.sohub-plugin/reverse/exploration/`). Les commentaires HTML sont des consignes : ne pas les recopier.
Règles :
- C'est un INDEX, pas une recopie : il attribue les identifiants, rattache les éléments aux composants et liste ce qu'il faut trancher. Le détail (rôles, relations, sens des termes, versions…) reste dans les fichiers d'exploration, que la rédaction lit directement. Viser 8 Ko au maximum.
- Une ligne par élément, une preuve `chemin/fichier.ext:ligne` (relative au dépôt) et la source dans les explorations (`S` = structure.md, `U` = usages.md, `D` = donnees.md). Pas de preuve → l'élément va dans « Zones d'incertitude ».
- Les identifiants posés ici (CMP-xx, CU-xx, FL-xx, CT-xx, CTR-xx, CH-xx) sont repris tels quels par la rédaction : jamais renumérotés.
- Pas d'ADR ni de décision en rétro-documentation : les choix constatés (CH-xx) vont dans l'architecture (§ 6) comme un constat, sans question sur leur raison.
- `structure` passe de « proposée » à « validée » quand l'orchestrateur reporte les choix de l'utilisateur (section 9).
- Une section sans contenu s'écrit « Aucun ». -->

# Cartographie — <nom du produit>

## 1. Produit observé

<!-- 2 à 3 phrases : ce que fait le produit, son type, les rôles visibles. Ce qui est supposé va en zone d'incertitude. -->

<résumé> — **Nom proposé** : <nom> (<preuve>) — **Périmètre exclu (proposé)** : <tests, migrations, vendored… ou « aucun »>

## 2. Composants

<!-- 4 à 12 composants nommés par leur responsabilité (fusion, découpe ou renommage des communautés du graphe). -->

| ID | Composant | Répertoires / fichiers principaux | Source |
|----|-----------|-----------------------------------|--------|
| CMP-01 | <nom> | <chemins> | S |

## 3. Cas d'utilisation

| ID | Cas d'utilisation | Composant(s) | Preuve | Source |
|----|-------------------|--------------|--------|--------|
| CU-01 | <intention utilisateur> | CMP-xx | <fichier:ligne> | U |

## 4. Entités, contrats et flux d'intégration

<!-- Entités : sans ID (leur nom fait foi). Contrats et flux : sens, type et déclencheur restent dans donnees.md. -->

| ID | Élément | Type | Composant(s) | Preuve | Source |
|----|---------|------|--------------|--------|--------|
| — | <entité> | entité | CMP-xx | <fichier:ligne> | D |
| CTR-01 | <contrat / service> | exposé / consommé | CMP-xx | <fichier:ligne> | D |
| FL-01 | <flux> | entrant / sortant / interne → CTR-xx | CMP-xx | <fichier:ligne> | D |

## 5. Contraintes techniques et choix constatés

| ID | Contrainte ou choix constaté | Preuve | Source |
|----|------------------------------|--------|--------|
| CT-01 | <langage / framework / version…> | <manifeste:ligne> | D |
| CH-01 | <choix structurant visible> | <fichier:ligne> | D |

## 6. Glossaire candidat

<!-- Les termes retenus, séparés par des virgules ; leur sens observé est dans usages.md. Signaler entre parenthèses un synonyme à bannir. -->

<terme>, <terme> (pas « <synonyme> »), …

## 7. Points à signaler

<!-- Fichiers rattachés à deux composants ou à aucun, contradictions entre explorations, écarts code / documentation existante. Une ligne chacun, ou « Aucun ». -->

- <point> — <preuves>

## 8. Zones d'incertitude

<!-- Ce que le code ne dit pas : intentions métier, objectifs, utilisateurs réels, exigences chiffrées, code mort, contradictions. Une ligne par question, fusionnée entre axes, avec l'endroit du doute. -->

- [I-01] <question> — <fichier:ligne ou « général »>

## 9. Structure validée

<!-- Rempli par l'orchestrateur après les choix de l'utilisateur. « En attente » tant que l'utilisateur n'a pas tranché. -->

En attente.
