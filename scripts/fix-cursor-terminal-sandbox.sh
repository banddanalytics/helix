#!/usr/bin/env bash
# Fix "Terminal sandbox could not start" (AppArmor / kernel 6.2+) on Linux.
# - Installs an enhanced AppArmor profile (netlink + dac_override + unix sockets).
# - Persists sysctl knobs AppArmor uses for unprivileged user namespaces.
#
# Docs: https://cursor.com/docs/agent/terminal
# Context: https://forum.cursor.com/t/terminal-sandbox-issue-linux/152979
#
# Do NOT chmod 4755 the cursorsandbox binary — that breaks unprivileged namespaces.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROFILE_SRC="${SCRIPT_DIR}/cursor-sandbox.apparmor"
TARGET_PROFILE="/etc/apparmor.d/cursor-sandbox"
SYSCTL_DROPIN="/etc/sysctl.d/99-cursor-sandbox.conf"

if [[ ! -f "$PROFILE_SRC" ]]; then
  echo "Missing $PROFILE_SRC" >&2
  exit 1
fi

SANDBOX_BIN="/usr/share/cursor/resources/app/resources/helpers/cursorsandbox"
if [[ ! -x "$SANDBOX_BIN" ]]; then
  echo "Warning: expected sandbox binary not found at $SANDBOX_BIN (non-.deb install?)." >&2
  echo "Edit cursor-sandbox.apparmor to match your cursorsandbox path, then re-run." >&2
fi

if [[ -f "$TARGET_PROFILE" ]]; then
  cp -a "$TARGET_PROFILE" "${TARGET_PROFILE}.bak.$(date +%Y%m%d%H%M%S)"
  echo "Backed up existing profile to ${TARGET_PROFILE}.bak.*"
fi

install -m 0644 "$PROFILE_SRC" "$TARGET_PROFILE"
echo "Installed AppArmor profile -> $TARGET_PROFILE"

cat >"$SYSCTL_DROPIN" <<'EOF'
# Cursor agent terminal sandbox (kernel 6.2+ / AppArmor)
# Lets unprivileged user namespaces work with confined profiles.
# Review: https://cursor.com/docs/agent/terminal
kernel.apparmor_restrict_unprivileged_userns=0
kernel.apparmor_restrict_unprivileged_unconfined=0
EOF
chmod 0644 "$SYSCTL_DROPIN"
echo "Wrote $SYSCTL_DROPIN"

sysctl -p "$SYSCTL_DROPIN"
echo "Applied sysctl from $SYSCTL_DROPIN"

# -T: do not read old compiled cache (avoids stale policy without netlink/network rules)
apparmor_parser -r -W -T "$TARGET_PROFILE"
echo "Reloaded AppArmor profile cursor_sandbox / cursor_sandbox_remote (cache bypass -T)."

if command -v aa-status >/dev/null 2>&1; then
  aa-status 2>/dev/null | grep -E 'cursor_sandbox' || true
fi

echo ""
echo "Done. Fully quit Cursor (all windows) and start it again."
echo "Optional check from a terminal:"
echo "  /usr/share/cursor/resources/app/resources/helpers/cursorsandbox \\"
echo "    --preflight-only --sandbox-policy-cwd /tmp \\"
echo "    --sandbox-policy '{\"type\":\"workspace_readwrite\",\"cwd\":\"/tmp\",\"folders\":[\"/tmp\"]}' \\"
echo "    -- echo ok"
echo ""
echo "If AppArmor still denies access:"
echo "  sudo journalctl -b --grep='apparmor.*DENIED.*cursor' --no-pager"
