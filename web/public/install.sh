#!/bin/sh
# SimAPI CLI installer (macOS / Linux)
#   curl -fsSL https://sim-api.vercel.app/install.sh | sh
set -e

REPO="https://raw.githubusercontent.com/TaxCollector23/SimAPI-YC-/main"
DEST="$HOME/.simapi"
BIN="$DEST/bin"
SRC="$REPO/sdk-node/bin/simapi.js"

printf '\n  Installing the SimAPI CLI…\n'

if ! command -v node >/dev/null 2>&1; then
  printf '  \033[31m✗\033[0m Node.js 18+ is required but was not found.\n'
  printf '    Install it with:  brew install node   (or from https://nodejs.org)\n'
  printf '    Then re-run this installer.\n\n'
  exit 1
fi
NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)
if [ "$NODE_MAJOR" -lt 18 ]; then
  printf '  \033[31m✗\033[0m Node 18+ required (found %s).\n\n' "$(node -v)"
  exit 1
fi

mkdir -p "$BIN"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$SRC" -o "$BIN/simapi.js"
else
  wget -qO "$BIN/simapi.js" "$SRC"
fi

# Wrapper lives next to the script, in a single stable location we control.
printf '#!/bin/sh\nexec node "%s/simapi.js" "$@"\n' "$BIN" > "$BIN/simapi"
chmod +x "$BIN/simapi"

printf '  \033[32m✓\033[0m Installed to %s/simapi\n' "$BIN"

# Ensure ~/.simapi/bin is on PATH — add it to the user's shell profiles.
added=""
add_path() {
  rc="$1"
  [ -f "$rc" ] || return 0
  if ! grep -qs '.simapi/bin' "$rc" 2>/dev/null; then
    printf '\n# SimAPI CLI\nexport PATH="$HOME/.simapi/bin:$PATH"\n' >> "$rc"
    added="$added $rc"
  fi
}
case ":$PATH:" in
  *":$BIN:"*) : ;;  # already on PATH
  *)
    add_path "$HOME/.zshrc"
    add_path "$HOME/.bashrc"
    add_path "$HOME/.profile"
    [ -n "$added" ] && printf '  \033[32m✓\033[0m Added %s to your PATH (%s)\n' "$BIN" "$(echo $added | xargs)"
    ;;
esac

printf '\n  Restart your terminal, or run this once now:\n'
printf '    \033[36mexport PATH="$HOME/.simapi/bin:$PATH"\033[0m\n'
printf '\n  Then get started:  \033[36msimapi login\033[0m\n\n'
