"""Tests du hook de métriques (hooks/metrics.py) : robustesse des hooks, détection du projet, coûts.

Lancement depuis la racine du dépôt : python3 -I -m unittest discover -s tests
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hooks", "metrics.py")
PLUGIN = "sohub-plugins-spec:"

_spec = importlib.util.spec_from_file_location("metrics_under_test", SCRIPT)
metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics)


def usage(inp=10, cw=1000, cr=5000, out=500):
    return {"input_tokens": inp, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr, "output_tokens": out}


def assistant(mid, ts, model="claude-opus-5-5", u=None, content=None, stop="end_turn", side=False, sid="S1"):
    return {"type": "assistant", "timestamp": ts, "sessionId": sid, "isSidechain": side,
            "message": {"id": mid, "model": model, "role": "assistant", "stop_reason": stop,
                        "usage": usage() if u is None else u,
                        "content": content if content is not None else [{"type": "text", "text": "ok"}]}}


def user(ts, text, side=False, sid="S1", **extra):
    row = {"type": "user", "timestamp": ts, "sessionId": sid, "isSidechain": side,
           "message": {"role": "user", "content": text}}
    row.update(extra)
    return row


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def make_project(path, sohub=False):
    os.makedirs(os.path.join(path, "docs"), exist_ok=True)
    if sohub:
        os.makedirs(os.path.join(path, ".sohub-plugin"), exist_ok=True)
    return path


def snapshot(root):
    """Fichiers et dossiers sous `root`, avec taille et date de modification."""
    state = {}
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(base, name)
            st = os.stat(path)
            state[path] = (st.st_size, st.st_mtime_ns)
    return state


def run(args, stdin="", cwd=None):
    return subprocess.run([sys.executable, "-I", SCRIPT] + args, input=stdin.encode("utf-8"),
                          capture_output=True, cwd=cwd or ROOT, timeout=60)


def metrics_rows(project):
    return metrics.load_jsonl(os.path.join(project, ".sohub-plugin", "metrics.jsonl"))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = os.path.realpath(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def hook(self, command, payload, cwd=None):
        stdin = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        result = run([command], stdin, cwd=cwd or self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        return result

    def agent_run(self, sid, aid, prompt, agent="scoping", description="Cadrage ANALYSE — PRD",
                  t0="10:00:00", t1="10:02:00", model="claude-opus-5-5", complete=True):
        """Écrit le transcript d'un agent et renvoie l'entrée du hook SubagentStop."""
        session = os.path.join(self.tmp, "transcripts", f"{sid}.jsonl")
        path = os.path.join(self.tmp, "transcripts", sid, "subagents", f"agent-{aid}.jsonl")
        rows = [user(f"2026-10-12T{t0}Z", prompt, side=True, sid=sid, agentId=aid)]
        if complete:
            rows.append(assistant("m" + aid, f"2026-10-12T{t1}Z", model=model, side=True, sid=sid))
        else:
            rows.append(assistant("m" + aid, f"2026-10-12T{t1}Z", model=model, side=True, sid=sid, stop=None,
                                  u=usage(out=1), content=[{"type": "text", "text": "x" * 3800}]))
        write_jsonl(path, rows)
        with open(path[:-6] + ".meta.json", "w", encoding="utf-8") as f:
            json.dump({"agentType": PLUGIN + agent, "description": description}, f)
        return {"session_id": sid, "transcript_path": session, "agent_id": aid,
                "agent_type": PLUGIN + agent, "cwd": self.tmp, "hook_event_name": "SubagentStop"}

    def session_transcript(self, sid, prompt, t_prompt="09:59:00", messages=(("o1", "09:59:30"), ("o2", "10:03:00")),
                           model="claude-opus-5-5"):
        path = os.path.join(self.tmp, "transcripts", f"{sid}.jsonl")
        write_jsonl(path, [user(f"2026-10-12T{t_prompt}Z", prompt, sid=sid)]
                    + [assistant(mid, f"2026-10-12T{ts}Z", model=model, sid=sid) for mid, ts in messages])
        return path


class HookRobustness(Base):
    def test_invalid_inputs_do_nothing(self):
        transcript = self.session_transcript("S9", "Bonjour, aide-moi sur /etc/docs")
        payloads = ["", "not json", "[]", "{}", "null",
                    {"session_id": "S9", "transcript_path": "/nonexistent/x.jsonl", "cwd": self.tmp},
                    {"session_id": "S9", "transcript_path": transcript, "cwd": self.tmp},
                    {"session_id": "S9", "transcript_path": transcript, "agent_id": "zz", "cwd": self.tmp}]
        before = snapshot(self.tmp)
        for payload in payloads:
            for command in ("subagent", "stop"):
                with self.subTest(command=command, payload=payload):
                    self.hook(command, payload)
        self.assertEqual(snapshot(self.tmp), before)

    def test_foreign_agent_and_session_write_nothing(self):
        project = make_project(os.path.join(self.tmp, "app"))
        hook = self.agent_run("S1", "a1", f"Projet : {project}/docs/prd.md", agent="x")
        hook["agent_type"] = "autre-plugin:scoping"
        transcript = self.session_transcript("S1", "Corrige le bug du login")
        before = snapshot(self.tmp)
        self.hook("subagent", hook)
        self.assertEqual(snapshot(self.tmp), before)
        # Répertoire parent de projets du plugin, tour sans agent ni projet cité : rien.
        make_project(os.path.join(self.tmp, "p2"), sohub=True)
        before = snapshot(self.tmp)
        self.hook("stop", {"session_id": "S1", "transcript_path": transcript, "cwd": self.tmp})
        self.assertEqual(snapshot(self.tmp), before)
        self.assertFalse(os.path.exists(os.path.join(project, ".sohub-plugin")))


class ProjectDetection(Base):
    def test_unquoted_path_with_space(self):
        project = make_project(os.path.join(self.tmp, "My Projects", "app"))
        self.hook("subagent", self.agent_run("S1", "a1", f"Projet : {project}/docs/prd.md et {project}/.sohub-plugin"))
        self.assertEqual(len(metrics_rows(project)), 1)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "My Projects", ".sohub-plugin")))
        self.assertTrue(os.path.exists(os.path.join(project, ".sohub-plugin", "metrics.md")))

    def test_quoted_path_with_space(self):
        project = make_project(os.path.join(self.tmp, "Mes projets", "app"))
        self.assertEqual(metrics.cited_projects(f"Dossier `{project}/docs/` puis \"{project}/.sohub-plugin\"", None),
                         [project])

    def test_url_before_path(self):
        project = make_project(os.path.join(self.tmp, "app"))
        prompt = f"Voir https://example.com/docs et //example.com/docs. Projet : {project}/docs/prd.md"
        self.hook("subagent", self.agent_run("S1", "a1", prompt))
        self.assertEqual(len(metrics_rows(project)), 1)
        self.assertEqual(metrics.cited_projects("Voir https://example.com/docs", self.tmp), [])

    def test_relative_path_resolved_against_cwd(self):
        project = make_project(os.path.join(self.tmp, "app"))
        self.assertEqual(metrics.cited_projects("Projet : ./app/docs/prd.md", self.tmp), [project])
        self.assertEqual(metrics.cited_projects("Projet : ./app/docs/prd.md", None), [])
        self.assertEqual(metrics.cited_projects("Projet : ./nulle-part/docs", self.tmp), [])

    def test_missing_docs_dir_rejected(self):
        os.makedirs(os.path.join(self.tmp, "app"))
        before = snapshot(self.tmp)
        self.hook("subagent", self.agent_run("S1", "a1", f"Projet : {self.tmp}/app/docs/prd.md"))
        after = snapshot(self.tmp)
        self.assertFalse([p for p in set(after) - set(before) if ".sohub-plugin" in p])


class StopHook(Base):
    def test_double_stop_with_agents_no_duplicate(self):
        project = make_project(os.path.join(self.tmp, "app"))
        prompt = f"Mode : ANALYSE. Projet : {project}/docs/prd.md"
        self.hook("subagent", self.agent_run("S1", "a1", prompt, t0="10:00:00", t1="10:02:00"))
        transcript = self.session_transcript("S1", "/create-project une idée")
        stop = {"session_id": "S1", "transcript_path": transcript, "cwd": self.tmp, "hook_event_name": "Stop"}
        self.hook("stop", stop)
        first = metrics_rows(project)
        self.hook("stop", stop)
        second = metrics_rows(project)
        self.assertEqual(len(first), len(second))
        self.assertEqual(sum(r["type"] == "orchestrateur" for r in second), 1)
        # Un SubagentStop rejoué ne duplique pas non plus l'agent.
        self.hook("subagent", self.agent_run("S1", "a1", prompt, t0="10:00:00", t1="10:02:00"))
        self.assertEqual(len(metrics_rows(project)), len(second))

    def test_turn_without_agent_in_project_cwd(self):
        project = make_project(os.path.join(self.tmp, "app"), sohub=True)
        transcript = self.session_transcript("S1", "On valide le PRD ?")
        stop = {"session_id": "S1", "transcript_path": transcript, "cwd": project}
        self.hook("stop", stop, cwd=project)
        self.hook("stop", stop, cwd=project)
        rows = metrics_rows(project)
        self.assertEqual([r["type"] for r in rows], ["orchestrateur"])
        self.assertEqual(rows[0]["iteration"], 1)

    def test_turn_without_agent_cited_project(self):
        project = make_project(os.path.join(self.tmp, "My Projects", "app"), sohub=True)
        transcript = self.session_transcript("S1", f"Relis {project}/docs/prd.md")
        self.hook("stop", {"session_id": "S1", "transcript_path": transcript, "cwd": self.tmp})
        self.assertEqual(len(metrics_rows(project)), 1)


class Costs(Base):
    def test_synthetic_message_ignored(self):
        entries = [assistant("o1", "2026-10-12T10:00:00Z"),
                   assistant("o2", "2026-10-12T10:01:00Z", model="<synthetic>", u=usage(0, 0, 0, 0))]
        tokens, cost, models, turns, estimated = metrics.usage_of(entries)
        self.assertFalse(cost["partiel"])
        self.assertEqual(models, ["claude-opus-5-5"])
        self.assertEqual(turns, 1)
        self.assertFalse(estimated)
        # Usage nul d'un modèle inconnu : rien à tarifer, pas de coût partiel.
        tokens, cost, *_ = metrics.usage_of(entries + [assistant("o3", "2026-10-12T10:02:00Z", model="x", u=usage(0, 0, 0, 0))])
        self.assertFalse(cost["partiel"])

    def test_bedrock_and_vertex_models(self):
        for model, key in [("anthropic.claude-opus-4-6-v1:0", "claude-opus-4-6"),
                           ("us.anthropic.claude-sonnet-4-6-20260101-v1:0", "claude-sonnet-4-6"),
                           ("eu.anthropic.claude-haiku-4-5-v2", "claude-haiku-4-5"),
                           ("claude-opus-4-6@20260101", "claude-opus-4-6"),
                           ("claude-opus-5-5", "claude-opus-5-5"),
                           ("<synthetic>", None), ("gpt-x", None)]:
            with self.subTest(model=model):
                self.assertEqual(metrics.model_key(model), key)
        project = make_project(os.path.join(self.tmp, "app"))
        self.hook("subagent", self.agent_run("S1", "a1", f"Projet : {project}/docs", model="us.anthropic.claude-sonnet-4-6-v1:0"))
        cost = metrics_rows(project)[0]["cout"]
        self.assertFalse(cost["partiel"])
        self.assertGreater(cost["total"], 0)

    def test_estimated_output_flagged(self):
        project = make_project(os.path.join(self.tmp, "app"))
        self.hook("subagent", self.agent_run("S1", "a1", f"Projet : {project}/docs", complete=False))
        row = metrics_rows(project)[0]
        self.assertTrue(row.get("estime"))
        self.assertEqual(row["tokens"]["sortie"], 2000)
        with open(os.path.join(project, ".sohub-plugin", "metrics.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("2 000†", text)
        self.assertIn("† tokens de sortie estimés", text)


class RenderCompare(Base):
    def populated(self, name, model):
        project = make_project(os.path.join(self.tmp, name))
        self.hook("subagent", self.agent_run("S-" + name, "a-" + name, f"Projet : {project}/docs", model=model))
        return project

    def test_corrupt_jsonl_and_compare(self):
        a = self.populated("projA", "claude-opus-5-5")
        b = self.populated("projB", "claude-sonnet-5-5")
        with open(os.path.join(a, ".sohub-plugin", "metrics.jsonl"), "a", encoding="utf-8") as f:
            f.write('{"type": "agent", "debut": \n')
            f.write('{"type": "agent"}\n')
            f.write('[1, 2]\n')
        result = run(["render", a])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        with open(os.path.join(a, ".sohub-plugin", "metrics.md"), encoding="utf-8") as f:
            self.assertIn("3 ligne(s) illisible(s) ou incomplète(s) de metrics.jsonl ignorée(s)", f.read())
        result = run(["compare", a, b, os.path.join(self.tmp, "absent")])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        out = result.stdout.decode("utf-8")
        self.assertIn("| projA |", out)
        self.assertIn("| projB |", out)
        self.assertIn("3 ligne(s) illisible(s)", out)
        self.assertIn("pas de .sohub-plugin/metrics.jsonl", out)
        # Un hook sur un projet dont le fichier est corrompu continue d'écrire.
        self.hook("subagent", self.agent_run("S-projA", "a2", f"Projet : {a}/docs", t0="11:00:00", t1="11:01:00"))
        self.assertEqual(sum(r.get("agent_id") == "a2" for r in metrics_rows(a)), 1)

    def test_render_errors_without_traceback(self):
        result = run(["render"])
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b"Traceback", result.stderr)


class TestTaskParsing(unittest.TestCase):
    def test_titles_imposed_by_skills(self):
        cases = {
            "Cadrage ANALYSE — PRD": ("ANALYSE", "PRD"),
            "Cadrage RÉDACTION — TICKET TK-001": ("RÉDACTION", "TICKET"),
            "Eval — TICKET PROJ-12": ("EVAL", "TICKET"),
            "Recherche RÉTRO — ARCHITECTURE": ("RÉTRO", "ARCHITECTURE"),
        }
        for title, expected in cases.items():
            self.assertEqual(metrics.parse_task(title, ""), expected, title)

    def test_step_fallback_from_prompt(self):
        self.assertEqual(metrics.parse_task("autre", "Mode : RÉTRO\nÉtape : ARCHITECTURE"), ("RÉTRO", "ARCHITECTURE"))
        self.assertEqual(metrics.parse_task("autre", "Étape : COMPOSANTS"), (None, None))


class TestIterationStarts(unittest.TestCase):
    def starts(self, modes):
        records = [{"type": "agent", "mode": m, "debut": f"2026-10-12T10:{i:02d}:00Z"} for i, m in enumerate(modes)]
        found = metrics.iteration_starts(records)
        return [i for i, r in enumerate(records) if metrics.parse_ts(r["debut"]) in found]

    def test_import_starts_an_iteration(self):
        self.assertEqual(self.starts(["IMPORT", "EVAL", "ANALYSE", "RÉDACTION", "EVAL"]), [0, 2])

    def test_reverse_run_is_one_iteration(self):
        modes = ["EXPLORATION", "EXPLORATION", "EXPLORATION", "CARTOGRAPHIE", "RÉTRO", "RÉTRO"]
        self.assertEqual(self.starts(modes), [0])

    def test_resumed_retro_starts_an_iteration(self):
        self.assertEqual(self.starts(["ANALYSE", "EVAL", "RÉTRO", "RÉTRO"]), [0, 2])


if __name__ == "__main__":
    unittest.main()
