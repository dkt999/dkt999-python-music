#!/usr/bin/env bash
# ============================================================================
# build_ubuntu.sh — Build DK Music Player v1.0 (PyQt6 + QFluentWidgets) 
# thành 1 file thực thi cho Ubuntu
#
# CÁCH DÙNG:
#   1. Đặt file này ở THƯ MỤC GỐC project (cùng cấp với main.py, assets/)
#   2. chmod +x build_ubuntu.sh
#   3. ./build_ubuntu.sh
#   → File thực thi nằm ở: dist/DKMusicPlayer
# ============================================================================
set -e

APP_NAME="DKMusicPlayer"
ENTRY_POINT="main.py"
ICON_PATH="assets/icon.ico"
ASSETS_DIR="assets"

# --- 1. Kiểm tra đang đứng đúng thư mục gốc project chưa ---
if [ ! -f "$ENTRY_POINT" ]; then
    echo "❌ Không tìm thấy $ENTRY_POINT. Hãy chạy script này từ thư mục gốc project."
    exit 1
fi

# --- 2. Tạo virtualenv riêng cho build ---
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

# --- 3. Dọn build cũ ---
rm -rf build dist "${APP_NAME}.spec"

# --- 4. Module hay bị PyInstaller bỏ sót ---
HIDDEN_IMPORTS=(
    "--hidden-import=PyQt6.QtSvg"
    "--hidden-import=PyQt6.QtNetwork"
    "--hidden-import=pygame"
    "--hidden-import=mutagen"
)

# --collect-all đảm bảo lấy đủ resource nội bộ (.qss, ảnh...)
COLLECT_ALL=(
    "--collect-all=qfluentwidgets"
    "--collect-all=pygame"
)

# --- 5. Dữ liệu đi kèm (icon, ảnh...) ---
ADD_DATA=()
if [ -d "$ASSETS_DIR" ]; then
    ADD_DATA+=("--add-data=${ASSETS_DIR}:${ASSETS_DIR}")
fi

# --- 6. Build ---
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
echo "   Chạy test: ./dist/${APP_NAME}"