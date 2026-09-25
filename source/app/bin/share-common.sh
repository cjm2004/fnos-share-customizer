#!/bin/bash
STATE_DIR="${FNOS_CUSTOM_STATE_DIR:-/usr/local/share/fnos-custom}"
SYSTEMD_DIR="${FNOS_CUSTOM_SYSTEMD_DIR:-/etc/systemd/system}"
ASSETS=(password-background.png file-background.png password-logo.png ad-top.png ad-bottom.png ad-left.png ad-right.png)
log() { printf '[Share Customizer] %s\n' "$*"; }
require_root() {
    [[ $(id -u) -eq 0 ]] || { log '请通过应用管理页面以 root 权限操作'; exit 1; }
}
find_share_module() {
    local candidate
    MODULE_DIR=""
    for candidate in "${FNOS_SHARE_MODULE_DIR:-/usr/trim/www/modules/trim_sharelink}" /usr/trim/www/modules/trim-sharelink /usr/local/share/trim_sharelink; do
        if [[ -d "$candidate" ]]; then MODULE_DIR="$candidate"; break; fi
    done
    [[ -n "$MODULE_DIR" ]] || { log '未找到 fnOS 分享模块'; return 1; }
    STATIC_DIR="$MODULE_DIR/s"
    SERVICE=trim_sharelink.service
    for candidate in trim_sharelink.service trim-sharelink.service; do
        if systemctl cat "$candidate" >/dev/null 2>&1; then SERVICE="$candidate"; break; fi
    done
}
remove_override() {
    rm -f "${SYSTEMD_DIR}/${SERVICE}.d/custom-share-page.conf"
    rmdir "${SYSTEMD_DIR}/${SERVICE}.d" 2>/dev/null || true
    systemctl daemon-reload
}
unmount_assets() {
    local target asset
    for target in "$MODULE_DIR/index.html" "$MODULE_DIR/favicon.ico"; do
        while mountpoint -q "$target"; do umount "$target" || return 1; done
    done
    for asset in "${ASSETS[@]}"; do
        for target in "$MODULE_DIR/$asset" "$STATIC_DIR/$asset"; do
            while mountpoint -q "$target"; do umount "$target" || return 1; done
        done
    done
}
