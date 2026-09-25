#!/bin/bash
set -Eeuo pipefail
BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$BIN_DIR/share-common.sh"
[[ -f "$STATE_DIR/disabled" ]] && exit 0
[[ -f "$STATE_DIR/web-config.json" ]] || exit 0
install -d -m 755 "$STATE_DIR"
# 应用启动与分享服务启动可能同时发生，串行处理，避免叠加绑定挂载。
exec 9>"$STATE_DIR/mount.lock"
flock -w 30 9
[[ -f "$STATE_DIR/disabled" ]] && exit 0
if [[ "$BIN_DIR" != "$STATE_DIR" ]]; then
    install -m 755 "$BIN_DIR/mount-assets.sh" "$STATE_DIR/mount-assets.sh"
    install -m 644 "$BIN_DIR/share-common.sh" "$BIN_DIR/render-page.py" "$BIN_DIR/page-assets.py" "$BIN_DIR/customize.js" "$STATE_DIR/"
fi
sleep "${1:-0}"
for attempt in {1..15}; do
    if find_share_module; then break; fi
    sleep 1
 done
[[ -n "$MODULE_DIR" ]] || exit 1
unmount_assets
# 使用卸载绑定后露出的当前系统页面，而不是永久保存的旧 original-index。
for attempt in {1..15}; do
    if python3 "$BIN_DIR/page-assets.py" "$MODULE_DIR/index.html" "$MODULE_DIR" --native 2>/dev/null; then break; fi
    [[ "$attempt" == 15 ]] && { log '当前系统入口或资源不完整，保持原始页面，不挂载旧版本'; exit 1; }
    sleep 1
 done
cp -p "$MODULE_DIR/index.html" "$STATE_DIR/original-index.html"
[[ ! -f "$MODULE_DIR/favicon.ico" ]] || cp -p "$MODULE_DIR/favicon.ico" "$STATE_DIR/original-favicon.ico"
TEMP_INDEX=$(mktemp "$STATE_DIR/share-index.XXXXXX")
cleanup() { rm -f "$TEMP_INDEX"; }
trap cleanup EXIT
ORIGINAL_INDEX="$STATE_DIR/original-index.html" CUSTOM_INDEX="$TEMP_INDEX" \
CONFIG_FILE="$STATE_DIR/web-config.json" PASSWORD_LOGO_FILE="$STATE_DIR/password-logo.png" \
python3 "$BIN_DIR/render-page.py"
python3 "$BIN_DIR/page-assets.py" "$TEMP_INDEX" "$MODULE_DIR"
chmod 644 "$TEMP_INDEX"
mv -f "$TEMP_INDEX" "$STATE_DIR/share-index.html"
mount_file() {
    local source="$1" target="$2"
    [[ -f "$source" ]] || return 0
    mkdir -p "$(dirname "$target")"
    [[ -e "$target" ]] || install -m 644 /dev/null "$target"
    mount --bind "$source" "$target"
}
# 任一挂载失败都撤销此次挂载，避免部分成功被误认为已应用。
rollback() { unmount_assets || true; cleanup; }
trap rollback ERR
mount_file "$STATE_DIR/share-index.html" "$MODULE_DIR/index.html"
mount_file "$STATE_DIR/custom-logo.png" "$MODULE_DIR/favicon.ico"
for asset in "${ASSETS[@]}"; do mount_file "$STATE_DIR/$asset" "$STATIC_DIR/$asset"; done
cmp -s "$STATE_DIR/share-index.html" "$MODULE_DIR/index.html"
log '当前版本分享页及自定义资源已挂载'
