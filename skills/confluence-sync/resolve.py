#!/usr/bin/env python3
"""Partie mécanique de /confluence-sync, autour du travail de l'agent layout.

L'agent écrit .sohub-plugin/sync/plan.json et .sohub-plugin/sync/corps/<clé>.(md|html), avec des liens
symboliques `page:<clé>` et des marqueurs `{{spec:docs/contrats/<fichier>}}` / `{{date_synchro}}`. Ce script :

  sources    <projet> <dossier du plugin>   empreinte des sources (tout docs/ sauf docs/eval/, + agent + gabarit) → stdout
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
  lots       <projet> [nombre max]          écrit .sohub-plugin/sync/lot-<n>.json (pages à publier)
  fusionner  <projet> <empreinte sources>   fusionne resultats-*.json dans confluence.json, supprime lots et résultats
  upload     <projet> <fichier> <commande curl>   exécute la commande d'envoi renvoyée par createConfluenceAttachment
                                            après contrôle : fichier sous docs/ (ou PNG d'un diagramme extrait), cité
                                            par un lot, hôte = site de confluence.json ou api.atlassian.com, options sûres

Seul le dossier docs/ du projet est publié (sauf docs/eval/, historique du processus) : aucun fichier hors de docs/
n'est lu dans une page ni joint.
"""
import glob, hashlib, html, json, os, re, shlex, shutil, subprocess, sys
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

PROCESS = [(r'§', '« § »'), (r'(?m)^#{1,6}\s+\d+(?:\.\d+)*\.?\s', 'titre numéroté'),
           (r'<h[1-6][^>]*>\s*\d+(?:\.\d+)*\.?\s', 'titre numéroté'), (r'\bI-\d{2}\b', 'identifiant de processus I-xx'),
           (r'\bS[1-9]\b', 'identifiant de processus Sx'), (r'structure validée', '« structure validée »'),
           (r'https?://[^\s)"]*atlassian\.net', 'URL Confluence écrite en dur')]
LINK = re.compile(r'(?<=\]\()page:([\w.-]+)|(?<=href=")page:([\w.-]+)')
IDS = re.compile(r'\b(?:CU|EF|RG|ENF|EC|CMP|FL|CTR|CH|QA|Q|OBJ|CT)-\d+\b')
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
    """Vrai si `path` (absolu, ou relatif au projet) désigne un fichier sous <projet>/docs/, hors docs/eval/."""
    real = os.path.realpath(path if os.path.isabs(path) else os.path.join(p, path))
    d = docs_dir(p)
    return real.startswith(d + os.sep) and not real.startswith(os.path.join(d, 'eval') + os.sep) and os.path.isfile(real)


def source_files(p):
    """Tous les fichiers publiables : docs/ entier, récursif, sauf docs/eval/ et les fichiers cachés."""
    out = []
    for root, dirs, files in os.walk(os.path.join(p, 'docs')):
        dirs[:] = sorted(x for x in dirs if not x.startswith('.') and not (root == os.path.join(p, 'docs') and x == 'eval'))
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


def cmd_sources(p, plugin):
    # chemins relatifs : l'empreinte ne change ni quand le projet est déplacé, ni quand le plugin change de dossier
    h = hashlib.sha256()
    files = [(os.path.relpath(f, p), f) for f in source_files(p)]
    files += [(r, os.path.join(plugin, r)) for r in ('agents/layout.md', 'templates/confluence-tree.md')]
    for rel, f in files:
        if os.path.isfile(f):
            h.update(rel.replace(os.sep, '/').encode()); h.update(open(f, 'rb').read())
    print(h.hexdigest())


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


def migrate(cfg):
    pages = cfg.setdefault('pages', {})
    for k in list(pages):
        new = OLD.get(k)
        if not new:
            m = re.match(r'docs/contrats/([^.]+)\.', k)
            new = f'contrat-{m.group(1)}' if m else None
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
        want = [ids[x['cle']] for x in plan['pages'] if x.get('parent') == par and ids.get(x['cle'])]
        have = [c for c in enfants.get(parid, []) if c in want]
        for i in range(len(want) - 2, -1, -1):  # place chaque page avant la suivante attendue
            if have.index(want[i]) > have.index(want[i + 1]):
                moves.append(dict(id=want[i], position='before', targetId=want[i + 1]))
                have.remove(want[i]); have.insert(have.index(want[i + 1]), want[i])
    print(json.dumps(moves, ensure_ascii=False))


