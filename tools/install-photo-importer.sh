#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="${1:-$HOME/projects/full-circle-paradise}"
SCRIPT="$PROJECT_DIR/tools/photo_importer.py"
if [[ ! -f "$SCRIPT" ]]; then
  echo "Photo importer not found at: $SCRIPT" >&2
  exit 1
fi
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
[[ -n "$DESKTOP_DIR" ]] || DESKTOP_DIR="$HOME/Desktop"
mkdir -p "$DESKTOP_DIR"
LAUNCHER="$DESKTOP_DIR/FieldStation Photo Importer.desktop"
cat > "$LAUNCHER" <<EOF
[Desktop Entry]
Type=Application
Name=FieldStation Photo Importer
Comment=Add Immich photographs to Full Circle Paradise galleries
Exec=python3 "$SCRIPT"
Terminal=true
Icon=applications-graphics
Categories=Graphics;Utility;
EOF
chmod +x "$LAUNCHER"
echo "Installed: $LAUNCHER"
