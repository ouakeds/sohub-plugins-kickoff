"""Tests de skills/reverse/check_refs.py (vérification des preuves des documents rétro)."""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "reverse", "check_refs.py")

FRONT = "---\nstatut: brouillon\norigine: rétro\n---\n"


def write(base, rel, content, encoding="utf-8"):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding, newline="") as f:
        f.write(content)


def lines(n):
    return "".join(f"l{i}\n" for i in range(1, n + 1))


class CheckRefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        write(self.repo, "src/a.py", lines(30))
        write(self.repo, "mon dossier/b.py", lines(3))
        write(self.repo, "routes/+page.svelte", lines(3))
        write(self.repo, "app/[id]/page.tsx", lines(4))
        write(self.repo, "scripts/deploy", lines(6))
        write(self.repo, "Jenkinsfile", lines(5))
        write(self.repo, "Gemfile", lines(2))

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, docs, repo=None):
        for rel, text in docs.items():
            write(self.repo, os.path.join("docs", rel), text)
        res = subprocess.run([sys.executable, "-I", SCRIPT, repo or self.repo], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        report = os.path.join(self.repo, ".sohub-plugin", "reverse", "preuves.md")
        if not os.path.exists(report):
            return res.stdout, None
        with open(report, encoding="utf-8") as f:
            return res.stdout, f.read()

    def assertBroken(self, report, ref, reason=""):
        line = next((l for l in report.splitlines() if l.startswith(f"| `{ref}` |")), None)
        self.assertIsNotNone(line, f"{ref} absent du rapport :\n{report}")
        self.assertIn(reason, line)

    # 1. Lecture des références
    def test_backtick_paths_with_spaces_plus_and_brackets(self):
        out, report = self.run_check({"prd.md": FRONT
            + "*(déduit : `mon dossier/b.py:2`)*\n*(déduit : `routes/+page.svelte:2`)*\n"
            + "*(déduit : `app/[id]/page.tsx:3`)*\n*(déduit : `app/[id]/page.tsx:99`)*\n"})
        self.assertIn("4 référence(s) vérifiée(s)", out)
        self.assertIn("1 cassée(s)", out)
        self.assertBroken(report, "app/[id]/page.tsx:99", "4 lignes")
        self.assertNotIn("page.svelte` | fichier absent", report)
        self.assertNotIn("dossier/b.py` |", report)

    def test_files_without_extension(self):
        out, report = self.run_check({"prd.md": FRONT
            + "*(déduit : `scripts/deploy:99`)*\n*(déduit : `Jenkinsfile:5`)*\n*(déduit : `Gemfile:9`)*\n"})
        self.assertIn("3 référence(s) vérifiée(s)", out)
        self.assertBroken(report, "scripts/deploy:99", "6 lignes")
        self.assertBroken(report, "Gemfile:9", "2 lignes")
        self.assertNotIn("Jenkinsfile", report)

    def test_hostnames_and_urls_are_not_files(self):
        out, report = self.run_check({"prd.md": FRONT
            + "*(déduit : `src/a.py:3`, appel vers api.example.com:443)*\n"
            + "| Flux | Preuve |\n|---|---|\n| x | `localhost:5432`, `127.0.0.1:8000`, http://h.io/x.py:3 |\n"})
        self.assertIn("1 référence(s) vérifiée(s)", out)
        self.assertIn("Aucune référence cassée", report)

    def test_windows_separator(self):
        out, report = self.run_check({"prd.md": FRONT + "*(déduit : `src\\a.py:3`)*\n*(déduit : src\\a.py:31)*\n"})
        self.assertIn("2 référence(s) vérifiée(s)", out)
        self.assertBroken(report, "src/a.py:31", "30 lignes")
        self.assertNotIn("fichier absent", report)

    def test_bare_marker_fallback_still_works(self):
        out, report = self.run_check({"prd.md": FRONT + "*(déduit : src/zz.py:3)*\n*(déduit : src/a.py:4)*\n"})
        self.assertIn("2 référence(s) vérifiée(s)", out)
        self.assertBroken(report, "src/zz.py:3", "fichier absent")

    def test_escaped_pipe_in_proof_cell(self):
        out, report = self.run_check({"prd.md": FRONT
            + "| ID | Preuve |\n|----|--------|\n| EC-01 | `src/a.py:3` \\| `src/a.py:400` |\n"
            + "| EC-02 | src/a.py:5 \\| src/a.py:500 |\n"})
        self.assertIn("4 référence(s) vérifiée(s)", out)
        self.assertBroken(report, "src/a.py:400")
        self.assertBroken(report, "src/a.py:500")

    # 2. Blocs de code ignorés
    def test_code_blocks_ignored(self):
        out, report = self.run_check({"prd.md": FRONT
            + "```\n*(déduit : `src/in_code.py:4`)*\n| Preuve |\n|---|\n| `src/codeblock.py:1` |\n```\n"
            + "~~~md\n*(déduit : `src/tilde.py:1`)*\n~~~\n*(déduit : `src/a.py:1`)*\n"})
        self.assertIn("1 référence(s) vérifiée(s)", out)
        self.assertIn("Aucune référence cassée", report)

    # 3. Lecture robuste
    def test_bom_crlf_and_quoted_origin(self):
        write(self.repo, "docs/prd.md", "﻿---\r\norigine: \"rétro\"\r\n---\r\n*(déduit : `src/zz.py:1`)*\r\n")
        write(self.repo, "docs/architecture.md", "---\norigine: 'rétro'\n---\n*(déduit : `src/yy.py:1`)*\n")
        out, report = self.run_check({})
        self.assertIn("dans 2 document(s)", out)
        self.assertBroken(report, "src/zz.py:1", "fichier absent")
        self.assertBroken(report, "src/yy.py:1", "fichier absent")

    def test_invalid_utf8_does_not_stop_other_docs(self):
        os.makedirs(os.path.join(self.repo, "docs"))
        with open(os.path.join(self.repo, "docs", "x.md"), "wb") as f:
            f.write(b"---\norigine: r\xc3\xa9tro\n---\n\xff\xfe *(d\xc3\xa9duit : `src/zz.py:1`)*\n")
        out, report = self.run_check({"prd.md": FRONT + "*(déduit : `src/a.py:99`)*\n"})
        self.assertIn("dans 2 document(s)", out)
        self.assertBroken(report, "src/a.py:99")
        self.assertBroken(report, "src/zz.py:1")

    def test_non_retro_docs_ignored(self):
        out, report = self.run_check({"prd.md": "---\nstatut: x\n---\n*(déduit : `src/zz.py:1`)*\n",
                                      "notes.md": "*(déduit : `src/zz.py:1`)*\n"})
        self.assertIn("dans 0 document(s)", out)

    # 4. Plage inversée, dépôt absent
    def test_inverted_range(self):
        out, report = self.run_check({"prd.md": FRONT + "*(déduit : `src/a.py:20-10`)*\n*(déduit : `src/a.py:10-20`)*\n"})
        self.assertBroken(report, "src/a.py:20-10", "plage inversée")
        self.assertIn("1 cassée(s)", out)

    def test_missing_repo(self):
        missing = os.path.join(self.repo, "nope")
        res = subprocess.run([sys.executable, "-I", SCRIPT, missing], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("dépôt introuvable", res.stdout)
        self.assertFalse(os.path.exists(missing))

    # 5. Références entre accents graves dans toutes les cellules
    def test_backticks_in_any_table_cell(self):
        out, report = self.run_check({"architecture.md": FRONT
            + "| ID | Composant | Emplacement |\n|---|---|---|\n"
            + "| CMP-01 | Socle `src/a.py:99` | `src/a.py:2` |\n| CMP-02 | Divers | src/bare.py:1 |\n"})
        self.assertIn("2 référence(s) vérifiée(s)", out)
        self.assertBroken(report, "src/a.py:99")
        self.assertNotIn("bare.py", report)  # sans accents graves hors colonne « Preuve » : non vérifié

    def test_code_identifiers_in_cells_not_counted(self):
        out, report = self.run_check({"architecture.md": FRONT
            + "| Terme | Sens |\n|---|---|\n| `timeout:30` | `foo(a:1)` `User` |\n"})
        self.assertIn("0 référence(s) vérifiée(s)", out)


if __name__ == "__main__":
    unittest.main()
