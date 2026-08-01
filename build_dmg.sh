#!/usr/bin/env bash
# ============================================================================
# build_dmg.sh — Đóng gói DK Music Player thành file .dmg cho macOS
# Tự động tăng version (1.0.0 -> 1.0.1 -> 1.0.2...) qua VERSION.txt
# Không cần Apple Developer Certificate / Code Sign
# ============================================================================
set -e

APP_ID="dkmusicplayer"
APP_DISPLAY_NAME="DKMusicPlayer"
APP_TITLE="DK Music Player"
BUILD_SCRIPT="./build_mac.sh"
VERSION_FILE="VERSION.txt"

# --- Quản lý & Tự động tăng Version (1.0.x) ---
if [ ! -f "$VERSION_FILE" ]; then
    echo "1.0.0" > "$VERSION_FILE"
fi

CURRENT_VERSION=$(cat "$VERSION_FILE" | tr -d '\r\n ')
BASE_VERSION=$(echo "$CURRENT_VERSION" | cut -d'.' -f1,2)
BUILD_NUM=$(echo "$CURRENT_VERSION" | cut -d'.' -f3)

if [ -z "$BUILD_NUM" ]; then
    BUILD_NUM=0
fi

NEW_BUILD_NUM=$((BUILD_NUM + 1))
VERSION="${BASE_VERSION}.${NEW_BUILD_NUM}"
echo "$VERSION" > "$VERSION_FILE"

echo "==> Version cũ: $CURRENT_VERSION"
echo "==> Version mới: $VERSION"

# --- 1. Build .app mới nhất trước khi đóng gói ---
# --- 1. Build .app mới nhất trước khi đóng gói ---
if [ ! -f "$BUILD_SCRIPT" ]; then
    echo "❌ Không tìm thấy file $BUILD_SCRIPT"
    exit 1
fi

chmod +x "$BUILD_SCRIPT"

echo "==> Đang gọi $BUILD_SCRIPT..."
"$BUILD_SCRIPT"

APP_PATH="dist/${APP_DISPLAY_NAME}.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Không tìm thấy $APP_PATH - build_mac.sh có thể đã lỗi."
    exit 1
fi

# --- 2. Dựng thư mục tạm để làm Cấu trúc đĩa DMG ---
STAGING_DIR="pkgroot_dmg"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

echo "==> Copy ${APP_DISPLAY_NAME}.app vào thư mục tạm..."
cp -R "$APP_PATH" "$STAGING_DIR/"

# Tạo Symlink dẫn tới thư mục /Applications để người dùng dễ kéo-thả cài đặt
ln -s /Applications "$STAGING_DIR/Applications"

# --- 3. Đóng gói thành File DMG ---
mkdir -p "installer/mac"
DMG_NAME="${APP_ID}_v${VERSION}.dmg"
OUT_DMG="installer/mac/${DMG_NAME}"

# Xóa DMG cũ nếu trùng tên
rm -f "$OUT_DMG"

echo "==> Đang tạo file DMG bằng hdiutil..."
hdiutil create \
    -volname "${APP_TITLE} v${VERSION}" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$OUT_DMG"

# Dọn dẹp thư mục tạm
rm -rf "$STAGING_DIR"

# --- 4. Hiển thị kết quả & Lưu ý bỏ qua Gatekeeper ---
echo ""
echo "================================================================"
echo "✅ Đã tạo thành công: ${OUT_DMG}"
echo "================================================================"
echo ""
echo "📌 LƯU Ý DÙNG CHO APP NỘI BỘ (KHÔNG SIGN):"
echo "Do app không có Chữ ký số (Code Sign) từ Apple, khi mở file DMG"
echo "hoặc khởi chạy App lần đầu trên máy Mac khác, macOS sẽ chặn Gatekeeper."
echo ""
echo "👉 Cách xử lý trên máy người dùng:"
echo " 1. Khi mở app bị báo 'App is damaged' hoặc 'Unidentified Developer':"
echo "    -> Click Chuột phải (hoặc Control + Click) vào App -> Chọn 'Open' (Mở)."
echo " 2. Hoặc mở Terminal trên máy Mac đó và chạy lệnh mở khóa 1 lần:"
echo "    xattr -cr /Applications/${APP_DISPLAY_NAME}.app"
echo "================================================================"