def statut_cadrage(p):
    def st(f):
        m = re.search(r'^statut:\s*(.+)$', open(f, encoding='utf-8').read(), re.M) if os.path.isfile(f) else None
        return m.group(1).strip() if m else None
    d = os.path.join(p, 'docs')
    ok = all(st(os.path.join(d, f)) == 'validé' for f in ('prd.md', 'architecture.md', 'adr/index.md')) and st(os.path.join(p, '.sohub-plugin', 'backlog.md')) == 'validé'
    return ('Cadrage validé', '#36B37E') if ok else ('En cadrage', '#FF8B00')


def titre_retenu(x, k):
    """Titre publié gardé s'il ne diffère du plan que par le suffixe « (<Projet>) » posé lors d'un conflit."""
    t = k.get('titre')
    return t if t and (t == x['titre'] or t.startswith(x['titre'] + ' (')) else x['titre']


def cmd_resoudre(p, date):
    cfg = migrate(load(cfg_path(p), {})); save(cfg_path(p), cfg)
    plan = load(os.path.join(sync_dir(p), 'plan.json'))
    known = dict(cfg.get('pages', {})); known['racine'] = cfg.get('racine') or {}
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
        jointes = [os.path.realpath(os.path.join(p, f)) for f in re.findall(r'\{\{spec:([^}]+)\}\}', open(corps_path(p, x), encoding='utf-8').read())
                   if x['format'] == 'html' and in_docs(p, f)]
        nat = cadrage if x['cle'] in ('racine', 'glossaire') or x.get('statut') in (None, '—') else statut_natif(x.get('statut'), cadrage)
        k = known.get(x['cle']) or {}
        titre = titre_retenu(x, k)
        if not k.get('id'):
            etat = 'inconnue'
        elif k.get('empreinte') != empreinte or k.get('titre') != titre:
            etat = 'à publier'
        elif k.get('statut') not in (nat[0], x.get('statut')):
            etat = 'statut seul'
        else:
            etat = 'inchangée'
        pages.append(dict(cle=x['cle'], id=k.get('id'), titre=titre, parent=x.get('parent'), corps=os.path.abspath(fp), format=x['format'],
                          statut={'name': nat[0], 'color': nat[1]}, statut_local=x.get('statut'), maj=x.get('maj'), empreinte=empreinte,
                          url=k.get('url'), etat=etat, diagrammes=diagrammes, pieces_jointes=jointes))
    racine = pages[0]
    if racine['etat'] in ('inchangée', 'statut seul') and any(x['etat'] in ('à publier', 'inconnue') for x in pages[1:]):
        racine['etat'] = 'à publier'  # le sommaire et la date de synchro suivent les autres pages
    save(os.path.join(sync_dir(p), 'manifest.json'), dict(projet=plan.get('projet'), pages=pages))
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


def mmdc_cmd():
    if shutil.which('mmdc'):
        return ['mmdc']
    nvm = os.path.expanduser('~/.nvm/nvm.sh')
    return ['bash', '-c', f'source {nvm} && mmdc "$@"', 'mmdc'] if os.path.isfile(nvm) else None


