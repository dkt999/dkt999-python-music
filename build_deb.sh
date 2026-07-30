#!/usr/bin/env bash
# ============================================================================
# build_deb.sh — Đóng gói MusicPlayer thành file .deb (cài xong tự có icon
# trong menu, chạy được từ Files/Application Launcher, double-click file
# nhạc cũng mở được app này nếu bạn đặt làm ứng dụng mặc định).
#
# CÁCH DÙNG:
#   1. Đặt file này CÙNG CẤP với build_ubuntu.sh (thư mục gốc project)
#   2. chmod +x build_deb.sh
#   3. ./build_deb.sh
#   → Ra file: installer/ubuntu/musicplayer_<version>_amd64.deb
#
# CÀI ĐẶT (trên máy test):
#   sudo apt install ./installer/ubuntu/musicplayer_<version>_amd64.deb
#
# NÂNG CẤP KHI CÓ FILE .deb MỚI:
#   Chạy lại đúng lệnh cài ở trên với file .deb mới - VERSION tự tăng theo
#   thời gian build (timestamp) nên dpkg tự hiểu là nâng cấp, không cần gỡ
#   bản cũ trước.
#
# ĐẶT LÀM APP MẶC ĐỊNH ĐỂ MỞ FILE NHẠC (double-click trong Files):
#   sau khi cài, chạy (đổi đuôi file theo nhu cầu):
#     xdg-mime default musicplayer.desktop audio/mpeg audio/ogg audio/x-wav audio/flac
# ============================================================================
set -e

APP_ID="musicplayer"                   # tên gói (chữ thường, không dấu, không khoảng trắng)
APP_DISPLAY_NAME="MusicPlayer"         # phải khớp APP_NAME trong build_ubuntu.sh
MAINTAINER="Thach Dinh Kim <you@example.com>"   # đổi thành email thật của bạn
ARCH="amd64"
ICON_SRC="assets/icon.ico"
BUILD_SCRIPT="./build_ubuntu.sh"

VERSION="${VERSION:-$(date +%Y.%m.%d.%H%M)}"
echo "==> Version gói: $VERSION"

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

# 2a. Binary chính -> /opt/musicplayer/
cp "dist/${APP_DISPLAY_NAME}" "$PKG_ROOT/opt/${APP_ID}/${APP_DISPLAY_NAME}"
chmod 755 "$PKG_ROOT/opt/${APP_ID}/${APP_DISPLAY_NAME}"

# 2b. Symlink vào PATH để gõ lệnh "musicplayer" trong terminal cũng chạy được
ln -sf "/opt/${APP_ID}/${APP_DISPLAY_NAME}" "$PKG_ROOT/usr/bin/${APP_ID}"

# 2c. Icon: convert .ico -> .png (chuẩn Linux dùng png/svg, không dùng .ico)
if [ -f "$ICON_SRC" ]; then
    python3 -c "
from PIL import Image
im = Image.open('${ICON_SRC}')
im.save('${PKG_ROOT}/usr/share/pixmaps/${APP_ID}.png')
" 2>/dev/null && echo "==> Đã convert icon." \
  || echo "⚠️  Không convert được icon (thiếu thư viện Pillow: pip install Pillow). App vẫn cài/chạy bình thường, chỉ launcher tạm thiếu icon."
else
    echo "⚠️  Không thấy ${ICON_SRC}, bỏ qua bước icon."
fi

# 2d. File .desktop — quyết định app hiện trong menu, gán icon, và mở đúng
#     khi double-click từ Files. "%f" ở Exec để hệ thống truyền đường dẫn
#     file nhạc được double-click vào app -> main.py đọc sys.argv[1] và
#     tự phát ngay (đúng tính năng "mở file là play luôn" đã làm trong code).
#     MimeType khai báo các định dạng app này biết mở, để Files gợi ý app
#     trong menu "Open With".
cat > "$PKG_ROOT/usr/share/applications/${APP_ID}.desktop" << EOF
[Desktop Entry]
Name=${APP_DISPLAY_NAME}
Comment=Trình phát nhạc gọn nhẹ
Exec=/usr/bin/${APP_ID} %f
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Player;
MimeType=audio/mpeg;audio/ogg;audio/x-wav;audio/flac;audio/x-flac;
StartupWMClass=${APP_DISPLAY_NAME}
EOF

# 2e. control - khai báo tên gói/version cho dpkg
INSTALLED_SIZE=$(du -sk "$PKG_ROOT/opt/${APP_ID}" | cut -f1)
cat > "$PKG_ROOT/DEBIAN/control" << EOF
Package: ${APP_ID}
Version: ${VERSION}
Section: sound
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${INSTALLED_SIZE}
Maintainer: ${MAINTAINER}
Description: MusicPlayer - trình phát nhạc gọn nhẹ desktop
 Trình phát nhạc viết bằng Tkinter + pygame. Cài lại bằng bản .deb mới hơn
 sẽ tự động nâng cấp, không cần gỡ bản cũ trước.
EOF

# 2f. postinst - chạy SAU khi cài (cả cài mới lẫn nâng cấp): cập nhật lại
#     danh sách app + icon cache để menu/launcher thấy app ngay
cat > "$PKG_ROOT/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e
update-desktop-database -q /usr/share/applications 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true
exit 0
EOF
chmod 755 "$PKG_ROOT/DEBIAN/postinst"

# 2g. postrm - dọn lại cache khi gỡ
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

echo ""
echo "✅ Đã tạo: ${OUT_DEB}"
echo "   Cài (hoặc nâng cấp bản cũ nếu đã cài trước đó):"
echo "     sudo apt install ./${OUT_DEB}"
echo "   Gỡ:"
echo "     sudo apt remove ${APP_ID}"
echo ""
echo "   Đặt làm app mặc định mở file nhạc (double-click trong Files):"
echo "     xdg-mime default ${APP_ID}.desktop audio/mpeg audio/ogg audio/x-wav audio/flac"