#!/bin/sh
# SimAPI CLI installer (macOS / Linux)
#   curl -fsSL https://raw.githubusercontent.com/TaxCollector23/SimAPI-YC-/main/install.sh | sh
set -e

REPO="https://raw.githubusercontent.com/TaxCollector23/SimAPI-YC-/main"
DEST="$HOME/.simapi"
SRC="$REPO/sdk-node/bin/simapi.js"

printf '\n  Installing the SimAPI CLI…\n'

if ! command -v node >/dev/null 2>&1; then
  printf '  ✗ Node.js 18+ is required. Install it from https://nodejs.org and re-run.\n\n'
  exit 1
fi
NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)
if [ "$NODE_MAJOR" -lt 18 ]; then
  printf '  ✗ Node 18+ required (found %s).\n\n' "$(node -v)"
  exit 1
fi

mkdir -p "$DEST/bin"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$SRC" -o "$DEST/bin/simapi.js"
else
  wget -qO "$DEST/bin/simapi.js" "$SRC"
fi

if [ -w /usr/local/bin ]; then
  BINDIR=/usr/local/bin
else
  BINDIR="$HOME/.local/bin"
  mkdir -p "$BINDIR"
fi

printf '#!/bin/sh\nexec node "%s/bin/simapi.js" "$@"\n' "$DEST" > "$BINDIR/simapi"
chmod +x "$BINDIR/simapi"

printf '  ✓ Installed to %s/simapi\n' "$BINDIR"
case ":$PATH:" in
  *":$BINDIR:"*) ;;
  *) printf '  →  Add %s to your PATH, then restart your shell.\n' "$BINDIR" ;;
esac
printf '\n  Get started:  simapi login\n\n'
