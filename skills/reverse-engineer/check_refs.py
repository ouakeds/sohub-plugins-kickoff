#!/usr/bin/env python3
"""Vérifie les preuves des documents rétro-générés par /reverse-engineer (remplace l'eval).

Usage : check_refs.py <dépôt>

Parcourt les documents `origine: rétro` de <dépôt>/docs/ et vérifie chaque référence `fichier:ligne`
(marqueurs « *(déduit : fichier:ligne)* », cellules des colonnes « Preuve » et chemins entre accents graves
des cellules de tableau) : le fichier doit exister dans le dépôt et la ligne ne pas dépasser sa longueur.
Les blocs de code (```) sont ignorés : une référence citée dans du code n'est pas une preuve.
Écrit <dépôt>/.sohub-plugin/reverse/preuves.md (références cassées par document) et affiche une ligne de
résumé. Ne bloque jamais (code de sortie 0).

Règles de lecture d'une référence :
- le contenu entre accents graves fait foi (chemin entier : espaces, `+`, `[]` compris) ; sans accents graves
  (marqueurs et colonnes « Preuve » seulement), repli sur un motif de chemin sans espace ;
- un chemin sans extension compte s'il contient un `/` (`scripts/deploy:9`) ou s'il est un nom en « …file »
  (Dockerfile, Makefile, Jenkinsfile, Gemfile…) ;
- `\\` est lu comme `/` (chemin Windows) ;
- n'est pas un fichier : une URL (`://`, `http…`) ni, sans `/`, `localhost`, une adresse IP ou un nom de
  domaine finissant par un TLD courant (`api.example.com:443`).
"""
import glob
import os
import re
import sys

SEG = r"[\w.\[\]+@~-]+"  # segment de chemin sans espace (repli sans accents graves)
# repli : chemin avec extension, nom en « …file », ou chemin sans extension contenant un /
REF = re.compile(rf"(?<![\w/.\[\]+@~-])((?:{SEG}/)*(?:{SEG}\.\w+|[A-Z][a-z]*file|[Mm]akefile)|(?:{SEG}/)+{SEG})"
                 r":(\d+)(?:-(\d+))?(?![\w:/])")
# contenu complet d'un passage entre accents graves : chemin (espaces admis) puis :ligne ou :début-fin
CODE_REF = re.compile(r"\s*([\w .\[\]+@~/\\-]+?):(\d+)(?:-(\d+))?\s*")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
DEDUIT = re.compile(r"\*\(déduit\s*:\s*(.*?)\)\*")
FENCE = re.compile(r"^\s*(```|~~~)")
TLD = {"com", "org", "net", "io", "fr", "eu", "de", "uk", "us", "dev", "app", "co", "ai", "cloud", "local",
       "internal", "localhost"}


def is_host(path):
    """Nom d'hôte (pas un fichier) : URL, localhost, adresse IP ou domaine à TLD courant, sans /."""
    if "://" in path or path.lower().startswith("http"):
        return True
    if "/" in path:
        return False
    low = path.lower()
    return (low == "localhost" or re.fullmatch(r"\d+(\.\d+){3}", low) is not None
            or (re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", low) is not None and low.rsplit(".", 1)[1] in TLD))


def looks_like_file(path):
    """Chemin plausible : contient un /, a une extension, ou est un nom en « …file »."""
    name = path.rsplit("/", 1)[-1]
    return "/" in path or re.search(r"\.\w{1,10}$", name) is not None or re.fullmatch(r"[A-Z][a-z]*file|[Mm]akefile", name) is not None


def refs_in(src, bare):
    """Références (chemin, début, fin) d'un texte : passages entre accents graves, plus, si `bare` (marqueurs
    « déduit » et colonnes « Preuve »), le repli sans accents sur le reste du texte."""
    spans = CODE_SPAN.findall(src)
    found = []
    for span in spans:
        m = CODE_REF.fullmatch(span)
        if m:
            path = m.group(1).strip().replace("\\", "/")
            if path and looks_like_file(path) and not is_host(path):
                found.append((path, int(m.group(2)), int(m.group(3) or m.group(2))))
    if bare:  # repli sur le texte hors accents graves
        rest = CODE_SPAN.sub(" ", src).replace("\\", "/")
        for m in REF.finditer(rest):
            if not is_host(m.group(1)) and not re.search(r"://\S*$", rest[:m.start()]):
                found.append((m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))))
    return found


def strip_code_blocks(text):
    """Remplace les lignes des blocs ``` / ~~~ par des lignes vides (les numéros de ligne restent justes)."""
    out, fence = [], None
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence:
            if m and m.group(1) == fence:
                fence = None
            out.append("")
        elif m:
            fence = m.group(1)
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


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


def table_cells(text):
    """Cellules des tableaux Markdown : (cellule, est dans une colonne « Preuve »). `\\|` ne sépare pas."""
    cells, col = [], None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            col = None
            continue
        parts = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if col is None:
            col = next((i for i, c in enumerate(parts) if c.lower().startswith("preuve")), -1)
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in parts if c):
            continue
        cells += [(c, i == col) for i, c in enumerate(parts)]
    return cells


def check_doc(text, count):
    """Références cassées d'un document : (nombre vérifié, [(référence, problème)])."""
    text = strip_code_blocks(text)
    sources = [(s, True) for s in DEDUIT.findall(text)] + table_cells(text)
    seen, broken = set(), []
    for src, bare in sources:
        for rel, start, end in refs_in(src, bare):
            if (rel, start, end) in seen:
                continue
            seen.add((rel, start, end))
            n = count(rel)
            if n is None:
                reason = "fichier absent du dépôt"
            elif start > end:
                reason = f"plage inversée ({start}-{end})"
            elif start < 1 or end > n:
                reason = f"ligne hors du fichier ({n} lignes)"
            else:
                continue
            broken.append((f"{rel}:{start}" + (f"-{end}" if end != start else ""), reason))
    return len(seen), broken


def main(repo):
    if not os.path.isdir(repo):
        print(f"Preuves : dépôt introuvable ({repo}), rien à vérifier.")
        return
    count = line_counts(repo)
    docs = sorted(glob.glob(os.path.join(repo, "docs", "**", "*.md"), recursive=True))
    total, broken, errors = 0, {}, {}
    checked_docs = 0
    for doc in docs:
        name = os.path.relpath(doc, repo)
        try:  # un document illisible n'empêche pas de vérifier les autres
            with open(doc, encoding="utf-8-sig", errors="replace") as f:
                text = f.read()
            front = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
            if not front or not re.search(r"""^origine:\s*["']?rétro["']?\s*$""", front.group(1), re.M):
                continue
            checked_docs += 1
            n, items = check_doc(text, count)
            total += n
            if items:
                broken[name] = items
        except Exception as exc:
            errors[name] = str(exc)

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
    if errors:
        L += ["", "## Documents non vérifiés", ""] + [f"- `{d}` : {e}" for d, e in errors.items()]
    with open(os.path.join(out_dir, "preuves.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"Preuves : {total} référence(s) vérifiée(s) dans {checked_docs} document(s), {nb_broken} cassée(s)"
          + (f" ({', '.join(f'{d} : {len(v)}' for d, v in broken.items())})" if broken else "")
          + (f", {len(errors)} document(s) illisible(s)" if errors else "")
          + " — détail dans .sohub-plugin/reverse/preuves.md.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage : check_refs.py <dépôt>")
        sys.exit(0)
    try:
        main(os.path.abspath(sys.argv[1]))
    except Exception as exc:  # ne bloque jamais
        print(f"Preuves : vérification impossible ({exc}).")
