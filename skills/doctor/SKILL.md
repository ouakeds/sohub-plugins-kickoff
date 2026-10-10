---
name: doctor
description: Vérifie les dépendances du plugin de cadrage (python3 et PyYAML, curl, unzip, Node.js, mermaid-cli et son navigateur headless, linters OpenAPI / AsyncAPI, uv et Code Review Graph, connecteur Atlassian) et installe celles qui manquent, avec l'accord de l'utilisateur. Proposé par /sync quand le rendu des diagrammes est impossible, par /reverse quand Code Review Graph manque, par /openapi quand le linter manque, ou lancé à la main. À utiliser quand l'utilisateur veut vérifier ou installer les dépendances du plugin.
argument-hint: ""
allowed-tools: AskUserQuestion, Bash, Read, ToolSearch
---

Tu diagnostiques et installes les dépendances du plugin. **Chaque installation se fait avec l'accord de l'utilisateur** (`AskUserQuestion`), jamais d'office. Tu n'exécutes **jamais** `sudo` toi-même : quand une commande demande les droits administrateur, donne-la à l'utilisateur pour qu'il la lance avec le préfixe `!` (ex. `! sudo apt-get install -y …`), puis revérifie.

Configuration de rendu : `${CLAUDE_SKILL_DIR}/puppeteer-config.json`

## Règles d'exécution (leçons des installations précédentes)

