#!/usr/bin/env python3
"""Condense le graphe Code Review Graph d'un dépôt en un digest Markdown.

Usage : graph_digest.py <dépôt> <fichier de sortie .md> [--max N]

Lit <dépôt>/.code-review-graph/graph.db (SQLite, schéma code-review-graph ≥ 2.3)
en lecture seule, avec la seule bibliothèque standard. Les chemins sont rendus
relatifs au dépôt. Le digest sert d'entrée à l'agent `researcher` (modes
EXPLORATION et CARTOGRAPHIE) : il dit où regarder, pas ce que fait le produit,
et répartit les fichiers à lire entre les trois axes d'exploration. Les points
d'entrée que le graphe ne voit pas (routes Express, Django `urls.py`, Flask) sont
lus dans le texte des fichiers.
"""
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

SKIP_DIRS = {".git", ".code-review-graph", ".sohub-plugin", "node_modules", "venv", ".venv", "env", "vendor",
             "__pycache__", "dist", "build", "target", ".idea", ".vscode", ".mypy_cache", ".pytest_cache", ".tox",
             "staticfiles", ".next", "coverage", ".terraform"}
SKIP_EXT = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".eot", ".mo",
            ".lock", ".map", ".min.js", ".zip", ".gz", ".jar", ".class", ".so", ".dll", ".exe", ".pdf"}
# Lecture de variables d'environnement : seul le NOM est capturé, jamais une valeur.
ENV_RE = re.compile(r"""(?:os\.environ(?:\.get)?\s*[\[(]\s*|os\.getenv\(\s*|getenv\(\s*|process\.env\.|"""
                    r"""process\.env\[\s*|System\.getenv\(\s*|ENV\[\s*|env\(\s*)['"]?([A-Z][A-Z0-9_]{2,})""")
# Shell, docker-compose, CI : $VAR et ${VAR} (seulement dans ces fichiers : ailleurs, ${X} est un gabarit de code)
SHELL_ENV_RE = re.compile(r"\$\{?([A-Z][A-Z0-9_]{2,})")
# Dockerfile : ENV X=… / ENV X … / ARG X
DOCKER_ENV_RE = re.compile(r"^\s*(ENV|ARG)\s+(.*)", re.I)
SHELL_FILE_RE = re.compile(r"\.(sh|bash|zsh|ya?ml|env|ini|conf|cfg)$|(^|/)(\.env[^/]*|dockerfile[^/]*|containerfile|"
                           r"makefile|procfile|jenkinsfile|docker-compose[^/]*|[^/.]+)$", re.I)
DOCKER_FILE_RE = re.compile(r"(^|/)(dockerfile|containerfile)[^/]*$", re.I)
# .env, .env.example… : X=… (nom seulement)
DOTENV_RE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]{2,})\s*=")
DOTENV_FILE_RE = re.compile(r"(^|/)\.env[^/]*$")
SHELL_BUILTINS = {"HOME", "PATH", "PWD", "OLDPWD", "USER", "SHELL", "IFS", "UID", "RANDOM", "LINENO", "HOSTNAME"}
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}

ROUTE_RE = re.compile(r"(route|get|post|put|patch|delete|api_view|endpoint|"
                      r"mapping|command|group|task|subscribe|listener|consumer|"
                      r"handler|errorhandler|on_event|websocket|cli)", re.I)


DATA_RE = re.compile(r"(^|/)(models?|schemas?|serializers?|entit(y|ies)|migrations?|alembic|repositor(y|ies)|dao|db|database|"
                     r"config|settings|email|mail|search|clients?|tasks?|workers?|celery|queues?|jobs?|translat\w*|"
                     r"requirements[^/]*\.txt|pyproject\.toml|setup\.(py|cfg)|package\.json|pom\.xml|build\.gradle|"
                     r"go\.mod|cargo\.toml|gemfile|composer\.json|dockerfile|docker-compose[^/]*|procfile|"
                     r"\.env\.example|\.flaskenv|[^/]*\.ya?ml|[^/]*\.sql)(\.\w+)?(/|$)", re.I)
