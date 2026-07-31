#!/usr/bin/env bash
# ============================================================================
# build_deb.sh — Đóng gói DK Music Player v1.0 thành file .deb cho Ubuntu
# Tự động tăng version (1.0.0 -> 1.0.1 -> 1.0.2...) qua VERSION.txt
# ============================================================================
set -e

APP_ID="dkmusicplayer"                          # tên gói (chữ thường, không khoảng trắng)
APP_DISPLAY_NAME="DKMusicPlayer"                # khớp với APP_NAME trong build_ubuntu.sh
APP_TITLE="DK Music Player v1.0"               # Tên hiển thị trên menu Ubuntu
MAINTAINER="Thach Dinh Kim <you@example.com>"
ARCH="amd64"
ICON_SRC="assets/icon.ico"
BUILD_SCRIPT="./build_ubuntu.sh"
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

# --- 1. Build binary mới nhất trước khi đóng gói ---
if [ ! -x "$BUILD_SCRIPT" ]; then
    echo "❌ Không tìm thấy $BUILD_SCRIPT (chưa chmod +x hoặc sai thư mục)."
    exit 1
fi
echo "==> Build binary mới nhất..."
"$BUILD_SCRIPT"

if [ ! -f "dist/${APP_DISPLAY_NAME}" ]; then
    echo "❌ Không thấy dist/${APP_DISPLAY_NAME} - build_ubuntu.sh có thể đã lỗi."
    exit 1
fi

# --- 2. Dựng cây thư mục gói .deb ---
PKG_ROOT="pkgroot_deb"
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/opt/${APP_ID}"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/pixmaps"

# 2a. Binary chính -> /opt/dkmusicplayer/
cp "dist/${APP_DISPLAY_NAME}" "$PKG_ROOT/opt/${APP_ID}/${APP_DISPLAY_NAME}"
chmod 755 "$PKG_ROOT/opt/${APP_ID}/${APP_DISPLAY_NAME}"

# 2b. Symlink vào PATH
ln -sf "/opt/${APP_ID}/${APP_DISPLAY_NAME}" "$PKG_ROOT/usr/bin/${APP_ID}"

# 2c. Icon: convert .ico -> .png
if [ -f "$ICON_SRC" ]; then
    python3 -c "
from PIL import Image
im = Image.open('${ICON_SRC}')
im.save('${PKG_ROOT}/usr/share/pixmaps/${APP_ID}.png')
" 2>/dev/null && echo "==> Đã convert icon." \
  || echo "⚠️ Không convert được icon (thiếu Pillow). Launcher tạm thiếu icon."
fi

# 2d. File .desktop
cat > "$PKG_ROOT/usr/share/applications/${APP_ID}.desktop" << EOF
[Desktop Entry]
Name=${APP_TITLE}
Comment=DK Music Player v1.0 - Lightweight Audio Player
Exec=/usr/bin/${APP_ID} %f
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;
MimeType=audio/mpeg;audio/ogg;audio/x-wav;audio/flac;audio/x-flac;
StartupWMClass=${APP_DISPLAY_NAME}
EOF

# 2e. control file
INSTALLED_SIZE=$(du -sk "$PKG_ROOT/opt/${APP_ID}" | cut -f1)
cat > "$PKG_ROOT/DEBIAN/control" << EOF
Package: ${APP_ID}
Version: ${VERSION}
Section: sound
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: ${MAINTAINER}
Description: ${APP_TITLE}
 Modern & lightweight music player v1.0 built with PyQt6 and QFluentWidgets.
EOF

# 2f. postinst
cat > "$PKG_ROOT/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e
update-desktop-database -q /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
exit 0
EOF
chmod 755 "$PKG_ROOT/DEBIAN/postinst"

# 2g. postrm
cat > "$PKG_ROOT/DEBIAN/postrm" << 'EOF'
#!/bin/sh
set -e
update-desktop-database -q /usr/share/applications 2>/dev/null || true
exit 0
EOF
chmod 755 "$PKG_ROOT/DEBIAN/postrm"

chmod 755 "$PKG_ROOT/DEBIAN"

# --- 3. Đóng gói .deb ---
mkdir -p "installer/ubuntu"
OUT_DEB="installer/ubuntu/${APP_ID}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUT_DEB"

# --- 4. Hiển thị thông tin & lệnh cài/gỡ ---
echo ""
echo "✅ Đã tạo gói: ${OUT_DEB}"
echo "   Cài đặt (hoặc nâng cấp bản cũ):"
echo "     sudo apt install ./${OUT_DEB}"
echo ""
echo "   Gỡ cài đặt:"
echo "     sudo apt remove ${APP_ID}"
echo ""
echo "   Đặt làm ứng dụng mặc định mở file nhạc (double-click trong Files):"
echo "     xdg-mime default ${APP_ID}.desktop audio/mpeg audio/ogg audio/x-wav audio/flac"