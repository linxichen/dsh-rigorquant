#!/bin/sh
# Provision the pinned Lean toolchain + jacobian Mathlib runtime for the
# dsh-rigorquant escalation lane. Idempotent; safe to re-run.
#
# NOT unattended by default: this script downloads and runs remote installers
# and can mutate shell rc files, so it refuses to run unless it has been
# explicitly approved. The framework asks the user first, then runs:
#
#   RQ_ALLOW_PROVISION=1 bash provision-lean.sh
#
# Env overrides (rarely needed):
#   RQ_ALLOW_PROVISION=1    required to run at all (the approval gate)
#   RQ_MODIFY_SHELL_RC=1    also persist ~/.elan/bin in the shell rc files
#                           (default: off — the preset injects ~/.elan/bin into
#                           the lane's PATH itself, so rc mutation is optional)
#   LEAN_TOOLCHAIN          e.g. leanprover/lean4:v4.31.0
#   JACOBIAN_TAG            e.g. jacobian-v0.12.0 (must match the pinned package)
set -eu

if [ "${RQ_ALLOW_PROVISION:-0}" != "1" ]; then
  echo "error: refusing to provision without approval." >&2
  echo "This script downloads and executes remote installers. Run it only after" >&2
  echo "the user approves, with: RQ_ALLOW_PROVISION=1 bash provision-lean.sh" >&2
  exit 1
fi

LEAN_TOOLCHAIN="${LEAN_TOOLCHAIN:-leanprover/lean4:v4.31.0}"
LEAN_VERSION="$(printf '%s' "$LEAN_TOOLCHAIN" | sed 's/.*:v//')"
JACOBIAN_TAG="${JACOBIAN_TAG:-jacobian-v0.12.0}"
RUNTIME_DIR="${JACOBIAN_LEAN_RUNTIME:-$HOME/.local/share/jacobian/lean}"
ELAN_BIN="$HOME/.elan/bin"

# 1. elan + the pinned toolchain. Download the installer to a temp file first
#    (never pipe curl into sh), then execute it. Note: elan-init.sh is fetched
#    from the elan master branch and is not hash-pinned; it is the residual
#    supply-chain surface, which is why this whole script is approval-gated.
if [ ! -x "$ELAN_BIN/elan" ]; then
  TMP_ELAN="$(mktemp "${TMPDIR:-/tmp}/elan-init.XXXXXX.sh")"
  trap 'rm -f "$TMP_ELAN"' EXIT
  curl -fsSL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    -o "$TMP_ELAN"
  sh "$TMP_ELAN" -y --default-toolchain "$LEAN_TOOLCHAIN"
  rm -f "$TMP_ELAN"
  trap - EXIT
fi
# elan exits non-zero when the toolchain is already installed; treat only
# that case as success so the script stays idempotent.
set +e
TOOLCHAIN_OUT="$("$ELAN_BIN/elan" toolchain install "$LEAN_TOOLCHAIN" 2>&1)"
TOOLCHAIN_RC=$?
set -e
if [ "$TOOLCHAIN_RC" -ne 0 ] && ! printf '%s' "$TOOLCHAIN_OUT" | grep -qi 'already installed'; then
  printf '%s
' "$TOOLCHAIN_OUT" >&2
  exit 1
fi
if ! "$ELAN_BIN/lean" --version 2>/dev/null | grep -q "$LEAN_VERSION"; then
  echo "error: pinned Lean $LEAN_VERSION toolchain is not resolvable" >&2
  exit 1
fi

# 2. Optionally persist elan on PATH for future shells. Off by default: the
#    preset's mcp-jacobian row already appends ~/.elan/bin to the lane PATH.
if [ "${RQ_MODIFY_SHELL_RC:-0}" = "1" ]; then
  for rc in "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.profile"; do
    [ -f "$rc" ] || continue
    grep -q '\.elan/bin' "$rc" || echo 'export PATH="$HOME/.elan/bin:$PATH"' >> "$rc"
  done
fi

# 3. jacobian's pinned Mathlib runtime (matches the package's MATHLIB_COMMIT).
#    Files are pinned by the jacobian release tag (JACOBIAN_TAG), not by hash.
mkdir -p "$RUNTIME_DIR"
for f in lakefile.toml lean-toolchain lake-manifest.json \
         JacobianLeanProofState.lean JacobianLeanRuntime.lean; do
  curl -fsSL "https://raw.githubusercontent.com/morluto/jacobian/${JACOBIAN_TAG}/lean/${f}" \
    -o "$RUNTIME_DIR/$f"
done
cd "$RUNTIME_DIR"
"$ELAN_BIN/lake" update    # pulls mathlib's prebuilt olean cache
"$ELAN_BIN/lake" build     # compiles the project modules only

echo "provisioned: elan + $LEAN_TOOLCHAIN + mathlib runtime at $RUNTIME_DIR"
echo "lean.check is now available to the jacobian lane (retry the call)."
