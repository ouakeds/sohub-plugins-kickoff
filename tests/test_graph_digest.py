"""Tests de skills/reverse-engineer/graph_digest.py (digest du graphe Code Review Graph).

Fonctions pures importées depuis le chemin du script ; bout en bout sur un graph.db minimal construit ici
(même schéma que code-review-graph 2.3, réduit aux colonnes lues par le digest).
"""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "reverse-engineer", "graph_digest.py")

spec = importlib.util.spec_from_file_location("graph_digest", SCRIPT)
gd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gd)


def write(base, rel, content):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_graph(repo, nodes, communities=(), flows=(), risks=()):
    """graph.db minimal : nodes (dict), communautés et flux (cohésion / criticité éventuellement NULL)."""
    d = os.path.join(repo, ".code-review-graph")
    os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(os.path.join(d, "graph.db"))
    con.executescript("""
        create table nodes (id integer primary key, kind text, name text, qualified_name text, file_path text,
            line_start integer, line_end integer, language text, parent_name text, extra text, docstring text,
            community_id integer, is_test integer);
        create table edges (kind text, source_qualified text, target_qualified text, extra text);
        create table communities (id integer, name text, size integer, cohesion real);
        create table flows (name text, criticality real, node_count integer, file_count integer, path_json text,
            entry_point_id integer);
        create table risk_index (qualified_name text, risk_score real, caller_count integer, test_coverage text,
            security_relevant integer);
    """)
    cols = ("id", "kind", "name", "qualified_name", "file_path", "line_start", "line_end", "language",
            "parent_name", "extra", "docstring", "community_id", "is_test")
    for n in nodes:
        con.execute(f"insert into nodes values ({','.join('?' * len(cols))})", [n.get(c) for c in cols])
    con.executemany("insert into communities values (?, ?, ?, ?)", communities)
    con.executemany("insert into flows values (?, ?, ?, ?, ?, ?)", flows)
    con.executemany("insert into risk_index values (?, ?, ?, ?, ?)", risks)
    con.commit()
    con.close()


def file_node(i, repo, rel, lang="python", community=None):
    return {"id": i, "kind": "File", "name": os.path.basename(rel), "qualified_name": os.path.join(repo, rel),
            "file_path": os.path.join(repo, rel), "line_start": None, "line_end": None, "language": lang,
            "community_id": community, "is_test": 0}


def func_node(i, repo, rel, name, line, decorators=(), community=None):
    return {"id": i, "kind": "Function", "name": name, "qualified_name": f"{os.path.join(repo, rel)}::{name}",
            "file_path": os.path.join(repo, rel), "line_start": line, "line_end": line + 3, "language": "python",
            "extra": json.dumps({"decorators": list(decorators)}), "community_id": community, "is_test": 0}


