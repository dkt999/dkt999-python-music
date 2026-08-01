#!/usr/bin/env bash
# ============================================================================
# build_mac.sh — Build DK Music Player cho macOS
# Tự động convert PNG/ICO -> ICNS trước khi đóng gói PyInstaller
# ============================================================================
set -e

APP_NAME="DKMusicPlayer"
ENTRY_POINT="main.py"
ASSETS_DIR="assets"
ICNS_PATH="assets/icon.icns"

if [ ! -f "$ENTRY_POINT" ]; then
    echo "❌ Không tìm thấy $ENTRY_POINT. Hãy chạy script này từ thư mục gốc project."
    exit 1
fi

# --- 1. TỰ ĐỘNG CHUYỂN PNG/ICO SANG ICNS NẾU CHƯA CÓ ---
convert_to_icns() {
    local src_img=""
    
    # Ưu tiên tìm PNG trước, nếu không có thì tìm ICO
    if [ -f "assets/icon.png" ]; then
        src_img="assets/icon.png"
    elif [ -f "assets/icon.ico" ]; then
        src_img="assets/icon.ico"
    fi

    if [ -n "$src_img" ]; then
        echo "🔄 Đang chuyển đổi $src_img -> $ICNS_PATH bằng Python & iconutil..."
        
        # Tạo thư mục iconset tạm
        ICONSET_DIR="assets/app.iconset"
        rm -rf "$ICONSET_DIR"
        mkdir -p "$ICONSET_DIR"

        # Dùng Python Pillow để render ra đủ các kích thước chuẩn Apple
        python3 - <<EOF
from PIL import Image
import os

src = "$src_img"
iconset = "$ICONSET_DIR"
img = Image.open(src)

sizes = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png")
]

for size, name in sizes:
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(os.path.join(iconset, name))
EOF

        # Dùng lệnh tích hợp sẵn của macOS để tạo .icns
        iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"
        rm -rf "$ICONSET_DIR"
        echo "✅ Đã tạo thành công $ICNS_PATH!"
    else
        echo "⚠️ Không tìm thấy assets/icon.png hoặc assets/icon.ico để chuyển đổi."
    fi
}

# Nếu chưa có icon.icns thì tự tạo
if [ ! -f "$ICNS_PATH" ]; then
    convert_to_icns
fi

# --- 2. CHUẨN BỊ VIRTUALENV & DEPENDENCIES ---
if [ -d "venv" ]; then
    source venv/bin/activate
else
    if [ ! -d ".venv-build" ]; then
        echo "==> Tạo virtualenv .venv-build..."
        python3 -m venv .venv-build
    fi
    source .venv-build/bin/activate
fi

echo "==> Cài dependencies..."
pip install --upgrade pip -q
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
else
    pip install PyQt6 PyQt6-Fluent-Widgets pygame mutagen Pillow -q
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

ICON_ARG=""
if [ -f "$ICNS_PATH" ]; then
    ICON_ARG="--icon=${ICNS_PATH}"
fi

# --- 3. PYINSTALLER BUILD VỚI CẤU HÌNH FILE ASSOCIATION (INFO.PLIST) ---
echo "==> Đang build ${APP_NAME}.app..."

# Tạo Dictionary cấu hình Plist cho macOS
INFO_PLIST_EXTRA=$(cat <<EOF
{
    "CFBundleDevelopmentRegion": "English",
    "CFBundleExecutable": "${APP_NAME}",
    "CFBundleIconFile": "icon.icns",
    "CFBundleIdentifier": "com.dkt999.${APP_NAME}",
    "CFBundleName": "${APP_NAME}",
    "CFBundlePackageType": "APPL",
    "CFBundleShortVersionString": "1.0",
    "CFBundleDocumentTypes": [
        {
            "CFBundleTypeName": "Audio File",
            "CFBundleTypeRole": "Viewer",
            "LSHandlerRank": "Alternate",
            "CFBundleTypeExtensions": ["mp3", "flac", "wav", "ogg", "m4a", "aac"]
        }
    ]
}
EOF
)

# Chỉnh sửa file spec hoặc truyền trực tiếp vào PyInstaller
pyinstaller \
    --name "$APP_NAME" \
    --windowed \
    --noconfirm \
    --clean \
    $ICON_ARG \
    "${ADD_DATA[@]}" \
    "${HIDDEN_IMPORTS[@]}" \
    "${COLLECT_ALL[@]}" \
    --osx-bundle-identifier "com.dkt999.${APP_NAME}" \
    "$ENTRY_POINT"

# Cập nhật Info.plist sau khi PyInstaller tạo ra .app
PLIST_PATH="dist/${APP_NAME}.app/Contents/Info.plist"

if [ -f "$PLIST_PATH" ]; then
    echo "==> Đang đăng ký File Types (mp3, flac, wav...) vào Info.plist..."
    python3 - <<EOF
import plistlib

plist_path = "$PLIST_PATH"

with open(plist_path, 'rb') as f:
    data = plistlib.load(f)

# Bổ sung danh sách đuôi file nhạc supported
data['CFBundleDocumentTypes'] = [
    {
        'CFBundleTypeName': 'Audio File',
        'CFBundleTypeRole': 'Viewer',
        'LSHandlerRank': 'Alternate',
        'CFBundleTypeExtensions': ['mp3', 'flac', 'wav', 'ogg', 'm4a', 'aac', 'wma']
    }
]

with open(plist_path, 'wb') as f:
    plistlib.dump(data, f)

print("✅ Đã cập nhật Info.plist thành công!")
EOF
fi

deactivate