- **Chaque appel `Bash` repart d'un shell neuf.** nvm ne modifie le `PATH` que du shell courant : préfixe **toute** commande qui utilise `node`, `npm`, `npx` ou `mmdc` par `source ~/.nvm/nvm.sh && …` dès que `~/.nvm/nvm.sh` existe. Ne passe jamais `nvm install` dans un tube (`nvm install --lts | tail`) : il s'exécute alors dans un sous-shell et le `PATH` est perdu ; vérifie `node --version` dans une commande séparée qui recharge nvm.
- **Navigateur de mermaid-cli : toujours la version qu'il attend.** Lance l'installation depuis le dossier de mermaid-cli pour utiliser *son* puppeteer : `source ~/.nvm/nvm.sh && cd "$(npm root -g)/@mermaid-js/mermaid-cli" && npx --yes puppeteer browsers install chrome-headless-shell`. Un `npx puppeteer` lancé ailleurs installe une autre version, que mermaid-cli ne trouvera pas. La version attendue se lit avec `node -e "import('puppeteer-core/internal/revisions.js').then(m=>console.log(m.PUPPETEER_REVISIONS['chrome-headless-shell']))"` (depuis ce même dossier).
- **Sous Linux, puppeteer extrait l'archive avec la commande `unzip`.** Sans elle, le téléchargement réussit mais l'extraction échoue et laisse un dossier vide `~/.cache/puppeteer/chrome-headless-shell/linux-<version>/` ; les essais suivants échouent alors avec « The browser folder … exists but the executable … is missing ». Avant de réessayer, supprime **ce seul dossier** (vérifie d'abord qu'il ne contient pas l'exécutable).
- **Lis les erreurs utiles, pas l'aide.** En cas d'échec, `puppeteer browsers install` affiche son aide complète avant l'erreur : redirige la sortie dans un fichier et filtre les lignes `Error`, `Provider`, `cause` (sans les lignes `at …` de la pile). Les lignes `npm notice` sont sans importance.
- **uv et ses outils s'installent dans `~/.local/bin`**, souvent absent du `PATH` d'un shell neuf : vérifie `uv` et `code-review-graph` par leur chemin complet (`~/.local/bin/uv`, `~/.local/bin/code-review-graph`) s'ils ne sont pas trouvés par leur nom.
- **Regroupe ce qui demande `sudo`** en une seule commande pour l'utilisateur, plutôt qu'une par problème.

## Dépendances

| Dépendance | Sert à | Vérification | Obligatoire |
|---|---|---|---|
| `python3` | hooks de métriques, `/compare`, script de `/sync` | `python3 --version` | oui |
| PyYAML (module Python `yaml`) | lecture des spécifications de `docs/contrats/` (`/openapi`) | `python3 -c "import yaml; print(yaml.__version__)"` | pour les contrats (contournable par `npx js-yaml`) |
| `curl` | dépôt des images et des spécifications sur Confluence (`/sync`), téléchargements | `curl --version` | pour la synchro |
| `unzip` (Linux) | extraction du navigateur par puppeteer | `unzip -v` | pour les diagrammes (contournable, voir 3) |
| Node.js ≥ 18 et `npm` | exécuter mermaid-cli | `node --version`, `npm --version` | pour les diagrammes |
| `mmdc` (`@mermaid-js/mermaid-cli`) | rendu des diagrammes Mermaid en PNG | `mmdc --version` | pour les diagrammes |
| navigateur headless de mermaid-cli (`chrome-headless-shell`, version attendue par mermaid-cli) | rendu effectif | exécutable présent dans `~/.cache/puppeteer/chrome-headless-shell/linux-<version>/chrome-headless-shell-linux64/`, puis rendu de test (voir 4) | pour les diagrammes |
| bibliothèques système du navigateur (Linux) | lancer le navigateur | `ldd <exécutable du navigateur> \| grep "not found"` vide | pour les diagrammes |
| `redocly` (`@redocly/cli`) et `asyncapi` (`@asyncapi/cli`) | validation des spécifications OpenAPI et AsyncAPI (`/openapi`) | `redocly --version`, `asyncapi --version` (ou `npx --yes @redocly/cli --version`) | pour `/openapi` (sinon spécifications non validées) |
| `uv` | installer Code Review Graph | `uv --version` | pour `/reverse` |
| `code-review-graph` (avec l'extra `communities`) | cartographie du code d'un projet existant | `code-review-graph --version` | pour `/reverse` |
| connecteur Atlassian (MCP) | `/sync` | présence d'outils Atlassian (`ToolSearch` « atlassian confluence ») | pour la synchro |

## Procédure

1. **Diagnostic.** Détecte le système (`uname -s`, et `/etc/os-release` sous Linux ; WSL si `uname -r` contient `microsoft`) puis lance toutes les vérifications du tableau (avec nvm rechargé s'il existe). N'installe encore rien. Affiche le diagnostic.
2. **Droits administrateur, en une fois.** Si des paquets système manquent déjà (python3, `python3-yaml`, curl, unzip, et sous Linux les bibliothèques du navigateur si celui-ci est présent — voir 4), donne à l'utilisateur **une seule** commande à lancer avec `!`, par exemple `! sudo apt-get install -y unzip libnss3 libnspr4` (Fedora : `sudo dnf install -y …` ; macOS : `brew install …`), puis revérifie. S'il ne veut pas, continue avec les contournements sans `sudo`.
3. **Installations sans droits administrateur**, dans l'ordre du tableau, pour chaque dépendance manquante ou trop ancienne : propose via `AskUserQuestion` « Installer » (avec la commande exacte) / « Passer ». Commandes :
   - Node.js via nvm : `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash`, puis, dans une **autre** commande, `source ~/.nvm/nvm.sh && nvm install --lts`, puis `source ~/.nvm/nvm.sh && node --version && npm --version`. Sur macOS, `brew install node` est aussi proposé.
   - mermaid-cli : `source ~/.nvm/nvm.sh && npm install -g @mermaid-js/mermaid-cli`. Avec un Node système dont le préfixe global (`npm config get prefix`) n'est pas accessible en écriture : `npm install -g --prefix ~/.local @mermaid-js/mermaid-cli`, et vérifie que `~/.local/bin` est dans le `PATH` (sinon indique la ligne à ajouter au profil du shell).
   - Navigateur : depuis le dossier de mermaid-cli (voir « Règles d'exécution »). Si `unzip` manque et que l'utilisateur n'a pas voulu l'installer, **contournement sans `sudo`** : télécharge `https://storage.googleapis.com/chrome-for-testing-public/<version>/linux64/chrome-headless-shell-linux64.zip` avec `curl -sSfL` dans un dossier temporaire et extrais-le avec `python3` (`zipfile`) dans `~/.cache/puppeteer/chrome-headless-shell/linux-<version>/`, en restaurant les permissions de chaque fichier (`os.chmod(chemin, (info.external_attr >> 16) & 0o777)`) ; vérifie que l'exécutable est présent et exécutable, puis supprime l'archive.
   - PyYAML : sous Debian / Ubuntu, le paquet système `python3-yaml` (à grouper avec les autres paquets de l'étape 2) ; sinon `python3 -m pip install --user pyyaml`.
   - Linters de spécifications : `source ~/.nvm/nvm.sh && npm install -g @redocly/cli @asyncapi/cli` (même règle de préfixe que mermaid-cli).
   - uv : `curl -LsSf https://astral.sh/uv/install.sh | sh` (installe `uv` et `uvx` dans `~/.local/bin`, sans droits administrateur).
   - Code Review Graph : `~/.local/bin/uv tool install "code-review-graph[communities]"` (l'extra `communities` apporte la détection des communautés, indispensable à la cartographie) ; pour le mettre à jour : `~/.local/bin/uv tool upgrade code-review-graph`. N'exécute **jamais** `code-review-graph install` : cette commande enregistre un serveur MCP dans les outils de l'utilisateur, le plugin n'utilise que la ligne de commande.
   - Connecteur Atlassian : il ne s'installe pas en ligne de commande. S'il manque, indique qu'il faut connecter Atlassian dans Claude ; s'il n'expose qu'un outil `authenticate`, lance-le et donne le lien d'autorisation.
   Après chaque installation, relance la vérification correspondante ; en cas d'échec, montre les lignes d'erreur utiles et passe à la suite.
4. **Bibliothèques du navigateur (Linux / WSL).** Lance `ldd <exécutable du navigateur> | grep "not found"` : ne demande que les paquets qui correspondent aux bibliothèques réellement manquantes, regroupés en une commande `! sudo apt-get install -y …`. Correspondances (Debian / Ubuntu) :

   | Bibliothèque manquante | Paquet |
   |---|---|
   | `libnspr4.so` | `libnspr4` |
   | `libnss3.so`, `libnssutil3.so`, `libsmime3.so` | `libnss3` |
   | `libasound.so.2` | `libasound2t64` (Ubuntu ≥ 24.04), sinon `libasound2` |
   | `libatk-1.0.so.0` | `libatk1.0-0t64` (Ubuntu ≥ 24.04), sinon `libatk1.0-0` |
   | `libatk-bridge-2.0.so.0` | `libatk-bridge2.0-0t64` (Ubuntu ≥ 24.04), sinon `libatk-bridge2.0-0` |
   | `libcups.so.2` | `libcups2t64` (Ubuntu ≥ 24.04), sinon `libcups2` |
   | `libgbm.so.1` | `libgbm1` |
   | `libdrm.so.2` | `libdrm2` |
   | `libxkbcommon.so.0` | `libxkbcommon0` |
   | `libXcomposite.so.1`, `libXdamage.so.1`, `libXfixes.so.3`, `libXrandr.so.2` | `libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxrandr2` |
   | `libpango-1.0.so.0`, `libcairo.so.2` | `libpango-1.0-0`, `libcairo2` |

   Une bibliothèque absente du tableau : cherche son paquet avec `apt-file search <bibliothèque>` s'il est disponible, sinon donne son nom à l'utilisateur. Après l'installation, relance `ldd` jusqu'à ce que la liste soit vide.
5. **Rendu de test** (si `mmdc` répond) : dans un dossier temporaire (`mktemp -d`), écris `graph LR; A-->B` dans `test.mmd`, puis lance `source ~/.nvm/nvm.sh && mmdc -i test.mmd -o test.png -b white -s 2 -p <configuration de rendu>` et vérifie que `test.png` existe et n'est pas vide. Si le rendu échoue : « Could not find Chrome » → navigateur (étape 3) ; « error while loading shared libraries » → bibliothèques (étape 4) ; puis relance le rendu de test. Supprime le dossier temporaire à la fin.
6. **Bilan** : un tableau dépendance → état (`OK` + version, `installé`, `manquant`, `passé`) et, pour chaque manque, ce qu'il empêche (ex. « diagrammes publiés en bloc de code par /sync »), avec la commande exacte qui reste à lancer. Si uv a été installé et que `~/.local/bin` n'est pas dans le `PATH`, indique la ligne à ajouter au profil du shell. Si nvm a été installé, rappelle qu'un nouveau terminal (ou `source ~/.nvm/nvm.sh`) est nécessaire pour que `node` et `mmdc` soient trouvés en dehors de cette session.
