#!/usr/bin/env bash
# Build a standalone vheist binary into dist/ using PyInstaller (via uv).
set -euo pipefail

cd "$(dirname "$0")"

NAME=vheist
BUILD_DIR=build
LAUNCHER="$BUILD_DIR/launcher.py"

rm -rf "$BUILD_DIR" "dist/$NAME"
mkdir -p "$BUILD_DIR" dist

# Entry shim: __main__.py uses relative imports, so import it as a package.
cat > "$LAUNCHER" <<'PY'
from vheist.__main__ import main

if __name__ == "__main__":
    main()
PY

uv run --with pyinstaller pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name "$NAME" \
    --paths src \
    --collect-data textual \
    --distpath dist \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    "$LAUNCHER"

echo "Built: dist/$NAME"
