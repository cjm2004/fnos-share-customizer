#!/bin/bash
set -euo pipefail
STATE_DIR="${FNOS_CUSTOM_STATE_DIR:-/usr/local/share/fnos-custom}"
BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${BIN_DIR}/share-common.sh"
require_root
find_share_module
install -d -m 755 "$STATE_DIR"
# 必须先撤掉旧 ExecStartPost，避免读取原始页时再次挂载旧入口。
remove_override
systemctl stop "$SERVICE"
recover_service() { systemctl start "$SERVICE" >/dev/null 2>&1 || true; }
trap recover_service EXIT
unmount_assets
[[ -f "$STATE_DIR/web-config.json" ]] || printf '{}\n' > "$STATE_DIR/web-config.json"
install -m 755 "$BIN_DIR/mount-assets.sh" "$STATE_DIR/mount-assets.sh"
install -m 644 "$BIN_DIR/share-common.sh" "$BIN_DIR/render-page.py" "$BIN_DIR/page-assets.py" "$BIN_DIR/customize.js" "$STATE_DIR/"
rm -f "$STATE_DIR/disabled"
systemctl start "$SERVICE"
# 首次启动/升级后服务异步释放前端资源，校验通过前不接管页面。
/bin/bash "$STATE_DIR/mount-assets.sh" 2
systemctl is-active --quiet "$SERVICE"
install -d -m 755 "${SYSTEMD_DIR}/${SERVICE}.d"
{
    printf '[Service]\nExecStartPost=-/bin/bash %s/mount-assets.sh 3\n' "$STATE_DIR"
    for target in index.html favicon.ico; do
        printf 'ExecStopPost=-/bin/umount %s/%s\n' "$MODULE_DIR" "$target"
    done
    for target in "${ASSETS[@]}"; do
        printf 'ExecStopPost=-/bin/umount %s/%s\n' "$STATIC_DIR" "$target"
    done
} > "${SYSTEMD_DIR}/${SERVICE}.d/custom-share-page.conf"
systemctl daemon-reload
trap - EXIT
log '已基于当前系统分享页重新生成并应用自定义设置'