class PureFunctionsTest(unittest.TestCase):
    # 6. Points d'entrée lus dans le texte
    def test_express_routes(self):
        self.assertEqual(gd.text_entries("src/routes/users.js", "router.get('/users/:id', h);"),
                         [("/users/:id", "router.get")])
        self.assertEqual(gd.text_entries("src/app.ts", 'app.use("/api", api);'), [("/api", "app.use")])
        self.assertEqual(gd.text_entries("src/a.js", "apiRouter.delete(`/x`, h)"), [("/x", "apiRouter.delete")])
        self.assertEqual(gd.text_entries("src/app.js", "app.use(express.json());"), [])  # middleware sans chemin
        self.assertEqual(gd.text_entries("src/a.js", "axios.get('/api/users')"), [])  # client HTTP
        self.assertEqual(gd.text_entries("src/a.py", "router.get('/x')"), [])  # pas un fichier JS/TS

    def test_django_urls(self):
        self.assertEqual(gd.text_entries("shop/urls.py", "    path('orders/<int:pk>/', views.detail),"),
                         [("orders/<int:pk>/", "path")])
        self.assertEqual(gd.text_entries("shop/urls.py", "    re_path(r'^old/$', views.old),"), [("^old/$", "re_path")])
        self.assertEqual(gd.text_entries("shop/utils.py", "path('x', y)"), [])  # hors urls.py
        self.assertEqual(gd.text_entries("shop/urls.py", "    path('', views.home),"), [("/", "path")])

    def test_flask_routes(self):
        self.assertEqual(gd.text_entries("app/views.py", "@app.route('/login', methods=['POST'])"),
                         [("/login", "@app.route")])
        self.assertEqual(gd.text_entries("app/api.py", "@bp.post(\"/items\")"), [("/items", "@bp.post")])
        self.assertEqual(gd.text_entries("app/views.py", "# @app.route('/x')"), [])

    # 7. Répartition par axe
    def test_axis_of_framework_files(self):
        self.assertEqual(gd.axis_of("shop/urls.py", set(), set()), "USAGES")
        self.assertEqual(gd.axis_of("src/router/index.js", set(), set()), "USAGES")
        self.assertEqual(gd.axis_of("src/routers.py", set(), set()), "USAGES")
        self.assertEqual(gd.axis_of("shop/admin.py", set(), set()), "USAGES")
        self.assertEqual(gd.axis_of("shop/views.py", set(), set()), "USAGES")
        self.assertEqual(gd.axis_of("shop/serializers.py", set(), set()), "DONNEES")
        self.assertEqual(gd.axis_of("shop/services.py", set(), set()), "STRUCTURE")
        self.assertEqual(gd.axis_of(".github/workflows/ci.yml", set(), set()), "DONNEES")
        self.assertEqual(gd.axis_of(".env.example", set(), set()), "DONNEES")

    def test_skipped_dirs(self):
        for path in (".next/server/page.js", "coverage/lcov.info", "staticfiles/admin/base.css",
                     "infra/.terraform/modules.json", "node_modules/x/index.js", "pkg.egg-info/PKG-INFO"):
            self.assertTrue(gd.skipped(path), path)
        for path in (".github/workflows/ci.yml", ".env.example", "src/app.py", "build.gradle"):
            self.assertFalse(gd.skipped(path), path)

    def test_real_env_files_never_read(self):
        for path in (".env", "config/.env", ".env.local", ".env.production"):
            self.assertTrue(gd.NOT_READ_RE.search(path), path)
        for path in (".env.example", ".env.sample", ".github/workflows/ci.yml"):
            self.assertFalse(gd.NOT_READ_RE.search(path), path)

    # 8. Variables d'environnement
    def test_env_names_code(self):
        self.assertEqual(gd.env_names("app/config.py", "x = os.environ.get('SECRET_KEY', 'dev')"), ["SECRET_KEY"])
        self.assertEqual(gd.env_names("src/a.js", "const p = process.env.PORT"), ["PORT"])
        self.assertEqual(gd.env_names("src/a.js", "const u = `${API_URL}/x`"), [])  # gabarit JS, pas du shell

    def test_env_names_shell(self):
        self.assertEqual(gd.env_names("scripts/run.sh", 'pg_dump "$DATABASE_URL" > "s3://${BUCKET}/"'),
                         ["DATABASE_URL", "BUCKET"])
        self.assertEqual(gd.env_names("scripts/deploy", "echo $HOME $PATH $DEPLOY_HOST"), ["DEPLOY_HOST"])
        self.assertEqual(gd.env_names("docker-compose.yml", "      - DB_URL=${DB_URL}"), ["DB_URL"])
        self.assertEqual(gd.env_names(".env.example", "export SECRET_KEY=changeme"), ["SECRET_KEY"])

    def test_env_names_dockerfile(self):
        self.assertEqual(gd.env_names("Dockerfile", "ENV APP_ENV=prod LOG_LEVEL=info"), ["APP_ENV", "LOG_LEVEL"])
        self.assertEqual(gd.env_names("Dockerfile", "ENV NODE_ENV production"), ["NODE_ENV"])
        self.assertEqual(gd.env_names("docker/Dockerfile.prod", "ARG BUILD_VERSION"), ["BUILD_VERSION"])
        self.assertEqual(gd.env_names("docker/Dockerfile", "ARG PY_VERSION=3.12"), ["PY_VERSION"])
        self.assertEqual(gd.env_names("Dockerfile", "RUN apt-get install -y curl"), [])
        self.assertEqual(gd.env_names("notes.md", "ENV APP_ENV=prod"), [])


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.out = os.path.join(self.repo, ".sohub-plugin", "reverse", "graphe.md")

    def tearDown(self):
        self.tmp.cleanup()

    def run_digest(self, *extra):
        return subprocess.run([sys.executable, "-I", SCRIPT, self.repo, self.out, *extra],
                              capture_output=True, text=True)

    def read_out(self):
        with open(self.out, encoding="utf-8") as f:
            return f.read()

    def test_text_entries_null_scores_and_axes(self):
        r = self.repo
        write(r, "src/app.js", "const app = require('express')();\napp.use('/users', require('./routes/users'));\n"
                               "app.listen(process.env.PORT);\n")
        write(r, "src/routes/users.js", "const router = require('express').Router();\nrouter.get('/', list);\n"
                                        "router.post('/', create);\n")
        write(r, "shop/urls.py", "urlpatterns = [\n    path('orders/', views.orders),\n]\n")
        write(r, "shop/views.py", "@app.route('/dup')\ndef orders(request):\n    return 1\n")
        write(r, ".github/workflows/ci.yml", "env:\n  TOKEN: ${{ secrets.TOKEN }}\n")
        write(r, ".env.example", "SECRET_KEY=\n")
        write(r, ".env", "SECRET_KEY=valeur-secrete\n")
        write(r, ".next/server/page.js", "app.get('/never', h)\n")
        write(r, "coverage/lcov.info", "x\n")
        write(r, "Dockerfile", "FROM python:3.12\nENV APP_ENV=prod\n")
        write(r, "scripts/run.sh", "#!/bin/sh\npg_dump \"$DATABASE_URL\"\n")
        make_graph(r, [
            file_node(1, r, "src/app.js", "javascript", 1), file_node(2, r, "src/routes/users.js", "javascript", 1),
            file_node(3, r, "shop/urls.py"), file_node(4, r, "shop/views.py"),
            func_node(5, r, "shop/views.py", "orders", 2, ["app.route('/dup')"], 1),
        ], communities=[(1, "web", 3, None)], flows=[("orders", None, 3, 2, "[5]", 5)],
            risks=[(os.path.join(r, "shop/views.py") + "::orders", None, 0, "none", 0)])
        res = self.run_digest()
        self.assertEqual(res.returncode, 0, res.stderr)
        out = self.read_out()
        self.assertIn("cohésion 0.00", out)
        self.assertIn("criticité 0.00", out)
        self.assertIn("| `/users` | src/app.js:2 | `app.use` |", out)
        self.assertIn("| `/` | src/routes/users.js:2 | `router.get` |", out)
        self.assertIn("| `orders/` | shop/urls.py:2 | `path` |", out)
        self.assertEqual(out.count("/dup"), 1)  # décorateur du graphe : pas de doublon par le texte
        self.assertNotIn("/never", out)
        axes = out.split("## Lecture par axe")[1]
        self.assertIn("`.github/workflows/ci.yml`", axes)
        self.assertIn("`.env.example`", axes)
        self.assertNotIn("`.env`", axes)
        self.assertNotIn(".next/", axes)
        self.assertNotIn("coverage/", axes)
        usages = next(l for l in axes.splitlines() if l.startswith("- **USAGES**"))
        self.assertIn("`shop/urls.py`", usages)
        env = out.split("## Variables d'environnement lues")[1].split("## Lecture par axe")[0]
        for name in ("PORT", "APP_ENV", "DATABASE_URL", "SECRET_KEY"):
            self.assertIn(f"`{name}`", env)
        self.assertNotIn("valeur-secrete", out)

    def test_max_without_value(self):
        make_graph(self.repo, [])
        for args in (["--max"], ["--max", "abc"], ["--max", "0"]):
            res = self.run_digest(*args)
            self.assertEqual(res.returncode, 2, args)
            self.assertIn("Usage", res.stderr)
        self.assertEqual(self.run_digest("--max", "3").returncode, 0)

    def test_missing_arguments(self):
        res = subprocess.run([sys.executable, "-I", SCRIPT, self.repo], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("Usage", res.stderr)


if __name__ == "__main__":
    unittest.main()
