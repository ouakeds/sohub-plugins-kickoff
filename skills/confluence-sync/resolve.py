#!/usr/bin/env python3
"""Partie mécanique de /confluence-sync, autour du travail de l'agent layout.

L'agent écrit .sohub-plugin/sync/plan.json et .sohub-plugin/sync/corps/<clé>.(md|html), avec des liens
symboliques `page:<clé>` et des marqueurs `{{spec:docs/contrats/<fichier>}}` / `{{date_synchro}}`. Ce script :

  sources    <projet> <dossier du plugin>   empreinte des sources (tout docs/ sauf docs/eval/ et docs/adr/, + agent + gabarit) → stdout ;
                                            relevé par fichier dans .sohub-plugin/sync/sources.json (enregistré par fusionner)
  changed    <projet> <dossier du plugin>   documents ajoutés / modifiés / supprimés depuis la dernière mise en page
                                            (transformation.files de confluence.json), pages à réécrire ou à garder
                                            (sources du plan précédent) ; `full: true` si tout est à refaire (agent
                                            layout ou gabarit modifié, aucun relevé, plan ou corps absents) ; sinon copie
                                            plan.json et corps/ dans .sohub-plugin/sync/previous/ → JSON sur stdout
  documents  <projet>                       liste des documents publiables (chemins relatifs au projet)
  verifier   <projet>                       contrôle le rendu de l'agent ; une erreur par ligne, code 1 si erreur
  squelette  <projet>                       migre les anciennes clés de confluence.json ; liste JSON des pages
                                            dans l'ordre du plan (clé, titre, parente, id connu) et des orphelines
  enregistrer <projet> <clé> <id> <titre> <url>   enregistre une page créée dans confluence.json
  ordre      <projet> <enfants.json>        déplacements à faire : <enfants.json> = {"<id parent>": [ids dans
                                            l'ordre affiché], …} ; sortie : liste JSON {id, position, targetId}
  resoudre   <projet> <date-heure>          liens et spécifications résolus dans .sohub-plugin/sync/final/,
                                            empreintes, état de chaque page, diagrammes extraits en .mmd et
                                            fichiers à joindre → .sohub-plugin/sync/manifest.json
  rendre     <projet> <config puppeteer>    rend en PNG (mermaid-cli, en parallèle) les diagrammes des pages à
                                            publier dont l'image manque ou est périmée
  lots       <projet> [--failed] [nombre max]   écrit .sohub-plugin/sync/lot-<n>.json (pages à publier) ; avec
                                            --failed, seulement les pages en échec ou incomplètes de la dernière
                                            fusion (.sohub-plugin/sync/failed.json) ; un PNG ou une spécification
                                            dont le sha256 est celui déjà joint (files de la page, fileId connu) est
                                            marqué `reuse: {fileId, attachmentId}` : il n'est pas renvoyé
  fusionner  <projet> <empreinte sources>   fusionne resultats-*.json dans confluence.json (dont les fichiers joints
                                            de chaque page, `files`, et le relevé des sources, transformation.files),
                                            supprime lots et résultats, écrit la liste des pages en échec dans
                                            .sohub-plugin/sync/failed.json
  forget     <projet> <clé>                 oublie l'id d'une page (ou de la racine) supprimée à la main dans
                                            Confluence : le squelette la recrée à la synchro
  upload     <projet> <fichier> <commande curl>   exécute la commande d'envoi renvoyée par createConfluenceAttachment
                                            après contrôle : fichier sous docs/ (ou PNG d'un diagramme extrait), cité
                                            par un lot, hôte = site de confluence.json ou api.atlassian.com, options sûres ;
                                            avec SOHUB_UPLOAD_DRY_RUN=1, affiche la commande validée sans l'exécuter (tests)

Seul le dossier docs/ du projet est publié (sauf docs/eval/, historique du processus, et docs/adr/, décisions) : aucun fichier hors de docs/
n'est lu dans une page ni joint.
"""
import glob, hashlib, html, json, os, re, shlex, shutil, subprocess, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# Numéro de titre : « 1. », « 1) », « 2.3 », « 2.3. » — pas un nombre seul (« ## 404 Not Found »).
_NUM = r'(?:\d+(?:\.\d+)+[.)]?|\d+[.)])\s'
# Identifiant de processus seulement dans un contexte de processus : « S1 : », « (S1) », « [S1] », « (S1, S2) »…
# (« Stockage sur S3 », « s3://… » ne sont pas visés)
_CTX = lambda i: rf'[(\[]{i}[,)\]]|\b{i}\s*:(?!//)'
PROCESS = [(r'§', '« § »'), (r'(?m)^#{1,6}\s+' + _NUM, 'titre numéroté'),
           (r'<h[1-6][^>]*>\s*' + _NUM, 'titre numéroté'), (_CTX(r'I-\d{2}'), 'identifiant de processus I-xx'),
           (_CTX(r'S[1-9]'), 'identifiant de processus Sx'), (r'structure validée', '« structure validée »'),
           (r'https?://[^\s)"]*atlassian\.net', 'URL Confluence écrite en dur'),
           # documentation minimale : ni preuve du code, ni chemin de fichier source
           (r'\(\s*déduit\s*:', 'preuve du code « déduit : »'), (r'diffère du code actuel', 'preuve « diffère du code actuel »'),
           (r'(?m)^\W*(?:<sub>)?\s*Sources\s*:', 'ligne « Sources : » de preuves'),
           (r'\b[\w.-]+/[\w./-]*\.[A-Za-z]{1,5}:\d+\b', 'référence fichier:ligne'),
           # documentation d'embarquement : ni questions ouvertes, ni dette
           (r'À CLARIFIER', 'marqueur [À CLARIFIER] (à remplacer par « à préciser »)'),
           (r'\bQ[AB]?-\d+\b', 'identifiant de question ouverte'),
           (r'(?im)^\s*(?:#{1,6}|<h[1-6][^>]*>)\s*(?:Questions ouvertes|Points ouverts|Dette)', 'section questions ouvertes ou dette')]
