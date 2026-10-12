#!/usr/bin/env python3
"""Vérifie les plans de tâches des stories (prêts à paralléliser), avant l'évaluateur.

Usage : check_tasks.py <projet> [--ticket <ID>]

Parcourt <projet>/.sohub-plugin/stories/*.md (avec --ticket : seulement les stories « Ticket : <ID> ») et
vérifie le tableau « Plan de tâches » de chacune : colonnes, identifiants, dépendances (existantes, sans cycle,
vers des vagues antérieures), fichiers écrits deux fois dans une même vague, CA de la story sans tâche,
sous-tâches sur un seul niveau, statuts connus. Recoupe ensuite les lots de « Parallélisation des US » du
backlog (fichiers écrits par deux US d'un même lot, US dépendantes dans un même lot). Écrit le détail dans
<projet>/.sohub-plugin/tasks.md (tasks-<ID>.md avec --ticket) et affiche une ligne de résumé. Ne bloque jamais :
code de sortie 0, sauf usage invalide (code 2).
"""
import glob
import os
import re
import sys

COLONNES = ["ID", "Tâche", "Vague", "Dépend de", "Fichiers écrits", "Lit", "CA", "Terminé quand", "Statut", "Agent"]
OBLIGATOIRES = ["ID", "Tâche", "CA", "Terminé quand", "Statut"]
STATUTS = ("à faire", "en cours", "fait", "bloqué")
TACHE_ID = re.compile(r"^T-(\d{3})-(\d{2})([a-z])?$")
US_ID = re.compile(r"US-\d{3}")
CA_ID = re.compile(r"CA-\d{3}-\d{2}")
VIDE = {"", "—", "-", "aucune", "aucun"}
COMMENTAIRE = re.compile(r"<!--.*?-->", re.S)
USAGE = "Usage : check_tasks.py <projet> [--ticket <ID>]"


def cellules(ligne):
    return [c.strip() for c in ligne.strip().strip("|").split("|")]


def section(texte, titre):
    """Lignes d'une section « ## <titre> » (jusqu'à la section suivante de même niveau)."""
    motif = re.escape(titre).replace("'", "['’]")
    m = re.search(r"^##\s+(?:\d+\.\s+)?" + motif + r"\s*$(.*?)(?=^##\s|\Z)", texte, re.M | re.S)
    return m.group(1).splitlines() if m else None


def tableau(lignes):
    """Premier tableau markdown des lignes : (en-tête, lignes de données)."""
    rows = [l for l in lignes if l.strip().startswith("|")]
    if len(rows) < 2:
        return None, []
    return cellules(rows[0]), [cellules(r) for r in rows[2:]]


def normalize_path(chemin):
    """Chemin comparable : sans accents graves ni « ./ », séparateurs « / », normalisé."""
    chemin = chemin.strip().strip("`").strip().replace("\\", "/")
    if not chemin:
        return ""
    return os.path.normpath(chemin).replace("\\", "/")


def fichiers(cellule):
    found = re.findall(r"`([^`]+)`", cellule)
    if not found and cellule.strip() not in VIDE:
        found = [f for f in cellule.split(",")]
    return [n for n in (normalize_path(f) for f in found) if n and n != "."]


def normalize_ticket(valeur):
    """Identifiant de ticket comparable : sans commentaire HTML, accents graves ni espaces."""
    return re.sub(r"[`\s]", "", COMMENTAIRE.sub("", valeur or "")).upper()


def lire_story(path):
    with open(path, encoding="utf-8") as f:
        texte = COMMENTAIRE.sub("", f.read())
    titre = re.search(r"^#\s+(US-\d{3})", texte, re.M)
    ticket = re.search(r"^\s*-\s*\*\*Ticket\*\*\s*:[ \t]*(.*)$", texte, re.M)
    lignes_ca = section(texte, "Critères d'acceptation")
    cas = set(CA_ID.findall("\n".join(lignes_ca))) if lignes_ca is not None else None
    us = titre.group(1) if titre else os.path.basename(path)[:6]
    return texte, us, (normalize_ticket(ticket.group(1)) if ticket else ""), cas


