#!/usr/bin/env python3
"""Vérifie les preuves des documents rétro-générés par /reverse (remplace l'eval).

Usage : check_refs.py <dépôt>

Parcourt les documents `origine: rétro` de <dépôt>/docs/ et vérifie chaque référence `fichier:ligne`
(marqueurs « *(déduit : fichier:ligne)* » et cellules des colonnes « Preuve ») : le fichier doit exister dans
le dépôt et la ligne ne pas dépasser sa longueur. Écrit <dépôt>/.sohub-plugin/reverse/preuves.md (références
cassées par document) et affiche une ligne de résumé. Ne bloque jamais (code de sortie 0).
"""
import glob
import os
import re
import sys

# chemin relatif avec extension ou nom de fichier connu, suivi de :ligne ou :début-fin
REF = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.[\w]+|(?:[\w.-]+/)*(?:Dockerfile|Makefile|Procfile)):(\d+)(?:-(\d+))?")
DEDUIT = re.compile(r"\*\(déduit\s*:\s*([^)]*)\)\*")


def line_counts(repo):
    cache = {}

    def count(rel):
        if rel not in cache:
            path = os.path.normpath(os.path.join(repo, rel))
            if not path.startswith(repo + os.sep) or not os.path.isfile(path):
                cache[rel] = None
            else:
                with open(path, "rb") as f:
                    data = f.read()
                cache[rel] = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
        return cache[rel]
    return count


def preuve_cells(text):
    """Cellules des colonnes « Preuve » des tableaux Markdown."""
    cells, col = [], None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            col = None
            continue
        parts = [c.strip() for c in line.strip().strip("|").split("|")]
        if col is None:
            col = next((i for i, c in enumerate(parts) if c.lower().startswith("preuve")), -1)
        elif col >= 0 and col < len(parts) and not re.fullmatch(r":?-+:?", parts[col]):
            cells.append(parts[col])
    return cells


def main(repo):
    count = line_counts(repo)
    docs = sorted(glob.glob(os.path.join(repo, "docs", "**", "*.md"), recursive=True))
    total, broken = 0, {}
    checked_docs = 0
    for doc in docs:
        with open(doc, encoding="utf-8") as f:
            text = f.read()
        front = re.match(r"---\n(.*?)\n---", text, re.S)
        if not front or not re.search(r"^origine:\s*rétro\s*$", front.group(1), re.M):
            continue
        checked_docs += 1
        sources = DEDUIT.findall(text) + preuve_cells(text)
        seen = set()
        for src in sources:
            for m in REF.finditer(src):
                rel, start, end = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
                if (rel, start, end) in seen:
                    continue
                seen.add((rel, start, end))
                total += 1
                n = count(rel)
                if n is None:
                    reason = "fichier absent du dépôt"
                elif start < 1 or end > n or start > end:
                    reason = f"ligne hors du fichier ({n} lignes)"
                else:
                    continue
                broken.setdefault(os.path.relpath(doc, repo), []).append((m.group(0), reason))

    nb_broken = sum(len(v) for v in broken.values())
    out_dir = os.path.join(repo, ".sohub-plugin", "reverse")
    os.makedirs(out_dir, exist_ok=True)
    L = ["# Vérification des preuves", "",
         f"{checked_docs} document(s) rétro, {total} référence(s) vérifiée(s), {nb_broken} cassée(s).", ""]
    for doc, items in broken.items():
        L += [f"## {doc}", "", "| Référence | Problème |", "|-----------|----------|"]
        L += [f"| `{ref}` | {reason} |" for ref, reason in items]
        L.append("")
    if not broken:
        L.append("Aucune référence cassée.")
    with open(os.path.join(out_dir, "preuves.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"Preuves : {total} référence(s) vérifiée(s) dans {checked_docs} document(s), {nb_broken} cassée(s)"
          + (f" ({', '.join(f'{d} : {len(v)}' for d, v in broken.items())})" if broken else "")
          + " — détail dans .sohub-plugin/reverse/preuves.md.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage : check_refs.py <dépôt>")
        sys.exit(0)
    try:
        main(os.path.abspath(sys.argv[1]))
    except Exception as exc:  # ne bloque jamais
        print(f"Preuves : vérification impossible ({exc}).")
