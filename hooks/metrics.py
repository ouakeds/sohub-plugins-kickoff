#!/usr/bin/env python3
"""Métriques du cadrage : temps, tokens, coût et qualité, par intervention et par itération.

Source de vérité : <projet>/.sohub-plugin/metrics.jsonl (une ligne JSON par enregistrement) ;
<projet>/.sohub-plugin/metrics.md en est une vue régénérée à chaque ajout.

Usages :
  metrics.py subagent            hook SubagentStop : une ligne par intervention d'un agent du plugin
  metrics.py stop                hook Stop : le travail de l'orchestrateur (session principale) du tour
  metrics.py render <projet>     régénère metrics.md
  metrics.py compare <projet>…   compare plusieurs runs (Markdown sur stdout)

Les hooks ne bloquent jamais : toute erreur est ignorée et rien n'est écrit sur stdout.
"""
import glob
import json
import os
import re
import sys
from datetime import datetime

PLUGIN = "sohub-plugins-spec:"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tarifs API Anthropic en $ par million de tokens : (entrée, sortie, cache lu).
# Écriture en cache : 1,25 × l'entrée (TTL 5 min), 2 × l'entrée (TTL 1 h).
PRICES = {
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-mythos-5-1": (10.0, 50.0, 0.25),
    "claude-fable-5": (10.0, 50.0, 1.0),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
    "claude-opus-4-7": (5.0, 25.0, 0.50),
    "claude-opus-4-6": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-sonnet-4-6": (3.0, 15.0, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}


# ---------- utilitaires ----------

def parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()


def iso(dt):
    return dt.isoformat(timespec="seconds")


def short(value):
    return parse_ts(value).strftime("%Y-%m-%d %H:%M:%S")


def fmt_duration(seconds):
    seconds = int(round(seconds or 0))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_usd(value):
    return "n/c" if value is None else f"${value:.3f}"


def fmt_int(value):
    return f"{int(value):,}".replace(",", " ")


def read_jsonl(path):
    """Objets JSON d'un fichier JSON Lines, et nombre de lignes illisibles (ignorées)."""
    rows, bad = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(row, dict):
                rows.append(row)
            else:
                bad += 1
    return rows, bad


def load_jsonl(path):
    return read_jsonl(path)[0]


def valid_record(r):
    try:
        parse_ts(r["debut"])
        parse_ts(r["fin"])
        return isinstance(r.get("duree_s"), (int, float)) and isinstance(r.get("tokens"), dict) and isinstance(r.get("acteur"), str) and isinstance(r.get("type"), str)
    except Exception:
        return False


def load_records(path):
    """Enregistrements exploitables de metrics.jsonl, et nombre de lignes ignorées (illisibles ou incomplètes)."""
    rows, bad = read_jsonl(path)
    records = [r for r in rows if valid_record(r)]
    return records, bad + len(rows) - len(records)


def plugin_version():
    try:
        with open(os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "?")
    except Exception:
        return "?"


def normalize_model(model):
    """Identifiant Anthropic d'un modèle servi par Bedrock ou Vertex AI
    (« us.anthropic.claude-sonnet-4-6-v1:0 », « claude-opus-4-6@20260101 » → « claude-… »)."""
    model = re.sub(r"^(?:[a-z]{2,6}\.)?anthropic\.", "", model.strip())
    model = re.sub(r"@[\w.-]*$", "", model)
    return re.sub(r"-v\d+(?::\d+)?$", "", model)


def model_key(model):
    if not model or model.startswith("<"):
        return None
    model = normalize_model(model)
    for key in sorted(PRICES, key=len, reverse=True):
        if model == key or model.startswith(key + "-") or model.startswith(key + "["):
            return key
    return None


# Caractères produits par token de sortie (mesuré sur des messages dont l'usage est complet).
CHARS_PER_OUTPUT_TOKEN = 1.9


def content_chars(message):
    """Taille du texte et des entrées d'outils d'une ligne de message assistant."""
    n = 0
    for c in message.get("content") or []:
        if c.get("type") == "text":
            n += len(c.get("text") or "")
        elif c.get("type") == "tool_use":
            n += len(json.dumps(c.get("input") or {}, ensure_ascii=False))
    return n


def usage_of(entries, main_thread=None):
    """Somme des usages des messages assistant (dernière ligne de chaque message.id, streaming)."""
    last, final, chars = {}, set(), {}
    for e in entries:
        message = e.get("message") or {}
        if e.get("type") != "assistant" or not isinstance(message.get("usage"), dict):
            continue
        if str(message.get("model") or "").startswith("<"):
            continue  # message <synthetic> (erreur API, interruption) : aucun token facturé
        if main_thread is not None and bool(e.get("isSidechain")) == main_thread:
            continue
        mid = message.get("id")
        last[mid] = message
        if message.get("stop_reason"):
            final.add(mid)
        chars[mid] = chars.get(mid, 0) + content_chars(message)
    totals = {"entree": 0, "cache_ecrit": 0, "cache_lu": 0, "sortie": 0}
    cost_in, cost_out, unknown, models, counted, estimated = 0.0, 0.0, False, set(), 0, False
    for message in last.values():
        u = message["usage"]
        inp = u.get("input_tokens") or 0
        cw = u.get("cache_creation_input_tokens") or 0
        cr = u.get("cache_read_input_tokens") or 0
        out = u.get("output_tokens") or 0
        mid = message.get("id")
        if mid not in final:
            # Dernière ligne de streaming absente : l'usage est partiel, on estime la sortie
            # d'après le texte et les entrées d'outils produits (la réflexion n'est pas comptée).
            guess = round(chars.get(mid, 0) / CHARS_PER_OUTPUT_TOKEN)
            if guess > out:
                out, estimated = guess, True
        if not (inp or cw or cr or out):
            continue  # usage nul : rien à compter ni à tarifer
        counted += 1
        totals["entree"] += inp
        totals["cache_ecrit"] += cw
        totals["cache_lu"] += cr
        totals["sortie"] += out
        models.add(message.get("model") or "?")
        key = model_key(message.get("model"))
        if not key:
            unknown = True
            continue
        p_in, p_out, p_cr = PRICES[key]
        speed = 2.0 if u.get("speed") == "fast" else 1.0
        split = u.get("cache_creation") or {}
        cw_1h = split.get("ephemeral_1h_input_tokens") or 0
        cw_5m = cw - cw_1h
        cost_in += speed * (inp * p_in + cw_5m * p_in * 1.25 + cw_1h * p_in * 2 + cr * p_cr) / 1e6
        cost_out += speed * out * p_out / 1e6
    tokens = dict(totals)
    tokens["entree_total"] = totals["entree"] + totals["cache_ecrit"] + totals["cache_lu"]
    tokens["total"] = tokens["entree_total"] + totals["sortie"]
    cost = None if unknown and not (cost_in or cost_out) else {
        "entree": round(cost_in, 6), "sortie": round(cost_out, 6), "total": round(cost_in + cost_out, 6),
        "partiel": unknown,
    }
    return tokens, cost, sorted(models), counted, estimated


def model_tag(entries, main_thread=None):
    """Étiquette « modèle · effort » des messages assistant, ex. « claude-opus-5-5 · high »."""
    tags = []
    for e in entries:
        model = (e.get("message") or {}).get("model")
        if e.get("type") != "assistant" or not model or model.startswith("<"):
            continue
        if main_thread is not None and bool(e.get("isSidechain")) == main_thread:
            continue
        tag = model + (f" · {e['effort']}" if e.get("effort") else "")
        if tag not in tags:
            tags.append(tag)
    return ", ".join(tags) or "?"


def prompt_text(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return content or ""


# Fin du chemin d'un projet : « /docs » ou « /.sohub-plugin » (séparateur / ou \), suivi d'une limite.
PROJECT_MARKER = re.compile(r"""[\\/](?:\.sohub-plugin|docs)(?=[\\/\s`'"),;:!?>\]]|\.(?:\s|$)|$)""")
PATH_OPENERS = " \t`'\"([<="
MAX_PATH_LENGTH = 1024


def path_starts(text, end):
    """Débuts possibles du chemin qui se termine en `end` (sur la même ligne), du plus proche au plus lointain :
    un chemin peut contenir des espaces (« /mnt/c/Users/x/My Projects/app »)."""
    line_start = max(text.rfind("\n", 0, end) + 1, end - MAX_PATH_LENGTH)
    for s in range(end - 1, line_start - 1, -1):
        if s > line_start and text[s - 1] not in PATH_OPENERS:
            continue
        head = text[s:s + 3]
        if head[:1] == "/" or head[:2] in ("~/", "./") or head == "../" or re.match(r"[A-Za-z]:[\\/]", head) \
                or re.match(r"[\w-]", head[:1]):
            yield s


def resolve_project(candidate, cwd):
    """Dossier du projet si `candidate` (chemin cité, relatif au cwd du hook) désigne un dossier dont `docs/`
    existe réellement et où `.sohub-plugin/` existe ou peut être créé ; sinon None."""
    if not candidate or "://" in candidate or candidate.startswith("//") or any(c in candidate for c in "`\"<>|\n"):
        return None
    path = os.path.expanduser(candidate)
    if not os.path.isabs(path):
        if not cwd or not os.path.isabs(cwd):
            return None
        path = os.path.join(cwd, path)
    path = os.path.normpath(path)
    if os.path.dirname(path) == path or not os.path.isdir(os.path.join(path, "docs")):
        return None
    sohub = os.path.join(path, ".sohub-plugin")
    if os.path.isdir(sohub) or (not os.path.lexists(sohub) and os.access(path, os.W_OK | os.X_OK)):
        return path
    return None


def cited_projects(text, cwd):
    """Projets cités dans un texte (chemins vers `<projet>/docs` ou `<projet>/.sohub-plugin`), dans l'ordre."""
    found = []

    def add(project):
        if project and project not in found:
            found.append(project)

    text = text or ""
    # Chemins entre backticks ou guillemets doubles (espaces compris) en priorité.
    for match in re.finditer(r"`([^`\n]+)`|\"([^\"\n]+)\"", text):
        span = (match.group(1) or match.group(2)).strip()
        for marker in PROJECT_MARKER.finditer(span):
            add(resolve_project(span[:marker.start()], cwd))
    for marker in PROJECT_MARKER.finditer(text):
        for s in path_starts(text, marker.start()):
            project = resolve_project(text[s:marker.start()], cwd)
            if project:
                add(project)
                break
    return found


def find_sohub_dir(prompt, cwd=None):
    projects = cited_projects(prompt, cwd)
    return os.path.join(projects[0], ".sohub-plugin") if projects else None


def is_plugin_project(path):
    """Projet du plugin : `docs/` et `.sohub-plugin/` existent."""
    return bool(path) and os.path.isdir(os.path.join(path, "docs")) and os.path.isdir(os.path.join(path, ".sohub-plugin"))


# Une itération commence à chaque analyse du cadrage, à chaque import de documents existants, ou à chaque série
# d'explorations d'un projet existant (les explorations parallèles, la cartographie qui les consolide et la rédaction
# rétro qui suit forment une seule itération ; une rédaction rétro reprise seule en ouvre une).
SERIES = ("EXPLORATION", "CARTOGRAPHIE")


def iteration_starts(records):
    """Débuts d'itération : une ANALYSE, un IMPORT, la première EXPLORATION / CARTOGRAPHIE d'une série, ou une
    RÉTRO qui ne suit ni une cartographie ni une autre RÉTRO (reprise de la rédaction)."""
    agents = sorted((r for r in records if r.get("type") == "agent"), key=lambda r: r["debut"])
    starts, previous = [], None
    for r in agents:
        mode = r.get("mode")
        if (mode in ("ANALYSE", "IMPORT") or (mode in SERIES and previous not in SERIES)
                or (mode == "EXPLORATION" and previous == "CARTOGRAPHIE")
                or (mode == "RÉTRO" and previous not in ("CARTOGRAPHIE", "RÉTRO"))):
            starts.append(parse_ts(r["debut"]))
        previous = mode
    return starts


def parse_task(description, prompt):
    """Mode et étape à partir du titre imposé par les skills (« Cadrage ANALYSE — PRD », « Eval — PRD »,
    « Recherche EXPLORATION — USAGES », « Recherche CARTOGRAPHIE — REVERSE », « Recherche RÉTRO — PRD », « Cadrage ANALYSE — TICKET TK-001 »)."""
    mode, etape = None, None
    match = re.match(r"\s*(?:(?:Cadrage|Recherche)\s+)?(ANALYSE|RÉDACTION|REDACTION|PROPOSITION|IMPORT|EXPLORATION|CARTOGRAPHIE|RÉTRO|RETRO|Eval)"
                     r"\b\s*[—-]\s*(?:après\s+)?(\w+)", description or "", re.I)
    if match:
        mode = match.group(1).upper().replace("REDACTION", "RÉDACTION").replace("RETRO", "RÉTRO")
        etape = match.group(2).upper()
    if not mode:
        match = re.search(r"Mode\s*:?\s*`?(ANALYSE|RÉDACTION|PROPOSITION|IMPORT|EXPLORATION|CARTOGRAPHIE|RÉTRO)", prompt)
        mode = match.group(1) if match else None
    if not etape:
        match = re.search(r"Étape[^:\n]*:\s*(PRD|ARCHITECTURE|ADR|BACKLOG|TICKET)", prompt)
        etape = match.group(1) if match else None
    return mode, etape


def latest_eval_quality(projet):
    files = sorted(glob.glob(os.path.join(projet, "docs", "eval", "*.md")))
    if not files:
        return None
    quality = {"fichier": os.path.basename(files[-1])}
    with open(files[-1], encoding="utf-8") as f:
        text = f.read()
    front = re.match(r"---\n(.*?)\n---", text, re.S)
    for line in (front.group(1).splitlines() if front else []):
        key, _, value = line.partition(":")
        value = value.strip()
        if key.strip() in ("points_ouverts", "bloquants", "bloquants_document_courant"):
            try:
                quality[key.strip()] = int(value)
            except ValueError:
                pass
        elif key.strip() == "etape":
            quality["etape"] = value
    return quality


def replace_records(sohub_dir, records, replaces):
    """Ajoute des enregistrements à metrics.jsonl en retirant ceux qu'ils remplacent (`replaces(ancien)` vrai),
    puis régénère metrics.md. Les autres lignes, même illisibles, sont gardées telles quelles."""
    os.makedirs(sohub_dir, exist_ok=True)
    path = os.path.join(sohub_dir, "metrics.jsonl")
    kept = []
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                try:
                    old = json.loads(line)
                    if isinstance(old, dict) and replaces(old):
                        continue
                except Exception:
                    pass
                kept.append(line)
    kept += [json.dumps(record, ensure_ascii=False) for record in records]
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    render(os.path.dirname(sohub_dir))


# ---------- hooks ----------

def hook_subagent(hook):
    path = hook.get("agent_transcript_path")
    if not path or not os.path.exists(path):
        session, agent_id = hook.get("transcript_path", ""), hook.get("agent_id")
        if not (session.endswith(".jsonl") and agent_id):
            return
        path = os.path.join(session[:-6], "subagents", f"agent-{agent_id}.jsonl")
    if not os.path.exists(path):
        return
    meta = {}
    if os.path.exists(path[:-6] + ".meta.json"):
        with open(path[:-6] + ".meta.json", encoding="utf-8") as f:
            meta = json.load(f)
    agent_type = hook.get("agent_type") or meta.get("agentType", "")
    if not agent_type.startswith(PLUGIN):
        return

    entries = load_jsonl(path)
    stamps = [e["timestamp"] for e in entries if e.get("timestamp")]
    first_user = next((e for e in entries if e.get("type") == "user"), None)
    if not stamps or not first_user:
        return
    prompt = prompt_text(first_user)
    sohub_dir = find_sohub_dir(prompt, hook.get("cwd"))
    if not sohub_dir:
        return
    projet = os.path.dirname(sohub_dir)

    tokens, cost, models, turns, estimated = usage_of(entries)
    tools = {}
    for e in entries:
        for block in ((e.get("message") or {}).get("content") or []) if e.get("type") == "assistant" else []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tools[block.get("name")] = tools.get(block.get("name"), 0) + 1
    description = meta.get("description") or ""
    agent = agent_type[len(PLUGIN):]
    mode, etape = parse_task(description, prompt)
    if agent == "evaluator":
        mode = "EVAL"
    start, end = parse_ts(stamps[0]), parse_ts(stamps[-1])
    record = {
        "type": "agent", "session": hook.get("session_id") or first_user.get("sessionId"),
        "agent_id": hook.get("agent_id") or first_user.get("agentId"), "acteur": agent,
        "mode": mode, "etape": etape, "tache": description or "—",
        "debut": iso(start), "fin": iso(end), "duree_s": round((end - start).total_seconds(), 1),
        "tours": turns, "outils": tools, "modeles": models, "modele": model_tag(entries),
        "tokens": tokens, "cout": cost,
        "version_plugin": plugin_version(),
    }
    if estimated:
        record["estime"] = True
    if mode == "EVAL":
        record["qualite"] = latest_eval_quality(projet)
    # Un même agent n'est compté qu'une fois, même si le hook se déclenche deux fois.
    replace_records(sohub_dir, [record], lambda old: bool(record["agent_id"]) and old.get("type") == "agent"
                    and old.get("agent_id") == record["agent_id"] and old.get("session") == record["session"])


def is_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    return isinstance(content, list) and not any(
        isinstance(c, dict) and c.get("type") == "tool_result" for c in content)


def turn_text(entries):
    """Texte où chercher les projets cités pendant un tour : invites de l'utilisateur et entrées d'outils
    de la session principale (chemins lus, prompts des agents)."""
    parts = []

    def strings(value):
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                strings(v)
        elif isinstance(value, list):
            for v in value:
                strings(v)

    for e in entries:
        if e.get("isSidechain"):
            continue
        if is_prompt(e):
            parts.append(prompt_text(e))
        elif e.get("type") == "assistant":
            for block in (e.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    strings(block.get("input"))
    return "\n".join(parts)


def hook_stop(hook):
    """Attribue le travail de la session principale pendant le tour (orchestrateur, attente de
    l'utilisateur comprise dans la durée) au projet dont des agents ont tourné pendant ce tour, sinon au
    projet du plugin concerné par le tour (répertoire courant, ou projet cité). Rien n'est écrit pour un
    tour qui ne concerne aucun projet du plugin."""
    session, path = hook.get("session_id"), hook.get("transcript_path")
    if not session or not path or not os.path.exists(path):
        return
    cwd = os.path.abspath(hook.get("cwd") or os.getcwd())
    entries = load_jsonl(path)
    start_idx = max((i for i, e in enumerate(entries) if is_prompt(e)), default=None)
    if start_idx is None:
        return
    turn = [e for e in entries[start_idx:] if e.get("timestamp")]
    if not turn:
        return
    turn_start = parse_ts(turn[0]["timestamp"])
    turn_end = max(parse_ts(e["timestamp"]) for e in turn)

    direct = ([cwd] if is_plugin_project(cwd) else []) + \
        [p for p in cited_projects(turn_text(turn), cwd) if is_plugin_project(p)]
    candidates = list(direct)
    for metrics_path in sorted(glob.glob(os.path.join(glob.escape(cwd), "*", ".sohub-plugin", "metrics.jsonl"))):
        project = os.path.dirname(os.path.dirname(metrics_path))
        if is_plugin_project(project):
            candidates.append(project)
    chosen, agents, records = None, [], []
    for project in dict.fromkeys(candidates):
        metrics_path = os.path.join(project, ".sohub-plugin", "metrics.jsonl")
        recs = load_records(metrics_path)[0] if os.path.exists(metrics_path) else []
        found = sorted((r for r in recs if r["type"] == "agent" and r.get("session") == session
                        and parse_ts(r["debut"]) >= turn_start), key=lambda r: r["debut"])
        if found:
            chosen, agents, records = project, found, recs
            break
    if not chosen:
        if not direct:
            return
        chosen = direct[0]
        metrics_path = os.path.join(chosen, ".sohub-plugin", "metrics.jsonl")
        records = load_records(metrics_path)[0] if os.path.exists(metrics_path) else []

    # Itération = nombre d'analyses (ou de séries d'explorations) lancées jusqu'à l'agent concerné (toutes sessions du projet).
    analyses = iteration_starts(records)

    def iteration_at(ts):
        return max(1, sum(1 for a in analyses if a <= ts))

    # Chaque message de l'orchestrateur va à l'itération de l'agent suivant (préparation), sinon du dernier ;
    # sans agent dans le tour, à l'itération en cours.
    buckets = {}
    for e in turn:
        if e.get("isSidechain"):
            continue
        ts = parse_ts(e["timestamp"])
        if agents:
            nxt = next((a for a in agents if parse_ts(a["debut"]) >= ts), None)
            it = iteration_at(parse_ts(nxt["debut"]) if nxt else parse_ts(agents[-1]["debut"]))
        else:
            it = iteration_at(turn_start)
        buckets.setdefault(it, []).append(e)
    out = []
    for it, items in sorted(buckets.items()):
        tokens, cost, models, turns, estimated = usage_of(items, main_thread=True)
        if not turns:
            continue
        debut = min(parse_ts(e["timestamp"]) for e in items)
        fin = max(parse_ts(e["timestamp"]) for e in items)
        if it == min(buckets):
            debut = turn_start
        if it == max(buckets):
            fin = turn_end
        record = {
            "type": "orchestrateur", "session": session, "acteur": "orchestrateur", "mode": "ORCHESTRATION",
            "etape": None, "tache": f"Orchestration — itération {it}", "iteration": it,
            "debut_tour": iso(turn_start),
            "debut": iso(debut), "fin": iso(fin), "duree_s": round((fin - debut).total_seconds(), 1),
            "tours": turns, "modeles": models, "modele": model_tag(items, main_thread=True),
            "tokens": tokens, "cout": cost,
            "version_plugin": plugin_version(),
        }
        if estimated:
            record["estime"] = True
        out.append(record)
    if not out:
        return

    def same_turn(old):
        # Hook Stop déclenché plusieurs fois pour un même tour : les nouveaux enregistrements remplacent les anciens.
        if old.get("type") != "orchestrateur" or old.get("session") != session:
            return False
        if old.get("debut_tour"):
            return parse_ts(old["debut_tour"]) == turn_start
        return turn_start <= parse_ts(old["debut"]) <= turn_end

    replace_records(os.path.join(chosen, ".sohub-plugin"), out, same_turn)


# ---------- agrégats ----------

def with_iterations(records):
    analyses = iteration_starts(records)
    for r in records:
        if "iteration" not in r:
            r["iteration"] = max(1, sum(1 for a in analyses if a <= parse_ts(r["debut"])))
    return records


def add_cost(acc, cost):
    if cost is None:
        acc["inconnu"] = True
        return
    for k in ("entree", "sortie", "total"):
        acc[k] = acc.get(k, 0.0) + cost[k]
    acc["inconnu"] = acc.get("inconnu", False) or cost.get("partiel", False)


def summarize(records):
    records = with_iterations(sorted(records, key=lambda r: r["debut"]))
    iterations = {}
    for r in records:
        it = iterations.setdefault(r["iteration"], {"records": [], "cout": {}, "tokens": {"entree_total": 0, "sortie": 0, "cache_lu": 0}})
        it["records"].append(r)
        add_cost(it["cout"], r.get("cout"))
        for k in it["tokens"]:
            it["tokens"][k] += r["tokens"].get(k, 0)
    rows = []
    for n, it in sorted(iterations.items()):
        recs = it["records"]
        debut = min(parse_ts(r["debut"]) for r in recs)
        fin = max(parse_ts(r["fin"]) for r in recs)
        evals = [r for r in recs if r.get("mode") == "EVAL" and r.get("qualite")]
        etapes = [r.get("etape") for r in recs if r.get("etape")]
        rows.append({
            "iteration": n, "etape": etapes[0] if etapes else "?",
            "duree_s": (fin - debut).total_seconds(),
            "agents_s": sum(r["duree_s"] for r in recs if r["type"] == "agent"),
            "tokens": it["tokens"], "cout": it["cout"],
            "qualite": evals[-1]["qualite"] if evals else None,
            "estime": any(r.get("estime") for r in recs),
            "orchestrateur": any(r["type"] == "orchestrateur" for r in recs),
        })
    total_cost = {}
    for r in records:
        add_cost(total_cost, r.get("cout"))
    last_quality = next((row["qualite"] for row in reversed(rows) if row["qualite"]), None)
    return {
        "records": records, "iterations": rows, "cout": total_cost,
        "tokens_entree": sum(r["tokens"].get("entree_total", 0) for r in records),
        "tokens_sortie": sum(r["tokens"].get("sortie", 0) for r in records),
        "sortie_estimee": any(r.get("estime") for r in records),
        "cache_lu": sum(r["tokens"].get("cache_lu", 0) for r in records),
        "duree_s": sum(row["duree_s"] for row in rows),
        "agents_s": sum(row["agents_s"] for row in rows),
        "qualite": last_quality,
        "versions": sorted({r.get("version_plugin", "?") for r in records}),
        "modeles": sorted({m for r in records for m in r.get("modeles", [])}),
        "modeles_par_acteur": {a: ", ".join(sorted({r.get("modele", "?") for r in records if r["acteur"] == a}))
                               for a in sorted({r["acteur"] for r in records})},
        "orchestrateur_mesure": any(r["type"] == "orchestrateur" for r in records),
        "etape_atteinte": rows[-1]["etape"] if rows else "?",
    }


def quality_cell(q):
    if not q:
        return "—"
    return f"{q.get('points_ouverts', '?')} ({q.get('bloquants', '?')} bloq.)"


def cost_cell(c, key):
    if not c or key not in c:
        return "n/c"
    return fmt_usd(c[key]) + ("*" if c.get("inconnu") else "")


def estimated_mark(flag):
    return "†" if flag else ""


def render(projet):
    sohub_dir = os.path.join(projet, ".sohub-plugin")
    path = os.path.join(sohub_dir, "metrics.jsonl")
    if not os.path.exists(path):
        return
    records, skipped = load_records(path)
    s = summarize(records)
    L = [
        "# Métriques du cadrage", "",
        "<!-- Vue générée automatiquement depuis metrics.jsonl (hooks du plugin) : ne pas modifier à la main. -->",
        "<!-- Tokens d'entrée = entrée + cache écrit + cache lu. Coûts = tarifs API Anthropic ($/M tokens), estimation. -->",
        "",
        "## Résumé du run", "",
        f"- **Version du plugin** : {', '.join(s['versions'])}",
        "- **Modèles (· effort)** : " + " ; ".join(f"{a} = {m}" for a, m in s["modeles_par_acteur"].items()),
        f"- **Itérations** : {len(s['iterations'])} — **Étape atteinte** : {s['etape_atteinte']}",
        f"- **Temps** : {fmt_duration(s['duree_s'])} au total, dont {fmt_duration(s['agents_s'])} d'agents"
        + ("" if s["orchestrateur_mesure"] else " (orchestrateur non mesuré)"),
        f"- **Tokens** : {fmt_int(s['tokens_entree'])} en entrée (dont {fmt_int(s['cache_lu'])} de cache lu), "
        f"{fmt_int(s['tokens_sortie'])}{estimated_mark(s['sortie_estimee'])} en sortie",
        f"- **Coût** : {cost_cell(s['cout'], 'entree')} en entrée + {cost_cell(s['cout'], 'sortie')} en sortie "
        f"= **{cost_cell(s['cout'], 'total')}**",
        f"- **Qualité (dernier eval)** : {quality_cell(s['qualite'])} points d'ombre ouverts",
        "",
        "## Par itération", "",
        "| It. | Étape | Durée | Agents | Tokens entrée | Tokens sortie | Coût entrée | Coût sortie | Coût total | Points ouverts (bloq.) |",
        "|-----|-------|-------|--------|---------------|---------------|-------------|-------------|------------|------------------------|",
    ]
    for row in s["iterations"]:
        L.append(f"| {row['iteration']} | {row['etape']} | {fmt_duration(row['duree_s'])} | {fmt_duration(row['agents_s'])} "
                 f"| {fmt_int(row['tokens']['entree_total'])} | {fmt_int(row['tokens']['sortie'])}{estimated_mark(row['estime'])} "
                 f"| {cost_cell(row['cout'], 'entree')} | {cost_cell(row['cout'], 'sortie')} | {cost_cell(row['cout'], 'total')} "
                 f"| {quality_cell(row['qualite'])} |")

    groups = {}
    for r in s["records"]:
        g = groups.setdefault((r["acteur"], r.get("mode") or "?", r.get("modele", "?")), {"n": 0, "duree": 0, "tin": 0, "tout": 0, "cout": {}})
        g["n"] += 1
        g["duree"] += r["duree_s"]
        g["tin"] += r["tokens"].get("entree_total", 0)
        g["tout"] += r["tokens"].get("sortie", 0)
        add_cost(g["cout"], r.get("cout"))
    L += ["", "## Moyennes par acteur et mode", "",
          "| Acteur | Mode | Modèle | N | Durée moy. | Tokens entrée moy. | Tokens sortie moy. | Coût entrée moy. | Coût sortie moy. | Coût total cumulé |",
          "|--------|------|--------|---|------------|--------------------|--------------------|------------------|------------------|-------------------|"]
    for (acteur, mode, modele), g in sorted(groups.items()):
        n, c = g["n"], g["cout"]
        avg = {k: c[k] / n for k in ("entree", "sortie") if k in c}
        avg["inconnu"] = c.get("inconnu")
        L.append(f"| {acteur} | {mode} | {modele} | {n} | {fmt_duration(g['duree'] / n)} | {fmt_int(g['tin'] / n)} | {fmt_int(g['tout'] / n)} "
                 f"| {cost_cell(avg, 'entree')} | {cost_cell(avg, 'sortie')} | {cost_cell(c, 'total')} |")

    L += ["", "## Interventions", "",
          "| It. | Acteur | Modèle | Tâche | Début | Fin | Durée | Tours | Outils | Tokens entrée (cache lu) | Tokens sortie | Total | Coût entrée | Coût sortie | Coût total |",
          "|-----|--------|--------|-------|-------|-----|-------|-------|--------|--------------------------|---------------|-------|-------------|-------------|------------|"]
    for r in s["records"]:
        t, c = {"entree_total": 0, "cache_lu": 0, "sortie": 0, "total": 0, **r["tokens"]}, r.get("cout")
        tools = ", ".join(f"{k} {v}" for k, v in sorted((r.get("outils") or {}).items())) or "—"
        L.append(f"| {r['iteration']} | {r['acteur']} | {r.get('modele', '?')} | {str(r.get('tache') or '—').replace('|', '/')} | {short(r['debut'])} | {short(r['fin'])} "
                 f"| {fmt_duration(r['duree_s'])} | {r.get('tours', '—')} | {tools} "
                 f"| {fmt_int(t['entree_total'])} ({fmt_int(t['cache_lu'])}) | {fmt_int(t['sortie'])}{estimated_mark(r.get('estime'))} | {fmt_int(t['total'])} "
                 f"| {fmt_usd(c and c['entree'])} | {fmt_usd(c and c['sortie'])} | {fmt_usd(c and c['total'])} |")
    notes = []
    if s["cout"].get("inconnu"):
        notes.append("\\* coût partiel : un modèle sans tarif connu a été utilisé.")
    if s["sortie_estimee"]:
        notes.append("† tokens de sortie estimés d'après le texte produit (dernière ligne de streaming absente du "
                     "transcript, réflexion non comptée) : probablement sous-estimés.")
    if skipped:
        notes.append(f"{skipped} ligne(s) illisible(s) ou incomplète(s) de metrics.jsonl ignorée(s).")
    for note in notes:
        L += ["", note]
    with open(os.path.join(sohub_dir, "metrics.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def compare(projets):
    runs = []
    for p in projets:
        path = os.path.join(p, ".sohub-plugin", "metrics.jsonl")
        if os.path.exists(path):
            records, skipped = load_records(path)
            if skipped:
                print(f"> {p} : {skipped} ligne(s) illisible(s) ou incomplète(s) de metrics.jsonl ignorée(s).\n")
            runs.append((p, summarize(records)))
        else:
            print(f"> {p} : pas de .sohub-plugin/metrics.jsonl, ignoré.\n")
    if not runs:
        return
    L = ["# Comparaison des runs", "",
         "| Run | Version | Itérations | Étape atteinte | Durée totale | Temps agents | Tokens entrée | Tokens sortie | Coût entrée | Coût sortie | Coût total | Points ouverts (bloq.) | Coût / itération |",
         "|-----|---------|------------|----------------|--------------|--------------|---------------|---------------|-------------|-------------|------------|------------------------|------------------|"]
    for p, s in runs:
        n = len(s["iterations"]) or 1
        per_it = {"total": s["cout"]["total"] / n, "inconnu": s["cout"].get("inconnu")} if "total" in s["cout"] else None
        L.append(f"| {os.path.basename(os.path.abspath(p))} | {', '.join(s['versions'])} | {len(s['iterations'])} | {s['etape_atteinte']} "
                 f"| {fmt_duration(s['duree_s'])} | {fmt_duration(s['agents_s'])} | {fmt_int(s['tokens_entree'])} "
                 f"| {fmt_int(s['tokens_sortie'])}{estimated_mark(s['sortie_estimee'])} "
                 f"| {cost_cell(s['cout'], 'entree')} | {cost_cell(s['cout'], 'sortie')} | {cost_cell(s['cout'], 'total')} "
                 f"| {quality_cell(s['qualite'])} | {cost_cell(per_it, 'total')} |")
    L += ["", "## Modèles par acteur (· effort)", ""]
    for p, s in runs:
        L.append(f"- **{os.path.basename(os.path.abspath(p))}** : "
                 + " ; ".join(f"{a} = {m}" for a, m in s["modeles_par_acteur"].items()))
    L += ["", "## Convergence (points ouverts après chaque itération)", ""]
    for p, s in runs:
        steps = " → ".join(quality_cell(row["qualite"]) for row in s["iterations"]) or "—"
        L.append(f"- **{os.path.basename(os.path.abspath(p))}** : {steps}")
    if any(not s["orchestrateur_mesure"] for _, s in runs):
        L += ["", "Attention : pour certains runs, l'orchestrateur n'est pas mesuré (durée et coût limités aux agents)."]
    if any(s["sortie_estimee"] for _, s in runs):
        L += ["", "† tokens de sortie en partie estimés (transcript incomplet) : probablement sous-estimés."]
    print("\n".join(L))


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "subagent"
    if command in ("render", "compare"):
        try:
            if command == "render":
                render(sys.argv[2])
            else:
                compare(sys.argv[2:])
        except Exception as exc:
            print(f"metrics.py {command} : échec ({type(exc).__name__} : {exc})", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            hook = json.load(sys.stdin)
            (hook_stop if command == "stop" else hook_subagent)(hook)
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
