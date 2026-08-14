#!/bin/sh
# Provision the pinned Lean toolchain + jacobian Mathlib runtime for the
# dsh-rigorquant escalation lane. Idempotent; safe to re-run; runs unattended.
#
# Usage: bash provision-lean.sh            (agent runs this on
#   TOOLCHAIN_RESOLUTION / MATHLIB_MANIFEST errors from the jacobian lane)
#
# Overrides (rarely needed):
#   LEAN_TOOLCHAIN   e.g. leanprover/lean4:v4.31.0
#   JACOBIAN_TAG     e.g. jacobian-v0.12.0  (must match the installed package)
set -eu

LEAN_TOOLCHAIN="${LEAN_TOOLCHAIN:-leanprover/lean4:v4.31.0}"
LEAN_VERSION="$(printf '%s' "$LEAN_TOOLCHAIN" | sed 's/.*:v//')"
JACOBIAN_TAG="${JACOBIAN_TAG:-jacobian-v0.12.0}"
RUNTIME_DIR="${JACOBIAN_LEAN_RUNTIME:-$HOME/.local/share/jacobian/lean}"
ELAN_BIN="$HOME/.elan/bin"

# 1. elan + the pinned toolchain (downloads ~hundreds of MB on first run)
if [ ! -x "$ELAN_BIN/elan" ]; then
  curl -fsSL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    | sh -s -- -y --default-toolchain "$LEAN_TOOLCHAIN"
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

# 2. Persist elan on PATH for future shells/processes
for rc in "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.profile"; do
  [ -f "$rc" ] || continue
  grep -q '\.elan/bin' "$rc" || echo 'export PATH="$HOME/.elan/bin:$PATH"' >> "$rc"
done

# 3. jacobian's pinned Mathlib runtime (matches the package's MATHLIB_COMMIT)
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
