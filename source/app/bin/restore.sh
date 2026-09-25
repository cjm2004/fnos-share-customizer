#!/bin/bash
set -euo pipefail
BIN_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$BIN_DIR/share-common.sh"
require_root
find_share_module
install -d -m 755 "$STATE_DIR"
# 保留设置，但禁止应用重启/升级时再次自动启用自定义。
touch "$STATE_DIR/disabled"
remove_override
systemctl stop "$SERVICE"
trap 'systemctl start "$SERVICE" >/dev/null 2>&1 || true' EXIT
exec 9>"$STATE_DIR/mount.lock"
flock -w 30 9
unmount_assets
# 不复制旧备份：底层原始页和当前服务才是系统升级后的权威来源。
systemctl start "$SERVICE"
for attempt in {1..15}; do
    if python3 "$BIN_DIR/page-assets.py" "$MODULE_DIR/index.html" "$MODULE_DIR" --native 2>/dev/null; then
        systemctl is-active --quiet "$SERVICE"
        trap - EXIT
        log '已恢复当前系统原始分享页'
        exit 0
    fi
    sleep 1
done
log '原始页面未就绪，请检查分享服务日志'
exit 1