FICHIER = re.compile(r'\bFichier\s*:\s*(?:<code>|`)?([^\s<`·|]*)')
YAML_CONTRAT = re.compile(r'docs/contrats/[^/]+\.ya?ml')
LINK = re.compile(r'(?<=\]\()page:([\w.-]+)|(?<=href=")page:([\w.-]+)')
# Identifiants à ne pas perdre : cas d'usage, exigences fonctionnelles, règles métier, contrats. Les autres (ENF, écrans,
# composants, flux synchrones, contraintes, questions ouvertes…) ne sont pas publiés dans la documentation minimale.
IDS = re.compile(r'\b(?:CU|EF|RG|CTR)-\d+\b')
NON_PUBLIES = ('eval', 'adr')  # dossiers de docs/ jamais publiés : historique des evals, décisions
STATUTS = {'brouillon': ('Brouillon', '#FF8B00'), 'proposé': ('Proposé', '#0065FF'), 'validé': ('Validé', '#36B37E'),
           'accepté': ('Validé', '#36B37E'), 'rejeté': ('Rejeté', '#6B778C'), 'déprécié': ('Déprécié', '#6B778C')}


def statut_natif(st, defaut):
    st = (st or '').strip()
    if st.startswith('remplacé'):  # « remplacé par ADR-NNNN »
        return ('Remplacé', '#6B778C')
    return STATUTS.get(st, defaut)


# Clés de l'ancienne arborescence → clés du plan
OLD = {'docs/architecture.md#vue-ensemble': 'vue-ensemble', 'docs/prd.md': 'fonctionnel', 'docs/architecture.md': 'architecture',
       'docs/architecture.md#base-de-donnees': 'donnees', 'docs/architecture.md#flux': 'flux', 'docs/architecture.md#contrats': 'interfaces',
       'docs/architecture.md#services': 'services', 'docs/adr/index.md': 'decisions', 'docs/glossaire.md': 'glossaire'}


def sync_dir(p):
    return os.path.join(p, '.sohub-plugin', 'sync')


def load(path, default=None):
    try:
        return json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return default


def save(path, data):
    json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def cfg_path(p):
    return os.path.join(p, '.sohub-plugin', 'confluence.json')


def docs_dir(p):
    return os.path.realpath(os.path.join(p, 'docs'))


def in_docs(p, path):
    """Vrai si `path` (absolu, ou relatif au projet) désigne un fichier sous <projet>/docs/, hors docs/eval/ et docs/adr/."""
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(p, path))
    d = docs_dir(p)
    return (real.startswith(d + os.sep) and not any(real.startswith(os.path.join(d, x) + os.sep) for x in NON_PUBLIES)
            and os.path.isfile(real))


def source_files(p):
    """Tous les fichiers publiables : docs/ entier, récursif, sauf docs/eval/, docs/adr/ et les fichiers cachés."""
    out = []
    for root, dirs, files in os.walk(os.path.join(p, 'docs')):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.') and not (root == os.path.join(p, 'docs') and x in NON_PUBLIES))
        out += [os.path.join(root, f) for f in sorted(files) if not f.startswith('.')]
    return [f for f in out if in_docs(p, f)]


def is_contract(p, f):
    return os.path.relpath(f, p).replace(os.sep, '/').startswith('docs/contrats/')


def corps_path(p, page):
    return os.path.join(sync_dir(p), 'corps', page['cle'] + ('.html' if page['format'] == 'html' else '.md'))


def strip_code(text):
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    text = re.sub(r'<pre>.*?</pre>', '', text, flags=re.S)
    return re.sub(r'`[^`\n]*`|<code>.*?</code>', '', text)


PLUGIN_FILES = ('agents/layout.md', 'templates/confluence-tree.md')


