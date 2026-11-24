#!/usr/bin/env bash
# Build the UMAP engine used by ReembedWidget and vendor it into
# datamapplot/static/wasm/.
#
# Source: the Rust/WASM UMAP from apple/embedding-atlas (packages/umap), with
# patches for custom initialisation, scheduled stepping and GPU status
# (fork branch `reembed-spike`). The build is single-threaded with optional
# WebGPU acceleration and uses the wasm-bindgen `no-modules` target, so it can
# run in a classic Blob worker (file://, notebooks, offline mode).
#
# Requirements: Rust with the wasm32-unknown-unknown target and
# wasm-bindgen-cli 0.2.121 (`cargo install wasm-bindgen-cli --version 0.2.121`).
#
#   EMBEDDING_ATLAS=/path/to/embedding-atlas scripts/build_reembed_engine.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
EA="${EMBEDDING_ATLAS:-$REPO/../embedding-atlas}"
BINDGEN="${WASM_BINDGEN:-$(command -v wasm-bindgen || echo "$HOME/.cargo/bin/wasm-bindgen")}"
OUT="$REPO/datamapplot/static/wasm"
TARGET_DIR="$EA/target-datamapplot"

"$BINDGEN" --version | grep -q "0.2.121" || { echo "wasm-bindgen 0.2.121 required" >&2; exit 1; }

(cd "$EA/packages/umap/umap-wasm" && CARGO_TARGET_DIR="$TARGET_DIR" \
  cargo build --target wasm32-unknown-unknown --release --features gpu)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp "$TARGET_DIR/wasm32-unknown-unknown/release/umap_wasm.wasm" "$TMP/umap_engine.wasm"
"$BINDGEN" "$TMP/umap_engine.wasm" --target no-modules --no-typescript \
  --remove-name-section --remove-producers-section --out-dir "$TMP/out"

mkdir -p "$OUT"
cp "$TMP/out/umap_engine.js" "$OUT/umap_engine.js"
gzip -9 -n -c "$TMP/out/umap_engine_bg.wasm" > "$OUT/umap_engine_bg.wasm.gz"
cp "$EA/LICENSE" "$OUT/LICENSE.embedding-atlas.txt"

COMMIT="$(git -C "$EA" rev-parse HEAD)"
BRANCH="$(git -C "$EA" rev-parse --abbrev-ref HEAD)"
DIRTY="$(git -C "$EA" status --porcelain -- packages/umap | wc -l)"
cat > "$OUT/BUILD_INFO.json" <<EOF
{
  "source": "https://github.com/apple/embedding-atlas (packages/umap), patched",
  "branch": "$BRANCH",
  "commit": "$COMMIT",
  "uncommitted_changes": $DIRTY,
  "features": ["gpu"],
  "target": "wasm-bindgen --target no-modules",
  "wasm_bindgen": "$("$BINDGEN" --version | awk '{print $2}')",
  "wasm_bytes": $(stat -c %s "$TMP/out/umap_engine_bg.wasm"),
  "license": "MIT (Apple Inc.), see LICENSE.embedding-atlas.txt"
}
EOF
ls -la "$OUT"