def cmd_rendre(p, config):
    man_path = os.path.join(sync_dir(p), 'manifest.json'); man = load(man_path)
    todo = [dg for x in man['pages'] if x['etat'] in ('à publier', 'inconnue') for dg in x.get('diagrammes', [])
            if not os.path.isfile(dg['png']) or os.path.getmtime(dg['png']) < os.path.getmtime(dg['mmd'])]
    base = mmdc_cmd()
    if todo and not base:
        print('MMDC ABSENT : diagrammes non rendus (proposer /install)'); return 1

    def run(dg):
        r = subprocess.run(base + ['-i', dg['mmd'], '-o', dg['png'], '-b', 'white', '-s', '2', '-p', config], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.isfile(dg['png']):
            err = next((l for l in (r.stderr + r.stdout).splitlines() if 'Error' in l), (r.stderr or r.stdout).strip()[-200:])
            return f"ÉCHEC {os.path.basename(dg['mmd'])} : {err}"
        return None
    with ThreadPoolExecutor(4) as ex:
        errs = [e for e in ex.map(run, todo) if e]
    for e in errs:
        print(e)
    print(f'{len(todo) - len(errs)} diagramme(s) rendu(s), {len(errs)} échec(s)')
    return 0


def cmd_lots(p, n=6):
    cfg = load(cfg_path(p), {}); man = load(os.path.join(sync_dir(p), 'manifest.json'))
    todo = [x for x in man['pages'] if x['etat'] == 'à publier']
    for f in glob.glob(os.path.join(sync_dir(p), 'lot-*.json')):
        os.remove(f)
    size = lambda x: 1 + 2 * len([d for d in x.get('diagrammes', []) if os.path.isfile(d['png'])]) + len(x.get('pieces_jointes', [])) + os.path.getsize(x['corps']) // 20000
    lots = [[] for _ in range(min(n, len(todo)))]
    for x in sorted(todo, key=size, reverse=True):
        min(lots, key=lambda l: sum(map(size, l))).append(x)
    for i, l in enumerate(lots, 1):
        save(os.path.join(sync_dir(p), f'lot-{i}.json'), dict(cloudId=cfg.get('cloudId'), pages=[
            dict(cle=x['cle'], id=x['id'], titre=x['titre'], corps=x['corps'], format=x['format'], statut=x['statut'],
                 statut_local=x['statut_local'], maj=x['maj'], empreinte=x['empreinte'], url=x['url'],
                 diagrammes=[dict(png=d['png'] if os.path.isfile(d['png']) else None, titre=d['titre']) for d in x.get('diagrammes', [])],
                 pieces_jointes=x.get('pieces_jointes', [])) for x in l]))
        print(f"lot-{i} : " + ', '.join(x['cle'] for x in l))


def cmd_fusionner(p, src_hash):
    cfg = load(cfg_path(p), {}); man = {x['cle']: x for x in load(os.path.join(sync_dir(p), 'manifest.json'))['pages']}
    echecs = []
    for f in sorted(glob.glob(os.path.join(sync_dir(p), 'resultats-*.json'))):
        for k, v in load(f, {}).items():
            target = cfg['racine'] if k == 'racine' else cfg.setdefault('pages', {}).setdefault(k, {})
            mk = man.get(k) or {}
            attendus = len([d for d in mk.get('diagrammes', []) if os.path.isfile(d['png'])])
            incomplet = v.get('ok') and (v.get('diagrammes', 0) < attendus or v.get('pieces_jointes', 0) < len(mk.get('pieces_jointes', [])))
            if incomplet:
                echecs.append((k, f"incomplète : {v.get('diagrammes', 0)}/{attendus} diagramme(s), {v.get('pieces_jointes', 0)}/{len(mk.get('pieces_jointes', []))} pièce(s) jointe(s) — republiée à la prochaine synchro"))
            if v.get('ok'):
                target.update(id=v.get('id') or target.get('id'), titre=v.get('titre') or target.get('titre'), maj=v.get('maj'), empreinte=v.get('empreinte'),
                              statut=(man.get(k) or {}).get('statut', {}).get('name') if v.get('statut_natif') != 'refusé' else target.get('statut'),
                              format=(man.get(k) or {}).get('format'), url=v.get('url') or target.get('url'),
                              diagrammes=v.get('diagrammes', 0), pieces_jointes=v.get('pieces_jointes', 0))
                if incomplet:
                    target['empreinte'] = None
            else:
                target['empreinte'] = None; echecs.append((k, v.get('erreurs')))
    cfg['transformation'] = dict(empreinte=src_hash)
    save(cfg_path(p), cfg)
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
    ok_file = in_docs(p, real) or (real.startswith(diag + os.sep) and real.endswith('.png') and os.path.isfile(real[:-4] + '.mmd'))
    lots = [load(f, {}) for f in glob.glob(os.path.join(sync_dir(p), 'lot-*.json'))]
    cites = {os.path.realpath(j) for l in lots for x in l.get('pages', []) for j in x.get('pieces_jointes', [])}
    cites |= {os.path.realpath(d['png']) for l in lots for x in l.get('pages', []) for d in x.get('diagrammes', []) if d.get('png')}
    if not ok_file:
        print(f'REFUS : fichier hors de docs/ et des diagrammes rendus « {fichier} »'); return 1
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
    r = subprocess.run(argv, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode:
        sys.stdout.write(r.stderr[-500:])
    return r.returncode


if __name__ == '__main__':
    a = sys.argv[1:]
    cmds = {'sources': (cmd_sources, 2), 'verifier': (cmd_verifier, 1), 'squelette': (cmd_squelette, 1), 'enregistrer': (cmd_enregistrer, 5),
            'ordre': (cmd_ordre, 2), 'resoudre': (cmd_resoudre, 2), 'rendre': (cmd_rendre, 2), 'lots': (cmd_lots, 1), 'fusionner': (cmd_fusionner, 2),
            'documents': (cmd_documents, 1), 'upload': (cmd_upload, 3)}
    if not a or a[0] not in cmds or len(a) - 1 < cmds[a[0]][1]:
        print(__doc__, file=sys.stderr); sys.exit(2)
    fn, n = cmds[a[0]]
    args = [os.path.abspath(a[1])] + a[2:]
    if a[0] == 'lots' and len(args) > 1:
        args[1] = int(args[1])
    sys.exit(fn(*args) or 0)
