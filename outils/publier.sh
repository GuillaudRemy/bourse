#!/usr/bin/env bash
# Publie une nouvelle version : tests locaux, etiquette, envoi sur GitHub.
# GitHub construit et teste alors l'installateur sous Windows, puis le publie ;
# l'application de bureau se met a jour toute seule a son prochain lancement.
#
# Usage : outils/publier.sh 0.2.0 "Ce qui change, en une phrase"
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="${1:?Usage : outils/publier.sh X.Y.Z \"description\"}"
NOTES="${2:?Ajoutez une description des changements}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Version attendue : X.Y.Z (ex. 0.2.0)"; exit 1; }

if [ -n "$(git status --porcelain)" ]; then
  echo "Des modifications ne sont pas commitees :"; git status --short; exit 1
fi
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
  echo "La version v$VERSION existe deja."; exit 1
fi
DERNIERE=$(git tag --list 'v*' --sort=-v:refname | head -1)
if [ -n "$DERNIERE" ] && [ "$(printf '%s\nv%s\n' "$DERNIERE" "$VERSION" | sort -V | tail -1)" != "v$VERSION" ]; then
  echo "v$VERSION doit etre plus recente que $DERNIERE."; exit 1
fi

echo "→ Tests"
.venv/bin/python -m pytest -q tests

echo "→ Envoi de v$VERSION"
git push origin HEAD
git tag -a "v$VERSION" -m "$NOTES"
git push origin "v$VERSION"

echo
echo "Construction et tests sous Windows en cours : gh run watch"
echo "Une fois termine, l'application se mettra a jour a son prochain lancement."
