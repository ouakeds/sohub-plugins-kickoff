#!/usr/bin/env bash
# Tests de non-régression des scripts du plugin (Python 3, bibliothèque standard uniquement).
# Usage : bash tests/run.sh   (depuis n'importe quel dossier)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m py_compile hooks/*.py skills/*/*.py
for f in .claude-plugin/*.json hooks/hooks.json skills/install-deps/puppeteer-config.json; do
  python3 -m json.tool "$f" > /dev/null
done
python3 -I -m unittest discover -s tests "$@"
