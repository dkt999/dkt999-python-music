#!/usr/bin/env bash
# ============================================================================
# build_ubuntu.sh — Build DK Music Player v1.0 (PyQt6 + QFluentWidgets) 
# thành 1 file thực thi cho Ubuntu
# ============================================================================
set -e

APP_NAME="DKMusicPlayer"
ENTRY_POINT="main.py"
ICON_PATH="assets/icon.ico"
ASSETS_DIR="assets"

if [ ! -f "$ENTRY_POINT" ]; then
    echo "❌ Không tìm thấy $ENTRY_POINT. Hãy chạy script này từ thư mục gốc project."
    exit 1
fi

if [ ! -d ".venv-build" ]; then
    echo "==> Tạo virtualenv .venv-build..."
    python3 -m venv .venv-build
fi
source .venv-build/bin/activate

echo "==> Cài dependencies..."
pip install --upgrade pip -q
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
else
    pip install PyQt6 PyQt6-Fluent-Widgets pygame mutagen -q
fi
pip install pyinstaller -q

rm -rf build dist "${APP_NAME}.spec"

HIDDEN_IMPORTS=(
    "--hidden-import=PyQt6.QtSvg"
    "--hidden-import=PyQt6.QtNetwork"
    "--hidden-import=pygame"
    "--hidden-import=mutagen"
)

COLLECT_ALL=(
    "--collect-all=qfluentwidgets"
    "--collect-all=pygame"
)

ADD_DATA=()
if [ -d "$ASSETS_DIR" ]; then
    ADD_DATA+=("--add-data=${ASSETS_DIR}:${ASSETS_DIR}")
fi

echo "==> Đang build ${APP_NAME} v1.0..."
ICON_ARG=""
if [ -f "$ICON_PATH" ]; then
    ICON_ARG="--icon=${ICON_PATH}"
fi

pyinstaller \
    --name "$APP_NAME" \
    --onefile \
    --windowed \
    $ICON_ARG \
    "${ADD_DATA[@]}" \
    "${HIDDEN_IMPORTS[@]}" \
    "${COLLECT_ALL[@]}" \
    "$ENTRY_POINT"

deactivate

echo ""
echo "✅ Build xong! File thực thi tại: dist/${APP_NAME}"