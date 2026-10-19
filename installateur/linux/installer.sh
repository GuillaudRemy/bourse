#!/usr/bin/env bash
# Installe Bourse pour l'utilisateur courant (sans sudo) :
#   programme  ~/.local/share/bourse/app
#   donnees    ~/.local/share/bourse/donnees et sauvegardes (jamais touchees par une mise a jour)
#   raccourcis menu Applications + bureau
#
# Usage : tar xzf bourse-linux-x86_64.tar.gz && ./bourse/installer.sh
set -euo pipefail

SOURCE="$(cd "$(dirname "$0")" && pwd)"
BASE="${XDG_DATA_HOME:-$HOME/.local/share}/bourse"
APP="$BASE/app"

if [ "$(uname -m)" != "x86_64" ]; then
  echo "Bourse est construit pour les PC 64 bits (x86_64) ; cette machine est $(uname -m)."; exit 1
fi

mkdir -p "$BASE"
if [ "$SOURCE" != "$APP" ]; then
  echo "→ Copie dans $APP"
  rm -rf "$APP.nouveau"
  cp -a "$SOURCE" "$APP.nouveau"
  rm -rf "$APP"
  mv "$APP.nouveau" "$APP"
fi

echo "→ Raccourcis"
RACCOURCI="[Desktop Entry]
Type=Application
Name=Bourse
Comment=Analyse des cours et des fondamentaux
Exec=$APP/bourse
Icon=$APP/bourse.png
Terminal=true
Categories=Office;Finance;
"
MENU="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$MENU"
printf '%s' "$RACCOURCI" > "$MENU/bourse.desktop"
chmod +x "$MENU/bourse.desktop"

BUREAU="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Bureau")"
if [ -d "$BUREAU" ] && [ "$BUREAU" != "$HOME" ]; then   # xdg-user-dir renvoie $HOME si le bureau n'est pas configure
  printf '%s' "$RACCOURCI" > "$BUREAU/bourse.desktop"
  chmod +x "$BUREAU/bourse.desktop"
  # Sans cela, GNOME demande de « faire confiance » au raccourci avant de le lancer.
  gio set "$BUREAU/bourse.desktop" metadata::trusted true 2>/dev/null || true
fi

echo
echo "Bourse $(cat "$APP/VERSION") est installe."
echo "Lancez-le depuis l'icone « Bourse » (bureau ou menu Applications)."
echo "Il se mettra a jour tout seul a chaque lancement."