USAGE_RE = re.compile(r"(^|/)(routes?|routers?|urls|views?|admin|controllers?|handlers?|endpoints?|api|forms?|cli|commands?|templates?|"
                      r"pages?|screens?|tests?|spec|readme[^/]*)(\.\w+)?(/|$)|\.(html|jinja2?|vue|svelte|tsx|jsx)$", re.I)


SCREEN_RE = re.compile(r"\.(html|jinja2?|vue|svelte|tsx|jsx)$", re.I)
# Documentation du cadrage déjà écrite par le plugin : jamais à explorer.
OWN_DOCS_RE = re.compile(r"^docs/(prd|architecture|glossaire)\.md$|^docs/(adr|contrats|eval|stories)/")
# .env réel (secrets) jamais à lire ; .env.example / .sample / .template restent visibles
NOT_READ_RE = re.compile(r"(^|/)(license|licence|copying)[^/]*$|\.(po|pot)$|(^|/)\.(ds_store|gitkeep|keep)$|"
                         r"(^|/)\.env(\.(?!(example|sample|template|dist)$)[^/]*)?$", re.I)
# Points d'entrée lus dans le texte quand le graphe n'en donne pas (Express, Django, Flask)
EXPRESS_RE = re.compile(r"\b(app|router|server|api|\w+Router)\.(get|post|put|patch|delete|all|use)\(\s*(['\"`])([^'\"`]*)\3")
DJANGO_RE = re.compile(r"\b(re_path|path)\(\s*r?(['\"])([^'\"]*)\2")
FLASK_RE = re.compile(r"^\s*@(\w+)\.(route|get|post|put|patch|delete)\(\s*(['\"])([^'\"]*)\3")
JS_EXT = (".js", ".mjs", ".cjs", ".ts", ".mts", ".cts")


def env_names(path, line):
    """Noms des variables d'environnement lues sur une ligne du fichier `path` (relatif au dépôt)."""
    names = [m.group(1) for m in ENV_RE.finditer(line)]
    if SHELL_FILE_RE.search(path):
        names += [n for n in SHELL_ENV_RE.findall(line) if n not in SHELL_BUILTINS]
    if DOTENV_FILE_RE.search(path):
        names += DOTENV_RE.findall(line)
    if DOCKER_FILE_RE.search(path):
        m = DOCKER_ENV_RE.match(line)
        if m:
            rest = m.group(2).strip()
            if "=" in rest.split(" ", 1)[0]:  # ENV X=1 Y=2, ARG X=défaut
                names += re.findall(r"(?:^|\s)([A-Z][A-Z0-9_]{2,})=", rest)
            else:  # ARG X, ENV X valeur
                names += re.findall(r"^([A-Z][A-Z0-9_]{2,})\b", rest)
    return list(dict.fromkeys(names))


def text_entries(path, line):
    """Points d'entrée d'une ligne de code : (route, déclencheur), selon le type de fichier."""
    found = []
    if path.endswith(JS_EXT):
        found += [(m.group(4) or "/", f"{m.group(1)}.{m.group(2)}") for m in EXPRESS_RE.finditer(line)]
    if path.endswith(".py"):
        if os.path.basename(path) == "urls.py":
            found += [(m.group(3) or "/", m.group(1)) for m in DJANGO_RE.finditer(line)]
        found += [(m.group(4) or "/", f"@{m.group(1)}.{m.group(2)}") for m in FLASK_RE.finditer(line)]
    return found


def skipped(path):
    """Chemin sous un répertoire ignoré (dépendances, générés, dossiers cachés d'outils)."""
    return any(p in SKIP_DIRS or p.endswith(".egg-info") for p in path.split("/")[:-1])


def axis_of(path, entry_files, env_files):
    """Axe d'exploration qui lit ce fichier : DONNEES, USAGES ou STRUCTURE (le reste)."""
    if SCREEN_RE.search(path) and not re.search(r"(^|/)e?mails?/", path, re.I):
        return "USAGES"
    if DATA_RE.search(path):
        return "DONNEES"
    if path in entry_files or USAGE_RE.search(path):
        return "USAGES"
    if path in env_files:
        return "DONNEES"
    return "STRUCTURE"


