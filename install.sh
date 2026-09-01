#!/usr/bin/env bash
# install.sh —— install gfreport-renew-skill to native tool paths (Linux/macOS)
# Idempotent: re-running overwrites symlinks without data loss.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="$(basename "$SKILL_DIR")"

# Tier 1 / Tier 2 native install paths (canonical 12 tools)
declare -A TARGETS=(
  ["$HOME/.claude/skills"]="$SKILL_NAME"
  ["$HOME/.config/opencode/skills"]="$SKILL_NAME"
  ["$HOME/.config/Cursor/User/skills"]="$SKILL_NAME"
  ["$HOME/.config/Codex/skills"]="$SKILL_NAME"
  ["$HOME/.config/goose/skills"]="$SKILL_NAME"
  ["$HOME/.config/Roo-Code/skills"]="$SKILL_NAME"
  ["$HOME/.config/Cline/skills"]="$SKILL_NAME"
  ["$HOME/.config/Kilo/skills"]="$SKILL_NAME"
  ["$HOME/.config/Kiro/skills"]="$SKILL_NAME"
  ["$HOME/.config/Factory/skills"]="$SKILL_NAME"
  ["$HOME/.config/Antigravity/skills"]="$SKILL_NAME"
  ["$HOME/.gemini/skills"]="$SKILL_NAME"
)

# Universal fallback (any tool that reads ~/.agents/skills/)
UNIVERSAL="$HOME/.agents/skills"

installed=0
for target in "${!TARGETS[@]}"; do
  if [[ -d "$(dirname "$target")" || "$(dirname "$target")" == "$HOME/.config" ]]; then
    mkdir -p "$target"
    ln -sfn "$SKILL_DIR" "$target/$SKILL_NAME"
    echo "  ✓ linked $target/$SKILL_NAME"
    installed=$((installed + 1))
  fi
done

mkdir -p "$UNIVERSAL"
ln -sfn "$SKILL_DIR" "$UNIVERSAL/$SKILL_NAME"
echo "  ✓ linked $UNIVERSAL/$SKILL_NAME (universal fallback)"
installed=$((installed + 1))

echo ""
echo "gfreport-renew-skill installed to $installed location(s)."
echo "Run:  python $SKILL_DIR/scripts/run_pipeline.py --help"