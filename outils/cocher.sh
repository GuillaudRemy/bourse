#!/usr/bin/env bash
# Coche une tache de TODO.md : outils/cocher.sh 1.2
sed -i "s/^- \[ \] $1 /- [x] $1 /" "$(dirname "$0")/../TODO.md" && grep -n "^- \[x\] $1 " "$(dirname "$0")/../TODO.md"