def file_sha(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def source_snapshot(p, plugin):
    """Empreinte globale des sources, sha256 de chaque document (chemin relatif au projet) et des fichiers du plugin."""
    # chemins relatifs : l'empreinte ne change ni quand le projet est déplacé, ni quand le plugin change de dossier
    h = hashlib.sha256()
    docs, plug = {}, {}
    files = [(os.path.relpath(f, p).replace(os.sep, '/'), f, docs) for f in source_files(p)]
    files += [(r, os.path.join(plugin, r), plug) for r in PLUGIN_FILES]
    for rel, f, out in files:
        if os.path.isfile(f):
            data = open(f, 'rb').read()
            h.update(rel.encode()); h.update(data)
            out[rel] = hashlib.sha256(data).hexdigest()
    return dict(empreinte=h.hexdigest(), files=docs, plugin=plug)


def cmd_sources(p, plugin):
    snap = source_snapshot(p, plugin)
    os.makedirs(sync_dir(p), exist_ok=True)
    save(os.path.join(sync_dir(p), 'sources.json'), snap)  # relevé enregistré par fusionner (transformation.files)
    print(snap['empreinte'])


def source_path(s):
    """Chemin d'une entrée `sources` du plan (« docs/architecture.md § 7, 8 » → « docs/architecture.md »)."""
    return s.split('§')[0].split('#')[0].strip()


def cites_doc(sources, rel):
    return any(c == rel or (c.endswith('/') and rel.startswith(c)) for c in map(source_path, sources or []))


def cmd_changed(p, plugin):
    """Documents changés depuis la dernière mise en page et pages du plan précédent à réécrire ou à garder."""
    cur = source_snapshot(p, plugin)
    tr = (load(cfg_path(p), {}) or {}).get('transformation') or {}
    old, old_plug = tr.get('files'), tr.get('plugin')
    out = dict(full=False, reasons=[], added=[], modified=[], removed=[], pages_to_rewrite=[], pages_to_keep=[], previous=None)
    if old is None or old_plug is None:
        out['reasons'].append('aucun relevé des sources de la dernière mise en page')
        old, old_plug = old or {}, old_plug or {}
    else:
        if old_plug.get('agents/layout.md') != cur['plugin'].get('agents/layout.md'):
            out['reasons'].append('agent layout modifié')
        if old_plug.get('templates/confluence-tree.md') != cur['plugin'].get('templates/confluence-tree.md'):
            out['reasons'].append('gabarit modifié')
    out['added'] = sorted(set(cur['files']) - set(old))
    out['removed'] = sorted(set(old) - set(cur['files']))
    out['modified'] = sorted(f for f in set(cur['files']) & set(old) if cur['files'][f] != old[f])
    plan = load(os.path.join(sync_dir(p), 'plan.json'))
    if not plan or not plan.get('pages'):
        out['reasons'].append('plan.json absent ou illisible')
    elif not os.path.isdir(os.path.join(sync_dir(p), 'corps')):
        out['reasons'].append('corps/ absent')
    if not out['reasons']:
        touched = out['modified'] + out['removed']
        for x in plan['pages']:
            if not os.path.isfile(corps_path(p, x)) or any(cites_doc(x.get('sources'), f) for f in touched):
                out['pages_to_rewrite'].append(x['cle'])
            else:
                out['pages_to_keep'].append(x['cle'])
        if (out['added'] or out['removed']) and 'racine' in out['pages_to_keep']:
            out['pages_to_keep'].remove('racine'); out['pages_to_rewrite'].insert(0, 'racine')  # le sommaire change
        # corps précédents conservés : l'agent recopie ceux des pages à garder même s'il réécrit corps/
        prev = os.path.join(sync_dir(p), 'previous')
        shutil.rmtree(prev, ignore_errors=True)
        shutil.copytree(os.path.join(sync_dir(p), 'corps'), os.path.join(prev, 'corps'))
        shutil.copy2(os.path.join(sync_dir(p), 'plan.json'), os.path.join(prev, 'plan.json'))
        out['previous'] = os.path.abspath(prev)
    out['full'] = bool(out['reasons'])
    print(json.dumps(out, ensure_ascii=False, indent=1))


def cmd_documents(p):
    for f in source_files(p):
        print(os.path.relpath(f, p).replace(os.sep, '/'))


def cmd_verifier(p):
    errs = []
    plan = load(os.path.join(sync_dir(p), 'plan.json'))
    if not plan or not plan.get('pages'):
        print('plan.json absent ou illisible'); return 1
    keys = [x['cle'] for x in plan['pages']]
    if keys[0] != 'racine':
        errs.append('la première page du plan doit être « racine »')
    for x in plan['pages']:
        for f in ('cle', 'titre', 'format'):
            if not x.get(f):
                errs.append(f"{x.get('cle')} : champ « {f} » manquant")
        if x.get('parent') and x['parent'] not in keys:
            errs.append(f"{x['cle']} : parente inconnue « {x['parent']} »")
    texts, cites = {}, set()
    if len(set(keys)) != len(keys):
        errs.append('clé en double dans le plan : ' + ', '.join(sorted({k for k in keys if keys.count(k) > 1})))
    for x in plan['pages']:
        if x.get('format') not in ('markdown', 'html'):
            errs.append(f"{x.get('cle')} : format inconnu « {x.get('format')} » (markdown ou html)")
    for x in plan['pages']:
        cp = corps_path(p, x)
        if not os.path.isfile(cp):
            errs.append(f"{x['cle']} : corps absent ({os.path.relpath(cp, p)})"); continue
        t = open(cp, encoding='utf-8').read(); texts[x['cle']] = t
        for k in (a or b for a, b in LINK.findall(t)):
            if k not in keys:
                errs.append(f"{x['cle']} : lien vers une page absente du plan « page:{k} »")
        for f in re.findall(r'\{\{spec:([^}]+)\}\}', t):
            if not in_docs(p, f):
                errs.append(f"{x['cle']} : spécification introuvable ou hors de docs/ « {f} »")
            elif x.get('format') != 'html':
                errs.append(f"{x['cle']} : {{{{spec:…}}}} n'est permis que dans une page Contrat (format html)")
            cites.add(os.path.realpath(os.path.join(p, f)))
        # « Fichier : <chemin> » : seulement la spécification YAML jointe à une page Contrat
        specs = set(re.findall(r'\{\{spec:([^}]+)\}\}', t))
        for m in FICHIER.finditer(t):
            chemin = m.group(1)
            if not (x.get('format') == 'html' and YAML_CONTRAT.fullmatch(chemin) and chemin in specs):
                errs.append(f"{x['cle']} : « Fichier : {chemin} » — un chemin n'est permis que pour la spécification "
                            f"YAML jointe à une page Contrat")
        bare = strip_code(t)
        for rx, label in PROCESS:
            m = re.search(rx, bare)
            if m:
                errs.append(f"{x['cle']} : {label} (« {bare[max(0, m.start() - 30):m.end() + 30].strip()} »)")
    if 'racine' in texts and '{{date_synchro}}' not in texts['racine']:
        errs.append('racine : marqueur {{date_synchro}} absent')
    # docs/ est publié en entier : chaque document doit nourrir au moins une page, chaque spécification sa page Contrat
    cited_docs = {s.split('§')[0].split('#')[0].strip() for x in plan['pages'] for s in x.get('sources', [])}
    src = set()
    for f in source_files(p):
        rel = os.path.relpath(f, p).replace(os.sep, '/')
        if is_contract(p, f):
            if os.path.realpath(f) not in cites:
                errs.append(f'spécification non publiée : {rel} (aucun {{{{spec:{rel}}}}} dans une page Contrat)')
            continue
        if rel not in cited_docs and not any(rel.startswith(c.rstrip('/') + '/') for c in cited_docs if c.endswith('/')):
            errs.append(f'document non publié : {rel} (cité dans les « sources » d\'aucune page du plan)')
        if f.endswith('.md'):
            src |= set(IDS.findall(open(f, encoding='utf-8', errors='replace').read()))
    published = set(IDS.findall('\n'.join(texts.values())))
    retired = {r['id'] for r in plan.get('ids_retires', [])}
    for i in sorted(src - published - retired, key=lambda s: (s.split('-')[0], int(s.split('-')[1]))):
        errs.append(f'identifiant perdu : {i} (ni publié, ni dans ids_retires)')
    for e in errs:
        print(e)
    return 1 if errs else 0


def contract_key(fichier, homonymes=()):
    """Clé de la page Contrat d'un fichier de docs/contrats/ : « contrat-<nom> » (nom avant le premier point), ou
    « contrat-<nom>-<type> » (type = segment suivant : openapi, asyncapi…) si un autre fichier porte le même nom."""
    parts = os.path.basename(fichier).split('.')
    nom, typ = parts[0], (parts[1] if len(parts) > 2 else '')
    autres = [h for h in homonymes if os.path.basename(h) != os.path.basename(fichier) and os.path.basename(h).split('.')[0] == nom]
    return f'contrat-{nom}-{typ}' if autres and typ else f'contrat-{nom}'


def migrate(cfg):
    pages = cfg.setdefault('pages', {})
    old_contracts = [k for k in pages if re.match(r'docs/contrats/[^.]+\.', k)]
    for k in list(pages):
        new = OLD.get(k)
        if not new and k in old_contracts:
            new = contract_key(k, old_contracts)
        if not new:
            m = re.match(r'docs/adr/(\d{4})-', k)
            new = f'adr-{m.group(1)}' if m else None
        if new and new not in pages:
            pages[new] = pages.pop(k)
    return cfg


def cmd_squelette(p):
    cfg = migrate(load(cfg_path(p), {}))
    save(cfg_path(p), cfg)
    plan = load(os.path.join(sync_dir(p), 'plan.json'))
    if not plan:  # première synchro : pas encore de mise en page, seule la migration compte
        print(json.dumps(dict(pages=[], orphelines=[]), ensure_ascii=False, indent=1))
        return
    known = dict(cfg.get('pages', {})); known['racine'] = cfg.get('racine') or {}
    out = []
    for x in plan['pages']:
        k = known.get(x['cle']) or {}
        out.append(dict(cle=x['cle'], titre=x['titre'], parent=x.get('parent'), id=k.get('id'),
                        parent_id=(known.get(x['parent']) or {}).get('id') if x.get('parent') else None))
    orph = [dict(cle=k, titre=v.get('titre'), url=v.get('url')) for k, v in cfg.get('pages', {}).items() if k not in {x['cle'] for x in plan['pages']}]
    print(json.dumps(dict(pages=out, orphelines=orph), ensure_ascii=False, indent=1))


def cmd_enregistrer(p, cle, pid, titre, url):
    cfg = load(cfg_path(p), {})
    entry = dict(id=pid, titre=titre, url=url, empreinte=None)
    if cle == 'racine':
        cfg['racine'] = {**(cfg.get('racine') or {}), **entry}
    else:
        cfg.setdefault('pages', {})[cle] = {**cfg.get('pages', {}).get(cle, {}), **entry}
    save(cfg_path(p), cfg)


def cmd_ordre(p, enfants_path):
    cfg = load(cfg_path(p), {}); plan = load(os.path.join(sync_dir(p), 'plan.json'))
    ids = dict((k, v.get('id')) for k, v in cfg.get('pages', {}).items()); ids['racine'] = (cfg.get('racine') or {}).get('id')
    enfants = load(enfants_path, {})
    where = {c: par for par, cs in enfants.items() for c in cs}
    # une page inconnue côté Confluence (supprimée à la main : à oublier avec forget) n'est ni déplacée ni cible
    present = set(enfants) | set(where)
    ids = {k: v for k, v in ids.items() if v in present}
    moves = []
    for x in plan['pages'][1:]:
        pid, parid = ids.get(x['cle']), ids.get(x['parent'])
        if pid and parid and where.get(pid) != parid:
            moves.append(dict(id=pid, position='append', targetId=parid)); enfants.setdefault(parid, []).append(pid)
            if where.get(pid) in enfants:
                enfants[where[pid]].remove(pid)
            where[pid] = parid
    for par in {x['parent'] for x in plan['pages'][1:]}:
        parid = ids.get(par)
        if not parid:
            continue
        have = [c for c in enfants.get(parid, []) if c in ids.values()]
        want = [ids[x['cle']] for x in plan['pages'] if x.get('parent') == par and ids.get(x['cle']) in have]
        have = [c for c in have if c in want]
        for i in range(len(want) - 2, -1, -1):  # place chaque page avant la suivante attendue
            if have.index(want[i]) > have.index(want[i + 1]):
                moves.append(dict(id=want[i], position='before', targetId=want[i + 1]))
                have.remove(want[i]); have.insert(have.index(want[i + 1]), want[i])
    print(json.dumps(moves, ensure_ascii=False))


def cmd_forget(p, cle):
    """Page supprimée à la main dans Confluence : retire son id de confluence.json pour que le squelette la recrée."""
    cfg = load(cfg_path(p), {})
    k = cfg.get('racine') if cle == 'racine' else cfg.get('pages', {}).get(cle)
    if not k or not k.get('id'):
        print(f'clé inconnue ou sans id dans confluence.json : « {cle} »'); return 1
    for f in ('id', 'url', 'statut', 'diagrammes', 'pieces_jointes', 'maj', 'files'):
        k.pop(f, None)
    k['empreinte'] = None
    save(cfg_path(p), cfg)
    print(f'{cle} oubliée : elle sera recréée par le squelette à la prochaine synchro')
    return 0


def statut_cadrage(p):
    def field(f, name):
        if not os.path.isfile(f):
            return None
        with open(f, encoding='utf-8') as fh:
            m = re.search(rf'^{name}:\s*(.+)$', fh.read(), re.M)
        return m.group(1).strip() if m else None
    st = lambda f: field(f, 'statut')
    d = os.path.join(p, 'docs')
    ok = all(st(os.path.join(d, f)) == 'validé' for f in ('prd.md', 'architecture.md', 'adr/index.md')) and st(os.path.join(p, '.sohub-plugin', 'backlog.md')) == 'validé'
    if ok:
        return ('Cadrage validé', '#36B37E')
    return ('Rétro-documenté', '#6554C0') if field(os.path.join(d, 'prd.md'), 'origine') == 'rétro' else ('En cadrage', '#FF8B00')


def titre_retenu(x, k):
    """Titre publié gardé s'il ne diffère du plan que par le suffixe « (<Projet>) » posé lors d'un conflit."""
    t = k.get('titre')
    return t if t and (t == x['titre'] or t.startswith(x['titre'] + ' (')) else x['titre']


def cmd_resoudre(p, date):
    cfg = migrate(load(cfg_path(p), {})); save(cfg_path(p), cfg)
    plan = load(os.path.join(sync_dir(p), 'plan.json'))
    if not plan or not plan.get('pages'):
        print('plan.json absent ou illisible : lancer la mise en page'); return 1
    absents = [os.path.relpath(corps_path(p, x), p) for x in plan['pages'] if not os.path.isfile(corps_path(p, x))]
    if absents:
        print('CORPS ABSENT(S) : ' + ', '.join(absents) + ' — relancer la mise en page (verifier)'); return 1
    known = dict(cfg.get('pages', {})); known['racine'] = cfg.get('racine') or {}
    refuse = bool(cfg.get('statut_natif_refuse'))
    rendu = mmdc_cmd() is not None
    out_dir = os.path.join(sync_dir(p), 'final'); os.makedirs(out_dir, exist_ok=True)
    for f in glob.glob(os.path.join(out_dir, '*')):
        os.remove(f)
    cadrage = statut_cadrage(p)
    pages, missing = [], []

    def url(k):
        u = (known.get(k) or {}).get('url')
        if not u:
            missing.append(k)
        return u or f'page:{k}'

    for x in plan['pages']:
        t = open(corps_path(p, x), encoding='utf-8').read()
        t = LINK.sub(lambda m: url(m.group(1) or m.group(2)), t)

        def spec(m):
            if not in_docs(p, m.group(1)):  # jamais un fichier hors de docs/ (contrôlé aussi par verifier)
                raise SystemExit(f"{x['cle']} : spécification hors de docs/ refusée « {m.group(1)} »")
            raw = open(os.path.join(p, m.group(1)), encoding='utf-8').read()
            lang = 'json' if m.group(1).endswith('.json') else 'yaml'
            if x['format'] == 'html':
                return f'<pre><code class="language-{lang}">{html.escape(raw, quote=False)}</code></pre>'
            return f'\n```{lang}\n{raw.rstrip()}\n```\n'
        t = re.sub(r'\{\{spec:([^}]+)\}\}', spec, t)
        empreinte = hashlib.sha256(t.replace('{{date_synchro}}', '').encode()).hexdigest()
        t = t.replace('{{date_synchro}}', date)
        fp = os.path.join(out_dir, os.path.basename(corps_path(p, x))); open(fp, 'w', encoding='utf-8').write(t)
        diagrammes = extract_diagrams(p, x['cle'], t, x['format'])
        # seules les spécifications YAML sont jointes (les autres restent lisibles dans leur bloc repliable)
        jointes = [os.path.realpath(os.path.join(p, f)) for f in re.findall(r'\{\{spec:([^}]+)\}\}', open(corps_path(p, x), encoding='utf-8').read())
                   if x['format'] == 'html' and contrat_yaml(p, f)]
        nat = cadrage if x['cle'] in ('racine', 'glossaire') or x.get('statut') in (None, '—') else statut_natif(x.get('statut'), cadrage)
        k = known.get(x['cle']) or {}
        titre = titre_retenu(x, k)
        if not k.get('id'):
            etat = 'inconnue'
        elif k.get('empreinte') != empreinte or k.get('titre') != titre:
            etat = 'à publier'
        elif rendu and k.get('diagrammes') is not None and k['diagrammes'] < len(diagrammes):
            etat = 'à publier'  # publiée sans images (mmdc absent alors) : les diagrammes peuvent maintenant être rendus
        elif not refuse and k.get('statut') not in (nat[0], x.get('statut')):
            etat = 'statut seul'
        else:
            etat = 'inchangée'
        pages.append(dict(cle=x['cle'], id=k.get('id'), titre=titre, parent=x.get('parent'), corps=os.path.abspath(fp), format=x['format'],
                          statut={'name': nat[0], 'color': nat[1]}, statut_local=x.get('statut'), maj=x.get('maj'), empreinte=empreinte,
                          url=k.get('url'), etat=etat, diagrammes=diagrammes, pieces_jointes=jointes))
    racine = pages[0]
    if racine['etat'] in ('inchangée', 'statut seul') and any(x['etat'] in ('à publier', 'inconnue') for x in pages[1:]):
        racine['etat'] = 'à publier'  # le sommaire et la date de synchro suivent les autres pages
    save(os.path.join(sync_dir(p), 'manifest.json'), dict(projet=plan.get('projet'), statut_natif_refuse=refuse, pages=pages))
    for x in pages:
        print(f"{x['etat']:11} {x['cle']:28} {x['titre']}")
    if missing:
        print('LIENS NON RÉSOLUS (pages sans URL) : ' + ', '.join(sorted(set(missing))))
        return 1
    return 0


DIAG_DIR = ('.sohub-plugin', 'diagrammes')


def extract_diagrams(p, cle, text, fmt):
    """Extrait chaque bloc mermaid du corps final en <projet>/.sohub-plugin/diagrammes/<clé>-<n>.mmd."""
    d = os.path.join(p, *DIAG_DIR); os.makedirs(d, exist_ok=True)
    rx = r'<pre[^>]*><code class="language-mermaid">(.*?)</code></pre>' if fmt == 'html' else r'```mermaid\n(.*?)```'
    out = []
    for n, m in enumerate(re.finditer(rx, text, re.S), 1):
        src = html.unescape(m.group(1)) if fmt == 'html' else m.group(1)
        if src.lstrip().startswith('sequenceDiagram'):  # « ; » dans un message = fin d'instruction pour Mermaid
            src = re.sub(r'^(\s*\S+\s*-[->x)]+\s*\S+\s*:)(.*)$', lambda mm: mm.group(1) + mm.group(2).replace(';', ','), src, flags=re.M)
        before = text[:m.start()]
        heads = re.findall(r'(?m)^#{1,6}\s+(.+)$', before) + re.findall(r'<h[1-6][^>]*>(.*?)</h[1-6]>', before)
        mmd = os.path.join(d, f'{cle}-{n}.mmd')
        if not os.path.isfile(mmd) or open(mmd, encoding='utf-8').read() != src:
            open(mmd, 'w', encoding='utf-8').write(src)
        out.append(dict(mmd=os.path.abspath(mmd), png=os.path.abspath(mmd[:-4] + '.png'), titre=(heads[-1].strip() if heads else cle)))
    return out


WIN_MOUNT = '/mnt/'  # sous WSL, disques Windows : un mmdc Windows trouvé là ne sait pas lire les chemins Linux


def is_wsl():
    try:
        return 'WSL_DISTRO_NAME' in os.environ or 'microsoft' in open('/proc/version').read().lower()
    except OSError:
        return False


def mmdc_cmd():
    path = os.environ.get('PATH', os.defpath).split(os.pathsep)
    if is_wsl():
        path = [d for d in path if not os.path.realpath(d or '.').startswith(WIN_MOUNT)]
    found = shutil.which('mmdc', path=os.pathsep.join(path))
    if found and not (is_wsl() and os.path.realpath(found).startswith(WIN_MOUNT)):
        return [found]
    nvm = os.path.expanduser('~/.nvm/nvm.sh')
    return ['bash', '-c', f'source {shlex.quote(nvm)} && mmdc "$@"', 'mmdc'] if os.path.isfile(nvm) else None


def png_ok(dg):
    """Vrai si le PNG du diagramme existe et n'est pas plus ancien que sa source .mmd."""
    png = dg.get('png')
    return bool(png) and os.path.isfile(png) and (not os.path.isfile(dg.get('mmd') or '') or os.path.getmtime(png) >= os.path.getmtime(dg['mmd']))


def cmd_rendre(p, config):
    man_path = os.path.join(sync_dir(p), 'manifest.json'); man = load(man_path)
    todo = [dg for x in man['pages'] if x['etat'] in ('à publier', 'inconnue') for dg in x.get('diagrammes', [])
            if not os.path.isfile(dg['png']) or os.path.getmtime(dg['png']) < os.path.getmtime(dg['mmd'])]
    base = mmdc_cmd()
    if todo and not base:
        print('MMDC ABSENT : diagrammes non rendus (proposer /install-deps)'); return 1

    def run(dg):
        if os.path.isfile(dg['png']):  # jamais d'image périmée si le rendu échoue
            os.remove(dg['png'])
        r = subprocess.run(base + ['-i', dg['mmd'], '-o', dg['png'], '-b', 'white', '-s', '2', '-p', config], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(dg['png']):
            if os.path.isfile(dg['png']):
                os.remove(dg['png'])
            err = next((l for l in (r.stderr + r.stdout).splitlines() if 'Error' in l), (r.stderr or r.stdout).strip()[-200:])
            return f"ÉCHEC {os.path.basename(dg['mmd'])} : {err}"
        return None
    with ThreadPoolExecutor(4) as ex:
        errs = [e for e in ex.map(run, todo) if e]
    for e in errs:
        print(e)
    print(f'{len(todo) - len(errs)} diagramme(s) rendu(s), {len(errs)} échec(s)')
    return 0


def reuse_of(known, name, sha):
    """Pièce déjà jointe à l'identique (même sha256, fileId connu) : {fileId, attachmentId}, sinon None."""
    e = ((known or {}).get('files') or {}).get(name) or {}
    if sha and e.get('sha256') == sha and e.get('fileId'):
        return dict(fileId=e['fileId'], attachmentId=e.get('attachmentId'))
    return None


def lot_files(known, x):
    """Diagrammes et pièces jointes d'une page du manifest, avec sha256 et `reuse` s'ils sont déjà joints à l'identique."""
    diags = []
    for d in x.get('diagrammes', []):
        png = d['png'] if png_ok(d) else None
        sha = file_sha(png) if png else None
        diags.append(dict(png=png, titre=d['titre'], sha256=sha, reuse=reuse_of(known, os.path.basename(png), sha) if png else None))
    pieces = []
    for j in x.get('pieces_jointes', []):
        sha = file_sha(j) if os.path.isfile(j) else None
        pieces.append(dict(path=j, sha256=sha, reuse=reuse_of(known, os.path.basename(j), sha)))
    return diags, pieces


def contrat_yaml(p, path):
    """Vrai si `path` (absolu, ou relatif au projet) est une spécification YAML de <projet>/docs/contrats/."""
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(p, path))
    return in_docs(p, real) and bool(YAML_CONTRAT.fullmatch(os.path.relpath(real, p).replace(os.sep, '/')))


def piece_path(j):
    """Chemin d'une pièce jointe de lot (chaîne, ou objet {path, sha256, reuse})."""
    return j if isinstance(j, str) else j.get('path')


def cmd_lots(p, n=6, failed=False):
    cfg = load(cfg_path(p), {}); man = load(os.path.join(sync_dir(p), 'manifest.json'))
    known = dict(cfg.get('pages', {})); known['racine'] = cfg.get('racine') or {}
    if not man:
        print('manifest.json absent : lancer resoudre'); return 1
    if failed:
        keys = set(load(os.path.join(sync_dir(p), 'failed.json'), []) or [])
        todo = [x for x in man['pages'] if x['cle'] in keys]
    else:
        todo = [x for x in man['pages'] if x['etat'] == 'à publier']
    for f in glob.glob(os.path.join(sync_dir(p), 'lot-*.json')):
        os.remove(f)
    files = {x['cle']: lot_files(known.get(x['cle']), x) for x in todo}
    # une pièce réutilisée ne coûte rien à envoyer ; un diagramme réutilisé reste à insérer
    size = lambda x: (1 + sum(1 if d['reuse'] else 2 for d in files[x['cle']][0] if d['png'])
                      + len([j for j in files[x['cle']][1] if not j['reuse']]) + os.path.getsize(x['corps']) // 20000)
    lots = [[] for _ in range(min(n, len(todo)))]
    for x in sorted(todo, key=size, reverse=True):
        min(lots, key=lambda l: sum(map(size, l))).append(x)
    reused = 0
    for i, l in enumerate(lots, 1):
        save(os.path.join(sync_dir(p), f'lot-{i}.json'), dict(cloudId=cfg.get('cloudId'), statut_natif_refuse=bool(cfg.get('statut_natif_refuse')), pages=[
            dict(cle=x['cle'], id=x['id'], titre=x['titre'], corps=x['corps'], format=x['format'], statut=x['statut'],
                 statut_local=x['statut_local'], maj=x['maj'], empreinte=x['empreinte'], url=x['url'],
                 diagrammes=files[x['cle']][0], pieces_jointes=files[x['cle']][1]) for x in l]))
        reused += sum(1 for x in l for f in files[x['cle']][0] + files[x['cle']][1] if f['reuse'])
        print(f"lot-{i} : " + ', '.join(x['cle'] for x in l))
    if reused:
        print(f'{reused} fichier(s) déjà joint(s) à l\'identique : non renvoyé(s)')
    if not todo:
        print('aucune page à publier')
    return 0


def cmd_fusionner(p, src_hash):
    cfg = load(cfg_path(p), {}); man = {x['cle']: x for x in load(os.path.join(sync_dir(p), 'manifest.json'))['pages']}
    lot = {x['cle']: x for f in glob.glob(os.path.join(sync_dir(p), 'lot-*.json')) for x in (load(f, {}) or {}).get('pages', [])}
    echecs = []
    for f in sorted(glob.glob(os.path.join(sync_dir(p), 'resultats-*.json'))):
        for k, v in load(f, {}).items():
            if k == 'racine':
                target = cfg['racine'] = cfg.get('racine') or {}
            else:
                target = cfg.setdefault('pages', {}).setdefault(k, {})
            mk = man.get(k) or {}
            attendus = len([d for d in mk.get('diagrammes', []) if png_ok(d)])
            if v.get('statut_natif') == 'refusé':
                cfg['statut_natif_refuse'] = True  # statuts personnalisés désactivés ou droits : on ne les redemande plus
            # fichiers du lot : sha256 (fait foi) et pièces réutilisées (déjà jointes à l'identique : comptent comme jointes)
            lp = lot.get(k) or {}
            entries = [(os.path.basename(d['png']), d) for d in lp.get('diagrammes', []) if isinstance(d, dict) and d.get('png')]
            entries += [(os.path.basename(piece_path(j)), j) for j in lp.get('pieces_jointes', []) if isinstance(j, dict)]
            reuse = {name: e['reuse'] for name, e in entries if e.get('reuse')}
            shas = {name: e.get('sha256') for name, e in entries}
            sent = {name: r for name, r in (v.get('files') or {}).items() if isinstance(r, dict) and r.get('fileId')}
            pieces = [os.path.basename(j) for j in mk.get('pieces_jointes', [])]
            if 'files' in v:
                jointes = len([n for n in pieces if n in reuse or n in sent])
            else:
                jointes = v.get('pieces_jointes', 0) + len([n for n in pieces if n in reuse])
            incomplet = v.get('ok') and (v.get('diagrammes', 0) < attendus or jointes < len(pieces))
            if incomplet:
                echecs.append((k, f"incomplète : {v.get('diagrammes', 0)}/{attendus} diagramme(s), {jointes}/{len(pieces)} pièce(s) jointe(s) — republiée à la prochaine synchro"))
            if v.get('ok'):
                target.update(id=v.get('id') or target.get('id'), titre=v.get('titre') or target.get('titre'), maj=v.get('maj'), empreinte=v.get('empreinte'),
                              statut=(man.get(k) or {}).get('statut', {}).get('name') if v.get('statut_natif') != 'refusé' else target.get('statut'),
                              format=(man.get(k) or {}).get('format'), url=v.get('url') or target.get('url'),
                              diagrammes=v.get('diagrammes', 0), pieces_jointes=jointes)
                files = dict(target.get('files') or {})
                for name, r in reuse.items():
                    files[name] = dict(sha256=shas.get(name), fileId=r.get('fileId'), attachmentId=r.get('attachmentId'))
                for name, r in sent.items():
                    files[name] = dict(sha256=shas.get(name) or r.get('sha256'), fileId=r['fileId'], attachmentId=r.get('attachmentId'))
                if files:
                    target['files'] = files
                if incomplet:
                    target['empreinte'] = None
            else:
                target['empreinte'] = None; echecs.append((k, v.get('erreurs')))
    # relevé des sources (sha256 par document, agent et gabarit) pris par `sources` pour cette empreinte : base de `changed`
    snap = load(os.path.join(sync_dir(p), 'sources.json'), {}) or {}
    old = cfg.get('transformation') or {}
    if snap.get('empreinte') == src_hash:
        cfg['transformation'] = dict(empreinte=src_hash, files=snap.get('files', {}), plugin=snap.get('plugin', {}))
    elif old.get('empreinte') != src_hash:  # relevé inconnu pour cette empreinte : la prochaine mise en page sera complète
        cfg['transformation'] = dict(empreinte=src_hash)
    save(cfg_path(p), cfg)
    save(os.path.join(sync_dir(p), 'failed.json'), sorted({k for k, _ in echecs}))  # pour lots --failed
    for f in glob.glob(os.path.join(sync_dir(p), 'lot-*.json')) + glob.glob(os.path.join(sync_dir(p), 'resultats-*.json')):
        os.remove(f)
    for k, e in echecs:
        print(f'ÉCHEC {k} : {e}')
    return 1 if echecs else 0


UPLOAD_OPTS = {'-L', '--location', '-X', '--request', '-H', '--header', '-F', '--form', '--url', '-s', '--silent',
               '-S', '--show-error', '-f', '--fail', '--compressed', '--data-binary', '-T', '--upload-file'}
UPLOAD_ARG = {'-X', '--request', '-H', '--header', '-F', '--form', '--url', '--data-binary', '-T', '--upload-file'}


def cmd_upload(p, fichier, commande):
    """Exécute la commande curl d'envoi après contrôle ; seule commande à autoriser pour joindre un fichier."""
    real = os.path.realpath(fichier)
    diag = os.path.realpath(os.path.join(p, *DIAG_DIR))
    # seuls fichiers envoyables : un diagramme rendu (PNG de son .mmd) ou une spécification YAML de docs/contrats/
    ok_file = contrat_yaml(p, real) or (real.startswith(diag + os.sep) and real.endswith('.png') and os.path.isfile(real[:-4] + '.mmd'))
    lots = [load(f, {}) for f in glob.glob(os.path.join(sync_dir(p), 'lot-*.json'))]
    # une pièce marquée `reuse` (déjà jointe à l'identique) n'est pas à renvoyer
    cites = {os.path.realpath(piece_path(j)) for l in lots for x in l.get('pages', []) for j in x.get('pieces_jointes', [])
             if piece_path(j) and not (isinstance(j, dict) and j.get('reuse'))}
    cites |= {os.path.realpath(d['png']) for l in lots for x in l.get('pages', []) for d in x.get('diagrammes', []) if d.get('png') and not d.get('reuse')}
    if not ok_file:
        print(f'REFUS : seuls les diagrammes rendus et les contrats YAML de docs/contrats/ sont envoyés « {fichier} »'); return 1
    if real not in cites:
        print(f'REFUS : fichier absent des lots en cours « {fichier} »'); return 1
    try:
        argv = shlex.split(commande)
    except ValueError as e:
        print(f'REFUS : commande illisible ({e})'); return 1
    if not argv or argv[0] != 'curl':
        print('REFUS : la commande doit être un appel curl'); return 1
    site = urlparse((load(cfg_path(p), {}) or {}).get('site') or '').hostname
    hosts = {h for h in (site, 'api.atlassian.com') if h}
    i, urls = 1, []
    while i < len(argv):
        a = argv[i]
        if a.startswith('-'):
            opt, _, val = a.partition('=') if a.startswith('--') else (a[:2], '', a[2:])
            if opt not in UPLOAD_OPTS or (val and not a.startswith('--') and opt not in UPLOAD_ARG):
                print(f'REFUS : option non permise « {a} »'); return 1
            if opt in UPLOAD_ARG and not val:
                i += 1
                val = argv[i] if i < len(argv) else ''
            if opt == '--url':
                urls.append(val)
            # fichier lu par curl : -F nom=@f / nom=<f (avant le premier « ; »), --data-binary @f, -T f
            if opt in ('-F', '--form'):
                v = val.split(';', 1)[0].partition('=')[2]
                ref = v[1:] if v[:1] in ('@', '<') else None
            elif opt == '--data-binary':
                ref = val[1:] if val.startswith('@') else None
            elif opt in ('-T', '--upload-file'):
                ref = val
            else:
                ref = None
            if ref is not None and os.path.realpath(os.path.expanduser(ref.strip('"\''))) != real:
                print(f'REFUS : la commande envoie un autre fichier que « {fichier} »'); return 1
        else:
            urls.append(a)
        i += 1
    if not urls or any(urlparse(u).scheme != 'https' or urlparse(u).hostname not in hosts for u in urls):
        print('REFUS : adresse non permise (https vers ' + ' ou '.join(sorted(hosts)) + ' seulement)'); return 1
    if os.environ.get('SOHUB_UPLOAD_DRY_RUN') == '1':
        print('DRY-RUN : ' + shlex.join(argv)); return 0
    r = subprocess.run(argv, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stdout.write(r.stderr[-500:])
    return r.returncode


if __name__ == '__main__':
    a = sys.argv[1:]
    cmds = {'sources': (cmd_sources, 2), 'changed': (cmd_changed, 2), 'verifier': (cmd_verifier, 1), 'squelette': (cmd_squelette, 1), 'enregistrer': (cmd_enregistrer, 5),
            'ordre': (cmd_ordre, 2), 'resoudre': (cmd_resoudre, 2), 'rendre': (cmd_rendre, 2), 'lots': (cmd_lots, 1), 'fusionner': (cmd_fusionner, 2),
            'documents': (cmd_documents, 1), 'upload': (cmd_upload, 3), 'forget': (cmd_forget, 2)}
    if not a or a[0] not in cmds or len(a) - 1 < cmds[a[0]][1]:
        print(__doc__, file=sys.stderr); sys.exit(2)
    fn, n = cmds[a[0]]
    args = [os.path.abspath(a[1])] + a[2:]
    if a[0] == 'lots':
        rest = [x for x in args[1:] if x != '--failed']
        try:
            args = [args[0], int(rest[0]) if rest else 6, '--failed' in args[1:]]
        except ValueError:
            print(__doc__, file=sys.stderr); sys.exit(2)
    sys.exit(fn(*args) or 0)