def verifier_story(path):
    texte, us, _, cas = lire_story(path)
    pb = []
    if cas is None:
        pb.append("section « Critères d'acceptation » absente")
    elif not cas:
        pb.append("section « Critères d'acceptation » sans CA (CA-NNN-xx attendu)")
    lignes = section(texte, "Plan de tâches")
    if lignes is None:
        if re.search(r"^##\s+Tâches\s*$", texte, re.M):
            return us, ["ancien format (liste de tâches à cocher) : à convertir en « Plan de tâches »"], set()
        return us, ["section « Plan de tâches » absente"], set()
    entete, rows = tableau(lignes)
    if not entete:
        return us, pb + ["« Plan de tâches » sans tableau"], set()
    manquantes = [c for c in COLONNES if c not in entete]
    if manquantes:
        pb.append("colonnes absentes : " + ", ".join(manquantes))
        return us, pb, set()
    idx = {c: entete.index(c) for c in COLONNES}
    # tâches découpées : déduites des identifiants de sous-tâches
    decoupees = set()
    for r in rows:
        m = TACHE_ID.match(r[idx["ID"]] if len(r) > idx["ID"] else "")
        if m and m.group(3):
            decoupees.add(f"T-{m.group(1)}-{m.group(2)}")
    taches = {}
    for r in rows:
        r = r + [""] * (len(entete) - len(r))
        t = {c: r[idx[c]] for c in COLONNES}
        tid = t["ID"]
        if not TACHE_ID.match(tid):
            if re.match(r"^T-\d{3}-\d{2}[a-z]\w+$", tid):
                pb.append(f"{tid} : sous-tâche de second niveau (un seul niveau autorisé)")
            else:
                pb.append(f"identifiant mal formé : « {tid} »")
            continue
        if tid in taches:
            pb.append(f"{tid} : identifiant en double")
            continue
        taches[tid] = t
        for c in OBLIGATOIRES:
            if c == "CA" or (c == "Terminé quand" and tid in decoupees):
                continue
            if t[c] in VIDE:
                pb.append(f"{tid} : colonne « {c} » vide")
        if cas:
            for ca in CA_ID.findall(t["CA"]):
                if ca not in cas:
                    pb.append(f"{tid} : sert {ca}, absent des critères d'acceptation de la story")
        statut = t["Statut"].lower()
        if not statut.startswith(STATUTS):
            pb.append(f"{tid} : statut inconnu « {t['Statut']} »")
    # sous-tâches : un seul niveau, parent sans vague ni fichiers
    parents = set()
    for tid in taches:
        m = TACHE_ID.match(tid)
        if m.group(3):
            parent = f"T-{m.group(1)}-{m.group(2)}"
            if parent not in taches:
                pb.append(f"{tid} : sous-tâche sans tâche parente {parent}")
            parents.add(parent)
    for p in parents & set(taches):
        if fichiers(taches[p]["Fichiers écrits"]) or taches[p]["Vague"] not in VIDE:
            pb.append(f"{p} : tâche découpée qui a encore une vague ou des fichiers écrits")
    feuilles = {tid: t for tid, t in taches.items() if tid not in parents}
    vagues = {}
    for tid, t in feuilles.items():
        if not t["Vague"].isdigit():
            pb.append(f"{tid} : vague « {t['Vague']} » invalide (entier attendu)")
        else:
            vagues[tid] = int(t["Vague"])
        if not fichiers(t["Fichiers écrits"]):
            pb.append(f"{tid} : aucun fichier écrit")
        elif len(fichiers(t["Fichiers écrits"])) > 3:
            pb.append(f"{tid} : écrit plus de 3 fichiers (à découper en sous-tâches)")
        if not CA_ID.findall(t["CA"]):
            pb.append(f"{tid} : aucun CA servi")
    # vagues d'une tâche découpée : de la première à la dernière vague de ses sous-tâches
    debut, fin = dict(vagues), dict(vagues)
    for p in parents & set(taches):
        sous = [v for tid, v in vagues.items() if tid[:-1] == p and tid != p]
        if sous:
            debut[p], fin[p] = min(sous), max(sous)
    # dépendances
    deps = {}
    for tid, t in taches.items():
        d = re.findall(r"T-\d{3}-\d{2}[a-z]?", t["Dépend de"])
        deps[tid] = d
        for x in d:
            if x not in taches:
                pb.append(f"{tid} : dépend de {x}, inconnue dans la story")
            elif tid in debut and x in fin and fin[x] >= debut[tid]:
                pb.append(f"{tid} (vague {debut[tid]}) : dépend de {x} (vague {fin[x]}), qui n'est pas antérieure")
    # cycles
    etat = {}

    def visite(n, chemin):
        etat[n] = 1
        for x in deps.get(n, []):
            if x not in taches:
                continue
            if etat.get(x) == 1:
                pb.append("cycle de dépendances : " + " → ".join(chemin[chemin.index(x):] + [x]))
            elif not etat.get(x):
                visite(x, chemin + [x])
        etat[n] = 2

    for n in taches:
        if not etat.get(n):
            visite(n, [n])
    # anti-conflit dans une vague
    par_vague = {}
    for tid, v in vagues.items():
        for f in fichiers(feuilles[tid]["Fichiers écrits"]):
            par_vague.setdefault((v, f), []).append(tid)
    for (v, f), ts in sorted(par_vague.items()):
        if len(ts) > 1:
            pb.append(f"vague {v} : `{f}` écrit par {', '.join(ts)}")
    # couverture des CA
    servis = set()
    for t in feuilles.values():
        servis |= set(CA_ID.findall(t["CA"]))
    for ca in sorted((cas or set()) - servis):
        pb.append(f"{ca} : aucune tâche ne le sert")
    if not section(texte, "Parallélisation"):
        pb.append("section « Parallélisation » absente")
    ecrits = {f for t in feuilles.values() for f in fichiers(t["Fichiers écrits"])}
    return us, pb, ecrits


