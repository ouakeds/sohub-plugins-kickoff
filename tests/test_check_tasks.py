"""Tests de skills/eval/check_tasks.py (contrôle des plans de tâches des stories et des lots du backlog)."""
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "eval", "check_tasks.py")
TEMPLATE = os.path.join(ROOT, "templates", "story.md")

HEADER = ("| ID | Tâche | Vague | Dépend de | Fichiers écrits | Lit | CA | Terminé quand | Statut | Agent |\n"
          "|----|-------|-------|-----------|-----------------|-----|----|---------------|--------|-------|\n")


def task_row(tid, wave="1", deps="—", files=None, ca="CA-010-01", done="tests verts", status="à faire"):
    files = f"`src/{tid}.ts`" if files is None else files
    return f"| {tid} | tâche | {wave} | {deps} | {files} | | {ca} | {done} | {status} | — |\n"


def make_story(rows, us="US-010", ticket="aucun", cas=("01",), ca_title="Critères d'acceptation"):
    num = us[3:]
    ca_lines = "".join(f"- **CA-{num}-{c}** (EF-01) — critère {c}.\n" for c in cas)
    ca_section = f"## {ca_title}\n\n{ca_lines}\n" if ca_title else ""
    return (f"# {us} — exemple\n\n- **Type** : feature\n- **Ticket** : {ticket}\n\n{ca_section}"
            f"## Plan de tâches\n\n{HEADER}{''.join(rows)}\n## Parallélisation\n\n- **Vagues** : 2\n")


def template_story():
    """Story tirée du gabarit, placeholders remplacés par des valeurs plausibles."""
    with open(TEMPLATE, encoding="utf-8") as f:
        text = f.read().replace("NNN", "010")
    lines = []
    for line in text.splitlines():
        m = re.match(r"^\| T-010-(\d{2}) ", line)
        if m:
            line = line.replace("<chemin>", f"src/f{m.group(1)}.ts")
        lines.append(line)
    return "\n".join(lines) + "\n"


class CheckTasksTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = self._tmp.name
        self.stories = os.path.join(self.project, ".sohub-plugin", "stories")
        os.makedirs(self.stories)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, content, binary=False):
        path = os.path.join(self.stories, name) if name.startswith("US-") else os.path.join(self.project, ".sohub-plugin", name)
        with open(path, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as f:
            f.write(content)

    def run_script(self, *args, expect=0):
        proc = subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, expect, proc.stdout + proc.stderr)
        return proc

    def check(self, *args, report="tasks.md"):
        """(nombre d'anomalies, texte du rapport)."""
        proc = self.run_script(self.project, *args)
        n = int(re.search(r"(\d+) anomalie", proc.stdout).group(1))
        with open(os.path.join(self.project, ".sohub-plugin", report), encoding="utf-8") as f:
            return n, f.read(), proc.stdout

    # --- conformité ---------------------------------------------------------
    def test_template_story_has_no_anomaly(self):
        self.write("US-010-gabarit.md", template_story())
        n, report, _ = self.check()
        self.assertEqual(n, 0, report)

    def test_typographic_apostrophe_in_ca_heading(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01")], ca_title="Critères d’acceptation"))
        n, report, _ = self.check()
        self.assertEqual(n, 0, report)

    def test_ca_section_missing_or_empty(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01")], ca_title=None))
        self.write("US-011-b.md", make_story([task_row("T-011-01", ca="CA-011-01")], us="US-011", cas=()))
        _, report, _ = self.check()
        self.assertIn("« Critères d'acceptation » absente", report)
        self.assertIn("« Critères d'acceptation » sans CA", report)

    def test_unknown_ca_cited_by_task(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01", ca="CA-010-01, CA-010-99")]))
        _, report, _ = self.check()
        self.assertIn("T-010-01 : sert CA-010-99, absent des critères d'acceptation", report)

    # --- tâches découpées ---------------------------------------------------
    def test_dependency_on_split_task_uses_last_subtask_wave(self):
        rows = [task_row("T-010-01"),
                task_row("T-010-02", wave="—", files="—", done="—"),
                task_row("T-010-02a", wave="2", deps="T-010-01"),
                task_row("T-010-02b", wave="3", deps="T-010-01"),
                task_row("T-010-03", wave="3", deps="T-010-02")]
        self.write("US-010-a.md", make_story(rows))
        _, report, _ = self.check()
        self.assertIn("T-010-03 (vague 3) : dépend de T-010-02 (vague 3), qui n'est pas antérieure", report)
        self.assertNotIn("colonne « Terminé quand » vide", report)

    def test_split_task_dependency_satisfied(self):
        rows = [task_row("T-010-01"),
                task_row("T-010-02", wave="—", files="—", done="—"),
                task_row("T-010-02a", wave="2", deps="T-010-01"),
                task_row("T-010-02b", wave="2", deps="T-010-01"),
                task_row("T-010-03", wave="3", deps="T-010-02")]
        self.write("US-010-a.md", make_story(rows))
        n, report, _ = self.check()
        self.assertEqual(n, 0, report)

    def test_empty_done_still_flagged_for_leaf(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01", done="—")]))
        _, report, _ = self.check()
        self.assertIn("T-010-01 : colonne « Terminé quand » vide", report)

    def test_second_level_subtask(self):
        rows = [task_row("T-010-01"), task_row("T-010-01ab", wave="2")]
        self.write("US-010-a.md", make_story(rows))
        _, report, _ = self.check()
        self.assertIn("T-010-01ab : sous-tâche de second niveau", report)

    # --- dépendances, vagues, fichiers -------------------------------------
    def test_cycle(self):
        rows = [task_row("T-010-01", wave="1", deps="T-010-02"), task_row("T-010-02", wave="2", deps="T-010-01")]
        self.write("US-010-a.md", make_story(rows))
        _, report, _ = self.check()
        self.assertIn("cycle de dépendances", report)

    def test_dependency_in_same_wave(self):
        rows = [task_row("T-010-01"), task_row("T-010-02", wave="1", deps="T-010-01")]
        self.write("US-010-a.md", make_story(rows))
        _, report, _ = self.check()
        self.assertIn("T-010-02 (vague 1) : dépend de T-010-01 (vague 1)", report)

    def test_file_written_twice_in_wave(self):
        rows = [task_row("T-010-01", files="`src/a.ts`"), task_row("T-010-02", files="`src/a.ts`")]
        self.write("US-010-a.md", make_story(rows))
        _, report, _ = self.check()
        self.assertIn("vague 1 : `src/a.ts` écrit par T-010-01, T-010-02", report)

    def test_file_paths_are_normalized(self):
        rows = [task_row("T-010-01", files="`./src/a.ts`"), task_row("T-010-02", files="src/lib/../a.ts")]
        self.write("US-010-a.md", make_story(rows))
        _, report, _ = self.check()
        self.assertIn("vague 1 : `src/a.ts` écrit par T-010-01, T-010-02", report)

    def test_unknown_status(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01", status="peut-être")]))
        _, report, _ = self.check()
        self.assertIn("T-010-01 : statut inconnu « peut-être »", report)

    # --- --ticket ------------------------------------------------------------
    def test_ticket_field_normalized(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01")], ticket="`PROJ-123`"))
        self.write("US-011-b.md", make_story([task_row("T-011-01", ca="CA-011-01")], us="US-011",
                                             ticket=" PROJ-123 <!-- clé Jira -->"))
        self.write("US-012-c.md", make_story([task_row("T-012-01", ca="CA-012-01")], us="US-012", ticket="PROJ-9"))
        _, report, out = self.check("--ticket", "PROJ-123", report="tasks-PROJ-123.md")
        self.assertIn("2 stories", out)
        self.assertIn("US-010", report)
        self.assertIn("US-011", report)
        self.assertNotIn("US-012", report)

    def test_ticket_without_story(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01")], ticket="TK-001"))
        _, report, out = self.check("--ticket", "TK-999", report="tasks-TK-999.md")
        self.assertIn("aucune story pour le ticket TK-999", out)
        self.assertIn("aucune story pour le ticket TK-999", report)

    def test_ticket_without_value_is_usage_error(self):
        proc = self.run_script(self.project, "--ticket", expect=2)
        self.assertIn("Usage", proc.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.project, ".sohub-plugin", "tasks.md")))
        self.run_script(expect=2)

    # --- robustesse ----------------------------------------------------------
    def test_unreadable_and_malformed_stories(self):
        self.write("US-010-bin.md", b"\xff\xfe\x00 pas de l'UTF-8 \x81", binary=True)
        self.write("US-011-x.md", "# US-011\n\n## Plan de tâches\n\n| ID |\n|---|\n| |||| | \n| `x` | | |\n")
        self.write("US-012-y.md", "rien d'exploitable | | |\n## Plan de tâches\n|\n|\n|\n")
        self.write("US-013-ok.md", make_story([task_row("T-013-01", ca="CA-013-01")], us="US-013"))
        n, report, _ = self.check()
        self.assertIn("story illisible", report)
        self.assertIn("## US-013", report)
        self.assertGreater(n, 0)

    # --- lots du backlog -----------------------------------------------------
    def backlog(self, us_rows, lots):
        rows = "".join(f"| {u} | t | P1 | {st} | {dep} | EF-01 | x |\n" for u, st, dep in us_rows)
        lot_rows = "".join(f"| {l} | {m} | — |\n" for l, m in lots)
        self.write("backlog.md", "# Backlog\n\n## 1. User stories\n\n| ID | Titre | Priorité | Statut | Dépend de | Besoins PRD | Fichier |\n"
                   "|----|----|----|----|----|----|----|\n" + rows +
                   "\n## 2. Parallélisation des US\n\n| Lot | US | Après |\n|----|----|----|\n" + lot_rows)

    def test_lots(self):
        self.write("US-010-a.md", make_story([task_row("T-010-01", files="`src/shared.ts`")]))
        self.write("US-011-b.md", make_story([task_row("T-011-01", ca="CA-011-01", files="`./src/shared.ts`")], us="US-011"))
        self.write("US-012-c.md", make_story([task_row("T-012-01", ca="CA-012-01")], us="US-012"))
        self.write("US-013-d.md", make_story([task_row("T-013-01", ca="CA-013-01")], us="US-013"))
        self.backlog([("US-010", "à faire", "aucune"), ("US-011", "à faire", "aucune"),
                      ("US-012", "à faire", "US-010"), ("US-013", "à cadrer", "aucune")],
                     [("L1", "US-010, US-011, US-012, US-013")])
        _, report, _ = self.check()
        self.assertIn("lot L1 : US-010 et US-011 écrivent tous deux `src/shared.ts`", report)
        self.assertIn("lot L1 : US-010 et US-012 sont dépendantes", report)
        self.assertIn("lot L1 : US-013 est « à cadrer »", report)


if __name__ == "__main__":
    unittest.main()