def main():
    args = sys.argv[1:]
    maxn = 15
    if "--max" in args:
        i = args.index("--max")
        if i + 1 >= len(args) or not args[i + 1].isdigit() or int(args[i + 1]) < 1:
            print("--max attend un entier positif.\n" + __doc__, file=sys.stderr)
            sys.exit(2)
        maxn = int(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    repo = os.path.abspath(args[0])
    out = args[1]
    db = os.path.join(os.environ.get("CRG_DATA_DIR") or os.path.join(repo, ".code-review-graph"), "graph.db")
    if not os.path.exists(db):
        sys.exit(f"graphe introuvable : {db} (lancer `code-review-graph build`)")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    q = lambda sql, *p: con.execute(sql, p).fetchall()

    def tables():
        return {r[0] for r in q("select name from sqlite_master where type='table'")}

    tbl = tables()
    meta = {r["key"]: r["value"] for r in q("select key, value from metadata")} if "metadata" in tbl else {}
    root = meta.get("repo_root") or repo

    def rel(path):
        if not path:
            return path
        file, sep, sym = path.partition("::")
        for base in (root, repo):
            if file.startswith(base.rstrip("/") + "/"):
                file = file[len(base.rstrip("/")) + 1:]
                break
        return file + sep + sym

    nodes = {r["id"]: r for r in q("select * from nodes")}
    by_qn = {r["qualified_name"]: r for r in nodes.values()}

    def loc(n):
        return f"{rel(n['file_path'])}:{n['line_start']}" if n["line_start"] else rel(n["file_path"])

    def label(qn):
        n = by_qn.get(qn)
        if not n:
            return qn
        return f"`{n['parent_name'] + '.' if n['parent_name'] and n['kind'] != 'File' else ''}{n['name']}`"

    L = []
    w = L.append

    # --- En-tête et chiffres
    kinds = Counter(n["kind"] for n in nodes.values())
    langs = Counter(n["language"] for n in nodes.values() if n["kind"] == "File" and n["language"])
    edges = Counter({r[0]: r[1] for r in q("select kind, count(*) from edges group by kind")})
    w("# Digest du graphe de code")
    w("")
    w(f"- Dépôt : `{repo}`")
    w(f"- Branche / commit : {meta.get('git_branch', '?')} / {meta.get('git_head_sha', '?')[:12]}")
    w(f"- Graphe construit le : {meta.get('last_updated', '?')} (code-review-graph, schéma {meta.get('schema_version', '?')})")
    w(f"- Fichiers : {kinds.get('File', 0)} · classes : {kinds.get('Class', 0)} · fonctions : {kinds.get('Function', 0)}"
      f" · types : {kinds.get('Type', 0)} · tests : {kinds.get('Test', 0)}")
    w(f"- Langages (fichiers) : " + ", ".join(f"{k} {v}" for k, v in langs.most_common()))
    w(f"- Arêtes : " + ", ".join(f"{k} {v}" for k, v in edges.most_common()))
    w("")
    w("Les chemins sont relatifs au dépôt ; `fichier:ligne` pointe le début du symbole.")
    w("")

    # --- Arborescence (répertoires, par nombre de symboles)
    dirs = defaultdict(lambda: [set(), 0])
    for n in nodes.values():
        d = os.path.dirname(rel(n["file_path"])) or "."
        dirs[d][0].add(rel(n["file_path"]))
        if n["kind"] != "File":
            dirs[d][1] += 1
    w("## Arborescence")
    w("")
    w("| Répertoire | Fichiers | Symboles |")
    w("|---|---|---|")
    for d in sorted(dirs):
        w(f"| `{d}` | {len(dirs[d][0])} | {dirs[d][1]} |")
    w("")

    # --- Points d'entrée (décorateurs de routes, commandes, handlers) et main
    entries = []
    for n in nodes.values():
        try:
            extra = json.loads(n["extra"] or "{}")
        except ValueError:
            extra = {}
        decos = [d for d in extra.get("decorators", []) if ROUTE_RE.search(d)]
        if decos:
            entries.append((loc(n), n["name"], "; ".join(decos), (extra.get("docstring") or n["docstring"] or "")[:80]))
        elif n["name"] in ("main", "__main__") and n["kind"] == "Function":
            entries.append((loc(n), n["name"], "main", ""))

    # --- Parcours du dépôt : fichiers hors graphe, variables d'environnement, et points d'entrée lus dans le
    # texte (Express, Django, Flask) des fichiers où le graphe n'a trouvé aucun décorateur
    graphed = {rel(n["file_path"]) for n in nodes.values() if n["kind"] == "File"}
    deco_files = {e[0].rsplit(":", 1)[0] for e in entries if e[2] != "main"}
    others = defaultdict(list)
    env = defaultdict(set)
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            r = os.path.relpath(full, repo).replace(os.sep, "/")
            low = fn.lower()
            if any(low.endswith(e) for e in SKIP_EXT):
                continue
            if r not in graphed:
                others[os.path.dirname(r) or "."].append(fn)
            try:
                if os.path.getsize(full) > 512_000:
                    continue
                with open(full, encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        for name in env_names(r, line):
                            if len(env[name]) < 3:
                                env[name].add(f"{r}:{i}")
                        if r not in deco_files:
                            entries += [(f"{r}:{i}", route, trig, "") for route, trig in text_entries(r, line)]
            except OSError:
                pass
    w(f"## Points d'entrée ({len(entries)})")
    w("")
    if entries:
        w("| Symbole | Emplacement | Déclencheur | Docstring |")
        w("|---|---|---|---|")
        for l, name, deco, doc in sorted(entries)[:maxn * 6]:
            w(f"| `{name}` | {l} | `{deco.replace('|', '/')}` | {doc.replace('|', '/')} |")
        if len(entries) > maxn * 6:
            w("")
            w(f"… {len(entries) - maxn * 6} autres points d'entrée (chercher les décorateurs et les routes dans le code).")
    else:
        w("Aucun décorateur de route ou de commande ni aucune route Express, Django ou Flask reconnus : chercher les points "
          "d'entrée dans les manifestes et la configuration.")
    w("")

    # --- Communautés
    comm = q("select * from communities order by size desc") if "communities" in tbl else []
    summ = {r["community_id"]: r for r in q("select * from community_summaries")} if "community_summaries" in tbl else {}
    members = defaultdict(list)
    for n in nodes.values():
        if n["community_id"] is not None:
            members[n["community_id"]].append(n)
    w(f"## Communautés ({len(comm)})")
    w("")
    w("Regroupements de symboles fortement liés (algorithme de Leiden). Candidats de composants, à fusionner ou renommer.")
    w("")
    shown = [c for c in comm if members.get(c["id"])]
    for c in shown[:maxn * 3]:
        ms = members[c["id"]]
        files = Counter(rel(m["file_path"]) for m in ms)
        key = []
        s = summ.get(c["id"])
        if s:
            try:
                key = json.loads(s["key_symbols"] or "[]")
            except ValueError:
                key = []
        w(f"### {c['name']} (id {c['id']}, {c['size']} symboles, cohésion {float(c['cohesion'] or 0):.2f})")
        w("")
        w("- Fichiers : " + ", ".join(f"`{f}` ({k})" for f, k in files.most_common(8))
          + (f", … (+{len(files) - 8})" if len(files) > 8 else ""))
        if key:
            w("- Symboles clés : " + ", ".join(f"`{k}`" for k in key[:8]))
        w("- Membres : " + ", ".join(f"`{m['name']}` ({loc(m)})" for m in sorted(ms, key=lambda m: (m['file_path'], m['line_start'] or 0))[:maxn])
          + (f", … (+{len(ms) - maxn})" if len(ms) > maxn else ""))
        w("")

    if len(shown) > maxn * 3:
        w("Autres communautés (petites) : " + ", ".join(f"{c['name']} ({c['size']})" for c in shown[maxn * 3:]))
        w("")

    # --- Couplage entre communautés (appels résolus)
    cid = {qn: n["community_id"] for qn, n in by_qn.items()}
    cname = {c["id"]: c["name"] for c in comm}
    pairs = Counter()
    for r in q("select source_qualified s, target_qualified t from edges where kind in ('CALLS','REFERENCES','INHERITS')"):
        a, b = cid.get(r["s"]), cid.get(r["t"])
        if a is not None and b is not None and a != b:
            pairs[(a, b)] += 1
    w("## Dépendances entre communautés")
    w("")
    if pairs:
        w("| De | Vers | Liens |")
        w("|---|---|---|")
        for (a, b), k in pairs.most_common(maxn * 2):
            w(f"| {cname.get(a, a)} | {cname.get(b, b)} | {k} |")
    else:
        w("Aucune.")
    w("")

    # --- Flux d'exécution
    flows = q("select * from flows order by criticality desc") if "flows" in tbl else []
    trivial = [f for f in flows if (f["node_count"] or 0) <= 2]
    flows = [f for f in flows if (f["node_count"] or 0) > 2]
    w(f"## Flux d'exécution ({len(flows)} à plusieurs étapes, par criticité)")
    w("")
    for f in flows[:maxn * 2]:
        try:
            path = json.loads(f["path_json"])
        except ValueError:
            path = []
        steps = [nodes[i] for i in path if i in nodes]
        entry = nodes.get(f["entry_point_id"])
        w(f"- **{f['name']}** (criticité {float(f['criticality'] or 0):.2f}, {f['node_count']} symboles, {f['file_count']} fichiers)"
          + (f" — entrée {loc(entry)}" if entry else ""))
        if steps:
            w("  - " + " → ".join(f"`{s['name']}`" for s in steps[:10]) + (" → …" if len(steps) > 10 else ""))
    if len(flows) > maxn * 2:
        w(f"- … {len(flows) - maxn * 2} autres flux (`code-review-graph flows`).")
    if trivial:
        w("")
        w(f"Flux à une seule étape ({len(trivial)}) : " + ", ".join(
            f"`{f['name']}`" + (f" ({loc(nodes[f['entry_point_id']])})" if f["entry_point_id"] in nodes else "")
            for f in trivial[:maxn * 3]) + (" …" if len(trivial) > maxn * 3 else ""))
    w("")

    # --- Hubs (symboles les plus appelés)
    deg_in = Counter()
    deg_out = Counter()
    for r in q("select source_qualified s, target_qualified t from edges where kind='CALLS'"):
        if r["t"] in by_qn:
            deg_in[r["t"]] += 1
        if r["s"] in by_qn:
            deg_out[r["s"]] += 1
    w("## Symboles les plus sollicités")
    w("")
    w("| Symbole | Emplacement | Appelé par | Appelle |")
    w("|---|---|---|---|")
    for qn, k in deg_in.most_common(maxn):
        n = by_qn[qn]
        if n["is_test"]:
            continue
        w(f"| {label(qn)} | {loc(n)} | {k} | {deg_out.get(qn, 0)} |")
    w("")

    # --- Héritage (modèles, formulaires, bases)
    inh = Counter()
    inh_ex = defaultdict(list)
    for r in q("select source_qualified s, target_qualified t from edges where kind='INHERITS'"):
        base = r["t"].split("::")[-1]
        inh[base] += 1
        if r["s"] in by_qn:
            inh_ex[base].append(by_qn[r["s"]])
    w("## Héritage (classes de base les plus étendues)")
    w("")
    for base, k in inh.most_common(maxn):
        w(f"- `{base}` ← " + ", ".join(f"`{n['name']}` ({loc(n)})" for n in inh_ex[base][:6])
          + (f", … (+{k - 6})" if k > 6 else ""))
    if not inh:
        w("Aucun.")
    w("")

    # --- Dépendances externes (imports non résolus = bibliothèques)
    ext = Counter()
    for r in q("select target_qualified t, extra from edges where kind='IMPORTS_FROM'"):
        if r["t"] in by_qn or os.path.isabs(r["t"]):
            continue
        try:
            extra = json.loads(r["extra"] or "{}")
        except ValueError:
            extra = {}
        if extra.get("import_resolution", "unresolved") == "resolved":
            continue
        mod = (extra.get("python_module") or r["t"]).lstrip(".").split("/")[0].split(".")[0]
        if mod:
            ext[mod] += 1
    w("## Bibliothèques importées (hors dépôt)")
    w("")
    third = [(m, k) for m, k in ext.most_common() if m not in STDLIB]
    std = [m for m, _ in ext.most_common() if m in STDLIB]
    w("- Tierces (clients de services externes probables : BD, cache, file, recherche, e-mail, API) : "
      + (", ".join(f"`{m}` ({k})" for m, k in third[:maxn * 3]) or "aucune"))
    if std:
        w("- Bibliothèque standard : " + ", ".join(f"`{m}`" for m in std))
    w("")

    # --- Tests et risques
    tested = {r[0] for r in q("select distinct source_qualified from edges where kind='TESTED_BY'")}
    funcs = [n for n in nodes.values() if n["kind"] in ("Function", "Class") and not n["is_test"]]
    untested = [n for n in funcs if n["qualified_name"] not in tested]
    w("## Tests et zones à risque")
    w("")
    w(f"- Symboles testés : {len(funcs) - len(untested)} / {len(funcs)}")
    if "risk_index" in tbl:
        risky = q("select qualified_name, risk_score, caller_count, test_coverage, security_relevant from risk_index "
                  "order by risk_score desc limit ?", maxn)
        if risky:
            w("")
            w("| Symbole | Emplacement | Risque | Appelants | Couverture | Sécurité |")
            w("|---|---|---|---|---|---|")
            for r in risky:
                n = by_qn.get(r["qualified_name"])
                w(f"| {label(r['qualified_name'])} | {loc(n) if n else '?'} | {float(r['risk_score'] or 0):.2f} | {r['caller_count']}"
                  f" | {r['test_coverage']} | {'oui' if r['security_relevant'] else ''} |")
    w("")

    # --- Gros symboles
    big = sorted((n for n in funcs if n["line_start"] and n["line_end"]),
                 key=lambda n: n["line_end"] - n["line_start"], reverse=True)[:maxn]
    w("## Plus gros symboles")
    w("")
    for n in big:
        w(f"- `{n['name']}` ({n['kind']}, {n['line_end'] - n['line_start'] + 1} lignes) — {loc(n)}")
    w("")

    # --- Fichiers hors graphe (parcourus avant les points d'entrée)
    w("## Fichiers hors graphe")
    w("")
    w("Non analysés par le graphe : manifestes, configuration, déploiement, gabarits d'interface, scripts, front. À lire selon le besoin.")
    w("")
    count = 0
    for d in sorted(others):
        files = others[d]
        w(f"- `{d}/` : " + ", ".join(f"`{f}`" for f in files[:20]) + (f", … (+{len(files) - 20})" if len(files) > 20 else ""))
        count += 1
        if count >= maxn * 4:
            w(f"- … {len(others) - count} autres répertoires.")
            break
    w("")
    w(f"## Variables d'environnement lues ({len(env)})")
    w("")
    w("Noms seulement : les valeurs (éventuels secrets) ne sont jamais recopiées.")
    w("")
    for name in sorted(env):
        w(f"- `{name}` — " + ", ".join(sorted(env[name])))
    if not env:
        w("Aucune détectée.")
    w("")

    # --- Répartition de la lecture entre les trois explorations parallèles (chaque fichier à un seul axe)
    entry_files = {e[0].rsplit(":", 1)[0] for e in entries}
    axes = {"STRUCTURE": [], "USAGES": [], "DONNEES": []}
    every = sorted(graphed | {os.path.join(d, f) if d != "." else f for d, fs in others.items() for f in fs})
    env_files = {ref.rsplit(":", 1)[0] for refs in env.values() for ref in refs}
    for r in every:
        if skipped(r) or OWN_DOCS_RE.search(r) or NOT_READ_RE.search(r):
            continue
        axes[axis_of(r, entry_files, env_files)].append(r)
    w("## Lecture par axe")
    w("")
    w("Chaque fichier est attribué à une seule exploration : un axe ne relit un fichier d'un autre axe que pour vérifier "
      "une preuve. Heuristique sur les chemins, à corriger au besoin.")
    w("")
    for axis, files in axes.items():
        w(f"- **{axis}** ({len(files)}) : " + (", ".join(f"`{f}`" for f in files[:maxn * 3])
          + (f", … (+{len(files) - maxn * 3})" if len(files) > maxn * 3 else "") if files else "aucun"))
    w("")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    print(f"{out} : {len(comm)} communautés, {len(flows)} flux, {len(entries)} points d'entrée, "
          f"{kinds.get('File', 0)} fichiers")


if __name__ == "__main__":
    main()
