#!/usr/bin/env bash
# Publie une nouvelle version : tests locaux, etiquette, envoi sur GitHub.
# GitHub construit et teste alors l'installateur sous Windows, puis le publie ;
# l'application de bureau se met a jour toute seule a son prochain lancement.
#
# Usage : outils/publier.sh 0.2.0 "Ce qui change, en une phrase"
#         outils/publier.sh 0.3.0-beta.1 "..."   version beta : seuls les PC ou « Recevoir les
#                                                 versions beta » vaut « oui » l'installent
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:?Usage : outils/publier.sh X.Y.Z \"description\"}"
NOTES="${2:?Ajoutez une description des changements}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-beta\.[0-9]+)?$ ]] || { echo "Version attendue : X.Y.Z ou X.Y.Z-beta.N (ex. 0.2.0)"; exit 1; }

# liens.txt : fichier personnel, jamais publie.
if [ -n "$(git status --porcelain -- . ':!liens.txt')" ]; then
  echo "Des modifications ne sont pas commitees :"; git status --short -- . ':!liens.txt'; exit 1
fi
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo "La version v$VERSION existe deja."; exit 1
fi
# Ordre des versions de l'application (0.5.0 > 0.5.0-beta.2 > 0.5.0-beta.1), pas celui de sort -V.
DERNIERE=$(.venv/bin/python -c "
import subprocess
from backend.mise_a_jour import cle_version
tags = [t for t in subprocess.run(['git', 'tag', '--list', 'v*'], capture_output=True, text=True).stdout.split() if cle_version(t)]
print(max(tags, key=cle_version) if tags else '')")
if [ -n "$DERNIERE" ] && ! .venv/bin/python -c "
import sys
from backend.mise_a_jour import cle_version
sys.exit(cle_version('$VERSION') <= cle_version('$DERNIERE'))"; then
  echo "v$VERSION doit etre plus recente que $DERNIERE."; exit 1
fi

echo "→ Tests"
.venv/bin/python -m pytest -q tests

echo "→ Envoi de v$VERSION"
DEPART=$(date -u +%Y-%m-%dT%H:%M:%SZ)
git push origin HEAD
git tag -a "v$VERSION" -m "$NOTES"
git push origin "v$VERSION"

echo
echo "Construction et tests sous Windows en cours : gh run watch"
echo "Une fois termine, l'application se mettra a jour a son prochain lancement."
