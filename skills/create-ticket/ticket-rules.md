# Règles de l'étape TICKET (agent scoping)

<!-- Lu par l'agent scoping quand /create-ticket l'invoque (modes ANALYSE et RÉDACTION, étape TICKET). Ces règles complètent celles de l'agent ; là où elles diffèrent, elles l'emportent pour le ticket. -->

Invoquée par `/create-ticket` pour cadrer une **évolution** (feature ou bugfix) sur un projet déjà documenté, cadré ou rétro-documenté. L'approche est **spec-driven** : la demande se cadre en mettant à jour les documents existants (PRD, architecture, ADR, glossaire), puis en créant les US du ticket ; il n'y a pas de document à part. L'orchestrateur te fournit en plus l'**identifiant du ticket** (clé Jira ou `TK-NNN`) et la **demande** (texte exact). Le dernier eval ne porte sur le ticket que si son `etape` vaut `TICKET <ID>` ; sinon, ignore ses points.

**Périmètre.** Tu ne traites que la demande. Tout ce qui est déjà écrit et que la demande ne touche pas reste tel quel ; ne rouvre pas les décisions actées (journaux, ADR acceptés, choix CH-xx) sauf si la demande les remet explicitement en cause.

## En mode ANALYSE

Ton rapport commence par deux sections, avant les sections habituelles (limitées à la demande) :

```
## Type et qualification
- Type : feature | bug — <justification en une phrase>
- Qualification (bug seulement) : écart à la spec (EF-xx / critère « … » existant non respecté : le PRD ne change pas) | cas non spécifié (règle ou critère absent du PRD : à ajouter)

## Impact
- PRD : <identifiants créés (nouveau), modifiés (ce qui change) ou retirés (→ Hors périmètre) ; « aucun »>
- Architecture : <§ et identifiants touchés (composants, entités, flux, contrats § 5.2, stack) ; « aucun »>
- ADR : <nouvelle décision nécessaire (titre), avec le choix existant qu'elle remplace s'il y en a ; « aucun »>
- Glossaire : <termes à ajouter ou modifier ; « aucun »>
- Backlog : <US envisagées (titre, une ligne chacune), US existantes impactées>
```

- **Bug** : relis les EF, critères d'acceptation et RG concernés. Si le comportement attendu y est écrit, c'est un *écart à la spec* : aucune question sur le besoin, seulement sur ce qui manque pour reproduire et vérifier (contexte, données, environnement). S'il n'y est pas, c'est un *cas non spécifié* : le comportement attendu est un point bloquant, avec des options.
- **Feature** : challenge-la comme toute fonctionnalité (à qui elle sert, quel usage concret) et remonte ses conflits avec l'existant (EF, RG, ENF, contraintes CT-xx, ADR) comme contradictions.
- La numérotation des points (B, F, C, X) continue celle des journaux, comme d'habitude.

## En mode RÉDACTION

L'orchestrateur te transmet en plus le type, la qualification et l'impact confirmés. Tu modifies **tous les documents touchés** par le ticket, en une passe. C'est une **exception explicite** à la règle « ne touche pas aux documents validés » :

- **Statuts** : ne change **jamais** le champ `statut` d'un document (ni `brouillon`, ni `validé`). Mets à jour `maj` de chaque document modifié.
- **Modifications** par `Edit` ciblés uniquement, là où l'impact l'exige. Nouvel élément : identifiant suivant le plus grand déjà attribué. Élément modifié : il garde son identifiant, le texte décrit la nouvelle cible. Élément retiré : il passe dans « Hors périmètre » avec son identifiant d'origine. Projet rétro : une cible qui diffère du code remplace la preuve par « (diffère du code actuel : <fichier>:<ligne>) ».
- **PRD** : feature → CU, EF (priorité V1 sauf décision contraire, critères d'acceptation), RG, écrans, ENF selon les décisions. Bug *écart à la spec* → le PRD ne change pas. Bug *cas non spécifié* → ajoute la RG ou le critère d'acceptation tranché.
- **Architecture** : seulement les § touchés (composants, entités, flux, index des contrats § 5.2 — nouveau contrat en « À produire (/openapi) » —, structure du code, tests). Un choix technique structurant tranché → nouvel ADR ; non tranché → « À décider (ADR attendu) » et question ouverte.
- **ADR** : une nouvelle décision donne un ADR `statut: proposé` (gabarit `adr.md`) dont le contexte cite le ticket, ajouté au tableau de `docs/adr/index.md` ; s'il remplace un ADR existant, renseigne « Remplace : ADR-XXXX » dans le nouveau. **N'écris rien dans l'ancien ADR** et ne change le statut d'aucun ADR existant : c'est l'orchestrateur qui passe l'ancien à `remplacé par ADR-NNNN` à la validation du ticket. Un choix CH-xx remplacé (projet rétro) renvoie au nouvel ADR (« remplacé, voir ADR-NNNN (proposé) »).
- **Glossaire** : comme d'habitude.
- **Backlog** : si `.sohub-plugin/backlog.md` n'existe pas, crée-le (gabarit `backlog.md`, `statut: brouillon`). Ajoute les US du ticket à la fin du tableau, au statut **`à cadrer`**, et une story par US (gabarit `story.md`) avec `Type` et `Ticket : <ID>`. Découpage vertical, critères d'acceptation repris des EF ou RG du ticket, plan de tâches parallélisable (voir « Découpage des tâches »). Les US du ticket n'entrent dans « Parallélisation des US » qu'à la validation du ticket (l'orchestrateur les y ajoute alors) : n'y touche pas. **Bug** : une US de type `bug` dont les besoins PRD citent l'EF, le critère ou la RG concerné, et dont la vague 1 écrit un test de non-régression qui échoue tant que le bug existe (contrats ensuite, s'il en faut). Une US existante impactée **`à faire`** est mise à jour et **repasse à `à cadrer`** dans le tableau du backlog, avec une ligne `| <date> | <ID> | US-xxx impactée : repassée à cadrer | US-xxx |` au journal du backlog (l'orchestrateur la remet `à faire` à la validation) ; une US existante `en cours`, `en revue` ou `fait` n'est jamais modifiée : le changement passe par une nouvelle US. Ne change le statut d'aucune autre US existante. Mets à jour la couverture des exigences.
- **Journaux** : dans chaque document modifié, une ligne par décision avec le point préfixé de l'identifiant (`| <date> | <ID>/B1 | <mots de l'utilisateur> | <éléments> |`) ; la demande elle-même se trace par une ligne `| <date> | <ID> | Demande : <résumé fidèle en une phrase> | <éléments> |`.
- **Questions ouvertes** : un point non tranché devient une question ouverte du document concerné, origine `<ID>/<point>`, avec son marqueur `[À CLARIFIER : …]`. Une proposition de ta part reste marquée `*(proposé)*`, même dans un document validé.

Compte rendu (15 lignes au maximum) : fichiers modifiés ou créés ; éléments ajoutés, modifiés, retirés (identifiants) ; US du ticket ; questions ouvertes du ticket (bloquantes d'abord) ; interprétations à vérifier.
