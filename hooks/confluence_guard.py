#!/usr/bin/env python3
"""Garde-fou Confluence de /confluence-sync : pendant une synchro, le connecteur Atlassian ne touche qu'à la page
parente choisie et aux pages du projet.

Usage :
  confluence_guard.py on <projet>    active le garde-fou pour ce projet (au début de /confluence-sync)
  confluence_guard.py off <projet>   le désactive (à la fin, ou à l'arrêt de la synchro)
  confluence_guard.py hook           hook PreToolUse (JSON de l'appel sur l'entrée standard)

Tant qu'un garde-fou est actif (fichier dans ~/.claude/sohub-plugins-spec/garde-confluence/, expiré après
EXPIRATION secondes si la synchro s'est interrompue), le hook refuse tout appel Confluence du connecteur Atlassian
qui ne vise pas une page autorisée : page parente (`parent.parentContentId`), racine et pages de
`<projet>/.sohub-plugin/confluence.json`. Sont refusés aussi : la recherche, la lecture d'un espace, toute opération
destructive, et toute opération Confluence sans identifiant de page. Les opérations Jira et les métadonnées du
compte (sites accessibles, utilisateur, découverte des opérations) passent. Sans garde-fou actif, le hook ne fait
rien : les autres usages du connecteur ne sont pas touchés.
"""
import glob
import hashlib
import json
import os
import re
import sys
import time

EXPIRATION = 4 * 3600
LIBRES = {"getAccessibleAtlassianResources", "atlassianUserInfo", "discover"}
# Opérations lancées par execute* : celles de /confluence-sync, toutes sur une page désignée par son identifiant
OPERATIONS = {"getConfluenceContentDescendants", "setConfluenceContentStatus", "createConfluenceAttachment",
              "moveConfluenceContent"}
SANS_PAGE = {"getContentFormatGuide"}  # guide de format : aucun contenu du site
RECHERCHE = {"search", "getGraphContext", "addGraphContext", "getGraphObject"}
CLE_ID = re.compile(r"^(?:id|content_?id|page_?id|parent_?(?:content_?)?id|target_?id)$", re.I)
CLE_URL = re.compile(r"url$", re.I)
URL_ID = re.compile(r"/(?:pages|blog|whiteboard|database|folder)/(\d+)")


def dossier():
    return os.path.join(os.path.expanduser("~"), ".claude", "sohub-plugins-spec", "garde-confluence")


def fichier_garde(projet):
    cle = hashlib.sha256(os.path.realpath(projet).encode()).hexdigest()[:16]
    return os.path.join(dossier(), cle + ".json")


def gardes_actifs():
    actifs = []
    for f in glob.glob(os.path.join(dossier(), "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                g = json.load(fh)
            if g.get("expire", 0) > time.time():
                actifs.append(g["projet"])
            else:
                os.remove(f)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return actifs


def pages_autorisees(projets):
    ids = set()
    for p in projets:
        try:
            with open(os.path.join(p, ".sohub-plugin", "confluence.json"), encoding="utf-8") as fh:
                c = json.load(fh)
        except (OSError, ValueError):
            continue
        ids.add(str((c.get("parent") or {}).get("parentContentId") or ""))
        ids.add(str((c.get("racine") or {}).get("id") or ""))
        ids.update(str((v or {}).get("id") or "") for v in (c.get("pages") or {}).values())
    ids.discard("")
    ids.discard("None")
    return ids


def identifiants(valeur, cle=""):
    """Identifiants de page cités dans les paramètres : clés *id* (contentId, pageId, parentContentId, targetId…)
    et URL de page (/pages/<id>…). Une URL sans identifiant lisible donne « ? » (refusée)."""
    trouves = []
    if isinstance(valeur, dict):
        for k, v in valeur.items():
            trouves += identifiants(v, k)
    elif isinstance(valeur, list):
        for v in valeur:
            trouves += identifiants(v, cle)
    elif isinstance(valeur, (str, int)) and str(valeur).strip():
        if CLE_ID.match(cle):
            trouves.append(str(valeur).strip())
        elif CLE_URL.search(cle):
            m = URL_ID.search(str(valeur))
            trouves.append(m.group(1) if m else "?")
    return trouves


def decision(outil, entree, autorisees):
    """None si l'appel passe, sinon la raison du refus."""
    nom = outil.split("__")[-1]
    if nom in LIBRES:
        return None
    if nom in RECHERCHE:
        return f"recherche « {nom} » interdite pendant /confluence-sync"
    cibles = entree
    if nom.startswith("execute"):
        op = str(entree.get("name") or "")
        if re.search(r"jira", op, re.I):
            return None
        if nom == "executeDestructive":
            return f"opération destructive « {op} » interdite pendant /confluence-sync"
        if op in SANS_PAGE:
            return None
        if op not in OPERATIONS:
            return f"opération « {op} » hors du périmètre de /confluence-sync"
        cibles = entree.get("inputs") or {}
    elif not re.search(r"confluence", nom, re.I):
        return None  # Jira, Compass… : hors du périmètre du garde-fou
    elif nom not in ("getConfluenceContent", "createConfluenceContent", "updateConfluenceContent"):
        return f"outil « {nom} » hors du périmètre de /confluence-sync"
    ids = identifiants(cibles)
    if not ids:
        return f"« {nom} » sans page désignée (espace ou recherche) : interdit pendant /confluence-sync"
    hors = [i for i in ids if i not in autorisees]
    if hors:
        return (f"page {', '.join(hors)} hors du projet : /confluence-sync ne lit et n'écrit que la page parente "
                f"et les pages du projet (confluence.json)")
    return None


def hook():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    outil = str(data.get("tool_name") or "")
    if not re.search(r"atlassian", outil, re.I):
        return 0
    projets = gardes_actifs()
    if not projets:
        return 0
    entree = data.get("tool_input") or {}
    try:
        raison = decision(outil, entree if isinstance(entree, dict) else {}, pages_autorisees(projets))
    except Exception as e:  # garde-fou actif : en cas de doute, on refuse
        raison = f"appel non vérifiable ({type(e).__name__})"
    if raison:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": "Garde-fou Confluence : " + raison}},
                         ensure_ascii=False))
    return 0


def main(argv):
    if argv[:1] == ["hook"]:
        return hook()
    if len(argv) == 2 and argv[0] in ("on", "off") and os.path.isdir(argv[1]):
        f = fichier_garde(argv[1])
        if argv[0] == "on":
            os.makedirs(dossier(), exist_ok=True)
            with open(f, "w", encoding="utf-8") as fh:
                json.dump({"projet": os.path.realpath(argv[1]), "expire": time.time() + EXPIRATION}, fh)
            print(f"garde-fou Confluence actif pour {os.path.realpath(argv[1])}")
        else:
            if os.path.exists(f):
                os.remove(f)
            print("garde-fou Confluence désactivé")
        return 0
    print(__doc__.split("\n\n")[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