def verifier_lots(projet, ecrits_par_us):
    path = os.path.join(projet, ".sohub-plugin", "backlog.md")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            texte = COMMENTAIRE.sub("", f.read())
    except (OSError, UnicodeDecodeError) as e:
        return [f"backlog illisible : {e}"]
    pb = []
    _, us_rows = tableau(section(texte, "User stories") or [])
    dependances, statuts = {}, {}
    for r in us_rows:
        if r and US_ID.fullmatch(r[0]):
            dependances[r[0]] = set(US_ID.findall(r[4] if len(r) > 4 else ""))
            statuts[r[0]] = r[3].lower() if len(r) > 3 else ""
    lignes = section(texte, "Parallélisation des US")
    if lignes is None:
        return ["backlog : section « Parallélisation des US » absente"] if ecrits_par_us else []
    _, rows = tableau(lignes)
    for r in rows:
        if len(r) < 2 or not r[0] or r[0].startswith("<"):
            continue
        lot, membres = r[0], US_ID.findall(r[1])
        for a in membres:
            if statuts.get(a, "").startswith("à cadrer"):
                pb.append(f"lot {lot} : {a} est « à cadrer » (n'entre dans un lot qu'à la validation de son ticket)")
        for i, a in enumerate(membres):
            for b in membres[i + 1:]:
                if b in dependances.get(a, ()) or a in dependances.get(b, ()):
                    pb.append(f"lot {lot} : {a} et {b} sont dépendantes")
                communs = ecrits_par_us.get(a, set()) & ecrits_par_us.get(b, set())
                if communs:
                    pb.append(f"lot {lot} : {a} et {b} écrivent tous deux " + ", ".join(f"`{c}`" for c in sorted(communs)))
    return pb


