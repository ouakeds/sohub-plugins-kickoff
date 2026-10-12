"""Tests de skills/confluence-sync/resolve.py (mécanique de /confluence-sync).

Lancement : python3 -I -m unittest discover -s tests   (depuis la racine du dépôt)
Aucun appel réseau : `upload` est testé avec SOHUB_UPLOAD_DRY_RUN=1, mermaid-cli est remplacé par un faux `mmdc`.
"""
import importlib.util, json, os, shlex, shutil, stat, subprocess, sys, tempfile, time, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'skills', 'confluence-sync', 'resolve.py')
SPEC = 'openapi: 3.0.0\ninfo:\n  title: API\n'


def load_module():
    spec = importlib.util.spec_from_file_location('resolve_under_test', SCRIPT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


R = load_module()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


class Project:
    """Projet factice : docs/ (avec eval/ et fichier caché), plan et corps valides pour verifier."""

    def __init__(self, base, mermaid=False):
        self.p = os.path.join(base, 'projet')
        self.tmp = base
        write(self.doc('docs/prd.md'), '---\nstatut: brouillon\n---\n# PRD\n')
        write(self.doc('docs/contrats/api.openapi.yaml'), SPEC)
        write(self.doc('docs/eval/historique.md'), 'S1 : rien\n')
        write(self.doc('docs/.cache.md'), 'caché\n')
        write(self.doc('secret.txt'), 'secret\n')
        self.plan([dict(cle='racine', titre='Projet', format='markdown', sources=['docs/prd.md']),
                   dict(cle='contrat-api', titre='Contrat API', format='html', parent='racine', statut='validé',
                        sources=['docs/contrats/api.openapi.yaml'])])
        body = 'Synchro : {{date_synchro}}\n\nVoir [contrat](page:contrat-api).\n'
        if mermaid:
            body += '\n## Schéma\n\n```mermaid\ngraph TD\n  A-->B\n```\n'
        self.corps('racine.md', body)
        self.corps('contrat-api.html', '<p>API</p><details>{{spec:docs/contrats/api.openapi.yaml}}</details>')
        self.fakebin = os.path.join(base, 'bin'); os.makedirs(self.fakebin, exist_ok=True)
        self.home = os.path.join(base, 'home'); os.makedirs(self.home, exist_ok=True)

    def doc(self, rel):
        return os.path.join(self.p, rel)

    def sync(self, *rel):
        return os.path.join(self.p, '.sohub-plugin', 'sync', *rel)

    def plan(self, pages, **extra):
        write(self.sync('plan.json'), json.dumps(dict(projet='Projet', pages=pages, **extra)))

    def corps(self, name, text):
        write(self.sync('corps', name), text)

    def cfg(self, data=None):
        path = os.path.join(self.p, '.sohub-plugin', 'confluence.json')
        if data is not None:
            write(path, json.dumps(data))
        return read_json(path)

    def fake_mmdc(self, ok=True):
        """Faux mermaid-cli : écrit le PNG demandé (-o) ou échoue."""
        path = os.path.join(self.fakebin, 'mmdc')
        script = ('#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done\nprintf png > "$out"\n' if ok
                  else '#!/bin/sh\necho "Error: parse error" >&2\nexit 1\n')
        write(path, script); os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run(self, *args, env=None):
        e = {'PATH': self.fakebin + os.pathsep + '/usr/bin:/bin', 'HOME': self.home, 'LANG': 'C.UTF-8',
             'SOHUB_UPLOAD_DRY_RUN': '1'}
        e.update(env or {})
        r = subprocess.run([sys.executable, '-I', SCRIPT, args[0], self.p, *args[1:]], capture_output=True, text=True, env=e)
        self.assertNoTraceback(r)
        return r

    @staticmethod
    def assertNoTraceback(r):
        if 'Traceback' in r.stderr:
            raise AssertionError(r.stderr)

    def published(self, extra_racine=None, extra_page=None):
        """confluence.json d'un projet déjà publié, empreintes à jour (calculées par resoudre)."""
        self.cfg(dict(cloudId='c', site='https://exemple.atlassian.net',
                      racine=dict(id='1', url='https://exemple.atlassian.net/wiki/1', titre='Projet'),
                      pages={'contrat-api': dict(id='2', url='https://exemple.atlassian.net/wiki/2', titre='Contrat API')}))
        self.run('resoudre', '2026-01-01 10:00')
        man = read_json(self.sync('manifest.json'))
        cfg = self.cfg()
        for x in man['pages']:
            t = cfg['racine'] if x['cle'] == 'racine' else cfg['pages'][x['cle']]
            t.update(empreinte=x['empreinte'], statut=x['statut']['name'], diagrammes=len(x['diagrammes']))
        cfg['racine'].update(extra_racine or {}); cfg['pages']['contrat-api'].update(extra_page or {})
        self.cfg(cfg)

    def etats(self, env=None):
        r = self.run('resoudre', '2026-01-02 10:00', env=env)
        return {x['cle']: x['etat'] for x in read_json(self.sync('manifest.json'))['pages']}, r


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(); self.addCleanup(self._td.cleanup)
        self.tmp = self._td.name

    def project(self, **kw):
        return Project(self.tmp, **kw)


# ---------------------------------------------------------------- garanties existantes : seul docs/ est publié

class TestDocsOnly(Base):
    def test_documents_all_docs_except_eval_and_hidden(self):
        pr = self.project(); write(pr.doc('docs/sous/dossier/note.md'), 'x\n')
        r = pr.run('documents')
        self.assertEqual(sorted(r.stdout.split()), ['docs/contrats/api.openapi.yaml', 'docs/prd.md', 'docs/sous/dossier/note.md'])

    def test_verifier_accepts_valid_project(self):
        r = self.project().run('verifier')
        self.assertEqual((r.returncode, r.stdout), (0, ''))

    def test_verifier_refuses_spec_outside_docs(self):
        pr = self.project()
        pr.corps('contrat-api.html', '<details>{{spec:docs/contrats/api.openapi.yaml}}</details>{{spec:/etc/hostname}}')
        r = pr.run('verifier')
        self.assertEqual(r.returncode, 1); self.assertIn('hors de docs/ « /etc/hostname »', r.stdout)

    def test_verifier_refuses_spec_in_markdown_page(self):
        pr = self.project()
        pr.corps('racine.md', '{{date_synchro}} {{spec:docs/contrats/api.openapi.yaml}}')
        r = pr.run('verifier')
        self.assertEqual(r.returncode, 1); self.assertIn("n'est permis que dans une page Contrat", r.stdout)

    def test_verifier_refuses_unpublished_document(self):
        pr = self.project(); write(pr.doc('docs/glossaire.md'), '# Glossaire\n')
        r = pr.run('verifier')
        self.assertEqual(r.returncode, 1); self.assertIn('document non publié : docs/glossaire.md', r.stdout)

    def test_verifier_refuses_unpublished_spec(self):
        pr = self.project(); write(pr.doc('docs/contrats/events.asyncapi.yaml'), 'asyncapi: 2.6.0\n')
        r = pr.run('verifier')
        self.assertEqual(r.returncode, 1); self.assertIn('spécification non publiée : docs/contrats/events.asyncapi.yaml', r.stdout)

    def test_sources_fingerprint_independent_of_location(self):
        pr = self.project()
        plugin = os.path.join(self.tmp, 'plugin'); write(os.path.join(plugin, 'agents', 'layout.md'), 'agent\n')
        h1 = pr.run('sources', plugin).stdout.strip()
        other = os.path.join(self.tmp, 'ailleurs', 'copie'); shutil.copytree(pr.p, other)
        plugin2 = os.path.join(self.tmp, 'plugin2'); shutil.copytree(plugin, plugin2)
        r = subprocess.run([sys.executable, '-I', SCRIPT, 'sources', other, plugin2], capture_output=True, text=True)
        self.assertEqual(h1, r.stdout.strip()); self.assertEqual(len(h1), 64)
        write(os.path.join(other, 'docs', 'eval', 'autre.md'), 'ignoré\n')  # docs/eval/ ne compte pas
        r = subprocess.run([sys.executable, '-I', SCRIPT, 'sources', other, plugin2], capture_output=True, text=True)
        self.assertEqual(h1, r.stdout.strip())

    def test_statut_natif_remplace(self):
        self.assertEqual(R.statut_natif('remplacé par ADR-0003', ('X', '#0')), ('Remplacé', '#6B778C'))
        self.assertEqual(R.statut_natif('inconnu', ('X', '#0')), ('X', '#0'))


# ---------------------------------------------------------------- upload

class TestUpload(Base):
    URL = 'https://api.atlassian.com/ex/confluence/c/wiki/rest/api/content/2/child/attachment'

    def setUp(self):
        super().setUp()
        self.pr = self.project()
        self.pr.cfg(dict(cloudId='c', site='https://exemple.atlassian.net', pages={}))
        self.spec = os.path.realpath(self.pr.doc('docs/contrats/api.openapi.yaml'))
        write(self.pr.sync('lot-1.json'), json.dumps(dict(pages=[dict(cle='contrat-api', pieces_jointes=[self.spec], diagrammes=[])])))

    def cmd(self, form=None, extra='', url=None):
        form = form or f'file=@{self.spec};type=application/yaml'
        return (f"curl -s -S -X POST -H 'Authorization: Bearer jeton' -H 'X-Atlassian-Token: no-check' "
                f"-F {shlex.quote(form)} {extra} {url or self.URL}")

    def upload(self, fichier, commande):
        return self.pr.run('upload', fichier, commande)

    def assertRefused(self, r, motif):
        self.assertEqual(r.returncode, 1, r.stdout); self.assertIn('REFUS', r.stdout); self.assertIn(motif, r.stdout)
        self.assertNotIn('DRY-RUN', r.stdout)

    def test_accepts_real_form(self):
        r = self.upload(self.spec, self.cmd())
        self.assertEqual(r.returncode, 0, r.stdout); self.assertTrue(r.stdout.startswith('DRY-RUN : curl '))
        self.assertIn(self.URL, r.stdout)

    def test_accepts_site_host(self):
        r = self.upload(self.spec, self.cmd(url='https://exemple.atlassian.net/wiki/rest/api/content/2/child/attachment'))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_refuses_file_outside_docs(self):
        r = self.upload(self.pr.doc('secret.txt'), self.cmd(form='file=@' + self.pr.doc('secret.txt')))
        self.assertRefused(r, 'hors de docs/')

    def test_refuses_file_in_eval(self):
        f = self.pr.doc('docs/eval/historique.md')
        self.assertRefused(self.upload(f, self.cmd(form='file=@' + f)), 'hors de docs/')

    def test_refuses_file_not_in_lots(self):
        f = os.path.realpath(self.pr.doc('docs/prd.md'))
        self.assertRefused(self.upload(f, self.cmd(form='file=@' + f)), 'absent des lots')

    def test_refuses_other_file_in_form(self):
        self.assertRefused(self.upload(self.spec, self.cmd(form='file=@/etc/passwd')), 'autre fichier')
        self.assertRefused(self.upload(self.spec, self.cmd(form='file=</etc/passwd')), 'autre fichier')
        self.assertRefused(self.upload(self.spec, self.cmd(extra='-F x=@/etc/hostname')), 'autre fichier')

    def test_refuses_output_options(self):
        self.assertRefused(self.upload(self.spec, self.cmd(extra='-o /tmp/x')), 'option non permise « -o »')
        self.assertRefused(self.upload(self.spec, self.cmd(extra='-so /tmp/x')), 'option non permise « -so »')
        self.assertRefused(self.upload(self.spec, self.cmd(extra='--output=/tmp/x')), 'option non permise')

    def test_refuses_other_host_and_http(self):
        self.assertRefused(self.upload(self.spec, self.cmd(url='https://evil.example.com/up')), 'adresse non permise')
        self.assertRefused(self.upload(self.spec, self.cmd(url='http://api.atlassian.com/up')), 'adresse non permise')

    def test_refuses_non_curl(self):
        self.assertRefused(self.upload(self.spec, 'wget ' + self.URL), 'curl')


# ---------------------------------------------------------------- corrections

class TestProcessPatterns(unittest.TestCase):
    def labels(self, text):
        import re
        return [label for rx, label in R.PROCESS if re.search(rx, text)]

    def test_no_false_positive(self):
        for t in ('Stockage sur S3 des pièces jointes.', 'Bucket s3://donnees', '## 404 Not Found handling',
                  '<h2>2024 en bref</h2>', 'Clé I-03X sans contexte', 'Le modèle S3 Glacier'):
            self.assertEqual(self.labels(t), [], t)

    def test_process_contexts_detected(self):
        for t, label in (('S1 : cadrage', 'Sx'), ('validé en (S2).', 'Sx'), ('voir [S3]', 'Sx'), ('(S1, S2)', 'Sx'),
                         ('I-03 : question', 'I-xx'), ('(I-12)', 'I-xx'), ('[I-04]', 'I-xx'),
                         ('## 1. Titre', 'titre numéroté'), ('## 2.3 Titre', 'titre numéroté'), ('### 2.3. Titre', 'titre numéroté'),
                         ('## 4) Titre', 'titre numéroté'), ('<h2>1. Titre</h2>', 'titre numéroté'), ('<h3>2.3 Titre</h3>', 'titre numéroté')):
            self.assertTrue(any(label in l for l in self.labels(t)), t)


def lot_page(pr, cle):
    lots = [read_json(pr.sync(f)) for f in sorted(os.listdir(pr.sync())) if f.startswith('lot-')]
    return next(x for l in lots for x in l['pages'] if x['cle'] == cle)


class TestRender(Base):
    def test_failed_render_removes_stale_png_and_lots_skip_stale(self):
        pr = self.project(mermaid=True)
        pr.cfg(dict(cloudId='c', racine=dict(id='1', url='u1', titre='Projet'), pages={'contrat-api': dict(id='2', url='u2', titre='Contrat API')}))
        pr.run('resoudre', '2026-01-01 10:00')
        dg = read_json(pr.sync('manifest.json'))['pages'][0]['diagrammes'][0]
        write(dg['png'], 'ancien'); past = time.time() - 100; os.utime(dg['png'], (past, past))
        # PNG plus ancien que la source : jamais transmis par lots
        pr.run('lots')
        self.assertIsNone(lot_page(pr, 'racine')['diagrammes'][0]['png'])
        pr.fake_mmdc(ok=False)
        r = pr.run('rendre', os.path.join(self.tmp, 'puppeteer.json'))
        self.assertIn('ÉCHEC', r.stdout); self.assertFalse(os.path.exists(dg['png']))
        pr.fake_mmdc(ok=True)
        r = pr.run('rendre', os.path.join(self.tmp, 'puppeteer.json'))
        self.assertIn('1 diagramme(s) rendu(s), 0 échec(s)', r.stdout)
        pr.run('lots')
        self.assertEqual(lot_page(pr, 'racine')['diagrammes'][0]['png'], dg['png'])


class TestResoudre(Base):
    def test_page_published_without_mmdc_republished_when_available(self):
        pr = self.project(mermaid=True)
        pr.published(extra_racine=dict(diagrammes=0))
        etats, _ = pr.etats()  # pas de mmdc : rien à republier
        self.assertEqual(etats['racine'], 'inchangée')
        pr.fake_mmdc()
        etats, _ = pr.etats()
        self.assertEqual(etats['racine'], 'à publier'); self.assertEqual(etats['contrat-api'], 'inchangée')
        pr.published()  # diagrammes enregistrés = extraits
        self.assertEqual(pr.etats()[0]['racine'], 'inchangée')

    def test_status_only_unless_refused(self):
        pr = self.project()
        pr.published(extra_page=dict(statut='Brouillon'))
        etats, _ = pr.etats()
        self.assertEqual(etats['contrat-api'], 'statut seul')
        cfg = pr.cfg(); cfg['statut_natif_refuse'] = True; pr.cfg(cfg)
        etats, _ = pr.etats()
        self.assertEqual(etats['contrat-api'], 'inchangée')
        self.assertTrue(read_json(pr.sync('manifest.json'))['statut_natif_refuse'])

    def test_missing_body_clear_error(self):
        pr = self.project(); pr.cfg(dict(pages={}))
        os.remove(pr.sync('corps', 'contrat-api.html'))
        r = pr.run('resoudre', '2026-01-01 10:00')
        self.assertEqual(r.returncode, 1); self.assertIn('CORPS ABSENT', r.stdout); self.assertIn('contrat-api.html', r.stdout)

    def test_missing_plan_clear_error(self):
        pr = self.project(); os.remove(pr.sync('plan.json'))
        r = pr.run('resoudre', '2026-01-01 10:00')
        self.assertEqual(r.returncode, 1); self.assertIn('plan.json', r.stdout)

    def test_statut_cadrage_retro(self):
        pr = self.project()
        self.assertEqual(R.statut_cadrage(pr.p), ('En cadrage', '#FF8B00'))
        write(pr.doc('docs/prd.md'), '---\nstatut: brouillon\norigine: rétro\n---\n# PRD\n')
        self.assertEqual(R.statut_cadrage(pr.p), ('Rétro-documenté', '#6554C0'))


class TestFusion(Base):
    def setUp(self):
        super().setUp()
        self.pr = self.project()
        self.pr.cfg(dict(cloudId='c', pages={'contrat-api': dict(id='2', url='u2', titre='Contrat API')}))  # pas de « racine »
        self.pr.run('resoudre', '2026-01-01 10:00')

    def results(self, data):
        write(self.pr.sync('resultats-1.json'), json.dumps(data))

    def test_racine_absent_from_config_and_status_refused(self):
        self.results({'racine': dict(ok=True, id='1', titre='Projet', url='u1', empreinte='e', statut_natif='refusé', diagrammes=0),
                      'contrat-api': dict(ok=True, id='2', titre='Contrat API', url='u2', empreinte='f', pieces_jointes=1)})
        r = self.pr.run('fusionner', 'h')
        self.assertEqual(r.returncode, 0, r.stdout)
        cfg = self.pr.cfg()
        self.assertEqual(cfg['racine']['id'], '1'); self.assertTrue(cfg['statut_natif_refuse'])
        self.assertEqual(read_json(self.pr.sync('failed.json')), [])
        self.pr.run('lots')
        self.assertTrue(read_json(self.pr.sync('lot-1.json'))['statut_natif_refuse'])

    def test_failed_pages_relaunched_alone(self):
        self.results({'racine': dict(ok=True, id='1', titre='Projet', url='u1', empreinte='e'),
                      'contrat-api': dict(ok=True, id='2', titre='Contrat API', url='u2', empreinte='f', pieces_jointes=0)})
        r = self.pr.run('fusionner', 'h')
        self.assertEqual(r.returncode, 1); self.assertIn('ÉCHEC contrat-api : incomplète', r.stdout)
        self.assertEqual(read_json(self.pr.sync('failed.json')), ['contrat-api'])
        self.assertIsNone(self.pr.cfg()['pages']['contrat-api']['empreinte'])
        r = self.pr.run('lots', '--failed')
        self.assertEqual(r.returncode, 0)
        lots = [read_json(self.pr.sync(f)) for f in sorted(os.listdir(self.pr.sync())) if f.startswith('lot-')]
        self.assertEqual([x['cle'] for l in lots for x in l['pages']], ['contrat-api'])


class TestForgetAndOrder(Base):
    def setUp(self):
        super().setUp()
        self.pr = self.project()
        self.pr.plan([dict(cle='racine', titre='Projet', format='markdown', sources=['docs/prd.md']),
                      dict(cle='a', titre='A', format='markdown', parent='racine'),
                      dict(cle='b', titre='B', format='markdown', parent='racine'),
                      dict(cle='contrat-api', titre='Contrat API', format='html', parent='a')])
        self.pr.cfg(dict(racine=dict(id='1', url='u1', titre='Projet', empreinte='x'),
                         pages={'a': dict(id='10', url='u10', titre='A', empreinte='x', diagrammes=1),
                                'b': dict(id='11', url='u11', titre='B'),
                                'contrat-api': dict(id='12', url='u12', titre='Contrat API')}))

    def ordre(self, enfants):
        path = os.path.join(self.tmp, 'enfants.json'); write(path, json.dumps(enfants))
        r = self.pr.run('ordre', path); self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_forget_page_and_racine(self):
        r = self.pr.run('forget', 'a')
        self.assertEqual(r.returncode, 0)
        a = self.pr.cfg()['pages']['a']
        self.assertNotIn('id', a); self.assertNotIn('url', a); self.assertIsNone(a['empreinte']); self.assertEqual(a['titre'], 'A')
        sq = json.loads(self.pr.run('squelette').stdout)
        self.assertIsNone(next(x for x in sq['pages'] if x['cle'] == 'a')['id'])
        self.assertEqual(self.pr.run('forget', 'racine').returncode, 0)
        self.assertNotIn('id', self.pr.cfg()['racine'])
        r = self.pr.run('forget', 'inconnue')
        self.assertEqual(r.returncode, 1); self.assertIn('inconnue', r.stdout)

    def test_order_ignores_pages_unknown_to_confluence(self):
        # « a » (10) supprimée à la main : absente de enfants.json
        moves = self.ordre({'1': ['11']})
        ids = {m['id'] for m in moves} | {m['targetId'] for m in moves}
        self.assertNotIn('10', ids); self.assertNotIn('12', ids)

    def test_order_moves_and_reorders(self):
        moves = self.ordre({'1': ['11', '10', '12'], '10': []})
        self.assertIn(dict(id='12', position='append', targetId='10'), moves)
        self.assertIn(dict(id='10', position='before', targetId='11'), moves)


class TestPureFunctions(Base):
    def test_contract_keys_distinct_and_old_keys_migrated(self):
        cfg = R.migrate({'pages': {'docs/contrats/x.openapi.yaml': dict(id='1'), 'docs/contrats/x.asyncapi.yaml': dict(id='2'),
                                   'docs/contrats/y.openapi.yaml': dict(id='3'), 'docs/prd.md': dict(id='4')}})
        self.assertEqual(cfg['pages'], {'contrat-x-openapi': dict(id='1'), 'contrat-x-asyncapi': dict(id='2'),
                                        'contrat-y': dict(id='3'), 'fonctionnel': dict(id='4')})
        self.assertEqual(R.migrate({'pages': {'docs/contrats/api.openapi.yaml': dict(id='9')}})['pages'], {'contrat-api': dict(id='9')})

    def fake(self, d):
        os.makedirs(d, exist_ok=True); f = os.path.join(d, 'mmdc'); write(f, '#!/bin/sh\n'); os.chmod(f, 0o755)
        return f

    def test_mmdc_windows_binary_ignored_under_wsl(self):
        win = os.path.join(self.tmp, 'mnt'); f = self.fake(os.path.join(win, 'c', 'npm'))
        home = os.path.join(self.tmp, 'home')
        with mock.patch.object(R, 'WIN_MOUNT', win + os.sep), mock.patch.dict(os.environ, {'PATH': os.path.dirname(f), 'HOME': home}):
            with mock.patch.object(R, 'is_wsl', return_value=True):
                self.assertIsNone(R.mmdc_cmd())
            with mock.patch.object(R, 'is_wsl', return_value=False):
                self.assertEqual(R.mmdc_cmd(), [f])
            linux = self.fake(os.path.join(self.tmp, 'usr', 'bin'))
            os.environ['PATH'] = os.pathsep.join([os.path.dirname(f), os.path.dirname(linux)])
            with mock.patch.object(R, 'is_wsl', return_value=True):
                self.assertEqual(R.mmdc_cmd(), [linux])

    def test_mmdc_nvm_path_quoted(self):
        home = os.path.join(self.tmp, "dossier d'essai $(touch pwned)")
        write(os.path.join(home, '.nvm', 'nvm.sh'), 'mmdc() { echo "OK $*"; }\n')
        with mock.patch.dict(os.environ, {'PATH': os.path.join(self.tmp, 'vide'), 'HOME': home}):
            cmd = R.mmdc_cmd()
        self.assertIn(shlex.quote(os.path.join(home, '.nvm', 'nvm.sh')), cmd[2])
        r = subprocess.run(['/bin/bash'] + cmd[1:] + ['-i', 'x'], capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(r.stdout.strip(), 'OK -i x'); self.assertFalse(os.path.exists(os.path.join(self.tmp, 'pwned')))


if __name__ == '__main__':
    unittest.main()