def parse_args(args):
    """(projet, ticket) ou None si l'usage est invalide."""
    projet, ticket = None, None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--ticket":
            if i + 1 >= len(args) or args[i + 1].startswith("--") or not normalize_ticket(args[i + 1]):
                return None
            ticket = args[i + 1]
            i += 2
            continue
        if a.startswith("--") or projet is not None:
            return None
        projet = a
        i += 1
    if projet is None or (ticket is not None and ticket.strip() == ""):
        return None
    return projet, ticket


def check_story(path):
    """(US, ticket, anomalies, fichiers écrits) ; une story illisible ou mal formée devient une anomalie."""
    us = os.path.basename(path)[:6]
    try:
        _, us, t, _ = lire_story(path)
    except (OSError, UnicodeDecodeError) as e:
        return us, "", [f"story illisible : {e}"], set()
    try:
        us_id, pb, ecrits = verifier_story(path)
    except Exception as e:  # story mal formée : on la signale sans interrompre le contrôle
        return us, t, [f"story mal formée, analyse interrompue : {type(e).__name__} : {e}"], set()
    return us_id, t, pb, ecrits


def main():
    parsed = parse_args(sys.argv[1:])
    if parsed is None:
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    projet, ticket = os.path.abspath(parsed[0]), parsed[1]
    if not os.path.isdir(projet):
        print(f"Projet introuvable : {projet}\n{USAGE}", file=sys.stderr)
        sys.exit(2)
    cle = normalize_ticket(ticket) if ticket else None
    stories = sorted(glob.glob(os.path.join(projet, ".sohub-plugin", "stories", "US-*.md")))
    resultats, ecrits_par_us = [], {}
    for path in stories:
        us_id, t, pb, ecrits = check_story(path)
        ecrits_par_us[us_id] = ecrits
        if cle and t != cle:
            continue
        resultats.append((us_id, os.path.relpath(path, projet), pb))
    try:
        lots = verifier_lots(projet, ecrits_par_us)
    except Exception as e:  # backlog mal formé
        lots = [f"backlog mal formé, analyse interrompue : {type(e).__name__} : {e}"]
    if ticket:
        miens = {u for u, _, _ in resultats}
        lots = [l for l in lots if any(u in l for u in miens)]
    n = sum(len(pb) for _, _, pb in resultats) + len(lots)
    portee = f"ticket {ticket}" if ticket else "backlog"
    out = [f"# Contrôle des plans de tâches — {portee}", "",
           f"{len(resultats)} stories vérifiées, {n} anomalie(s).", ""]
    absent = f"aucune story pour le ticket {ticket}" if ticket and not resultats else ""
    if absent:
        out.extend([f"- {absent} (champ « Ticket » des stories).", ""])
    for us, rel, pb in resultats:
        out.append(f"## {us} — `{rel}`")
        out.extend([f"- {p}" for p in pb] or ["- OK"])
        out.append("")
    if lots or not ticket:
        out.append("## Parallélisation des US (backlog)")
        out.extend([f"- {p}" for p in lots] or ["- OK"])
        out.append("")
    nom = f"tasks-{re.sub(r'[^A-Za-z0-9_.-]', '_', ticket)}.md" if ticket else "tasks.md"
    dest = os.path.join(projet, ".sohub-plugin", nom)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write("\n".join(out))
        detail = f"détail dans .sohub-plugin/{nom}"
    except OSError as e:
        detail = f"rapport non écrit ({e})"
    print(f"Plans de tâches ({portee}) : {len(resultats)} stories, {n} anomalie(s)"
          + (f", {absent}" if absent else "") + f" — {detail}.")


if __name__ == "__main__":
    main()
