#!/usr/bin/env python3
import os
import re
import json
import shutil
import mimetypes
import subprocess
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from html import escape

STATE_DIR = os.environ.get("FNOS_CUSTOM_STATE_DIR", "/usr/local/share/fnos-custom")
MODULE_DIR = os.environ.get("FNOS_SHARE_MODULE_DIR", "/usr/trim/www/modules/trim_sharelink")
UPLOAD_DIR = os.path.join(STATE_DIR, "uploads")
CONFIG_FILE = os.path.join(STATE_DIR, "web-config.json")
LOGO_DIR = os.path.join(STATE_DIR, "uploads")
LOGO_PATH = os.path.join(STATE_DIR, "custom-logo.png")
PASSWORD_BACKGROUND_PATH = os.path.join(STATE_DIR, "password-background.png")
FILE_BACKGROUND_PATH = os.path.join(STATE_DIR, "file-background.png")
PASSWORD_LOGO_PATH = os.path.join(STATE_DIR, "password-logo.png")
AD_PATHS = {
    "top": os.path.join(STATE_DIR, "ad-top.png"),
    "bottom": os.path.join(STATE_DIR, "ad-bottom.png"),
    "left": os.path.join(STATE_DIR, "ad-left.png"),
    "right": os.path.join(STATE_DIR, "ad-right.png"),
}
DEFAULT_PORT = 38080
MAX_JSON_BODY = 256 * 1024
MAX_IMAGE_BODY = 10 * 1024 * 1024

# fnOS 更新管理器接入
UPDATE_MANAGER_URL = os.environ.get("FNOS_UPDATE_URL", "http://nas.192321.xyz:18080").rstrip("/")
UPDATE_APP_KEY = os.environ.get("FNOS_UPDATE_APP_KEY", "fnos-share-customizer")
UPDATE_CHANNEL = os.environ.get("FNOS_UPDATE_CHANNEL", "stable")


def app_version():
    """从 manifest 读取当前版本；找不到时回退到与 manifest 保持一致的常量。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for root in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        manifest = os.path.join(root, "manifest")
        if not os.path.isfile(manifest):
            continue
        try:
            with open(manifest, "r", encoding="utf-8") as f:
                for line in f:
                    match = re.match(r"\s*version\s*=\s*(\S+)", line)
                    if match:
                        return match.group(1)
        except OSError:
            continue
    return "2.0.0"


APP_VERSION = app_version()

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(STATE_DIR, "backups"), exist_ok=True)

DEFAULT_CONFIG = {
    "download_button_variant": "solid",
    "download_button_color": "#2b6cff",
    "download_button_text_color": "#ffffff",
    "transfer_button_variant": "soft",
    "transfer_button_color": "#e8efff",
    "transfer_button_text_color": "#2b6cff",
    "button_width_layout": "download_wide",
    "button_order": "transfer_left",
    "title_text": "\u6587\u4ef6\u5206\u4eab",
    "footer_text": "shared by cjm",
    "browser_title": "\u6587\u4ef6\u5206\u4eab",
    "logo_link": "https://www.fnnas.com",
    "logo_link_new_tab": False,
    "background_color": "#ffffff",
    "file_row_color": "#ffffff",
    "file_row_hover_color": "#f5f7fa",
    "primary_color": "#2b6cff",
    "password_title": "\u8f93\u5165\u5bc6\u7801\u4ee5\u8bbf\u95ee\u6587\u4ef6",
    "password_hint": "\u8bf7\u8f93\u5165\u5206\u4eab\u5bc6\u7801",
    "password_background_color": "#ffffff",
    "password_button_color": "#2b6cff",
    "password_button_text_color": "#ffffff",
    "password_background_image": False,
    "file_background_image": False,
    "password_logo_uploaded": False,
    "password_footer_text": "Copyright © 广州铁刃智造技术有限公司 版权所有",
    "error_invalid_link": "\u65e0\u6548\u94fe\u63a5\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002",
    "error_link_exceeded": "\u8be5\u94fe\u63a5\u8bbf\u95ee\u6b21\u6570\u5df2\u8fbe\u9650\u5236\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002",
    "error_link_expired": "\u8be5\u94fe\u63a5\u5df2\u8fc7\u671f\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002",
    "error_file_missing": "\u6587\u4ef6\u4e0d\u5b58\u5728\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002",
    "button_border_radius": "6px",
    "show_download_all": True,
    "show_transfer_button": True,
    "page_max_width": "800px",
    "ad_top_enabled": False,
    "ad_bottom_enabled": False,
    "ad_left_enabled": False,
    "ad_right_enabled": False
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                cfg.pop("custom_share_format", None)
                for k, v in DEFAULT_CONFIG.items():
                    cfg.setdefault(k, v)
                if cfg.get("password_footer_text") == "Copyright 广州xxx":
                    cfg["password_footer_text"] = DEFAULT_CONFIG["password_footer_text"]
                return cfg
        except:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_mime(path):
    t, _ = mimetypes.guess_type(path)
    return t or "application/octet-stream"


def image_type(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 33 and data[12:16] == b"IHDR" and data[-8:-4] == b"IEND":
        return "png"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")) and data.endswith(b"\x3b"):
        return "gif"
    if len(data) >= 20 and data[:4] == b"RIFF" and data[8:12] == b"WEBP" and int.from_bytes(data[4:8], "little") + 8 <= len(data):
        return "webp"
    return None


def valid_image(data, limit):
    return isinstance(data, bytes) and 0 < len(data) <= limit and image_type(data) is not None


class CustomizerHandler(BaseHTTPRequestHandler):

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self, max_length=MAX_IMAGE_BODY):
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except (TypeError, ValueError):
            self._send_json({"success": False, "error": "无效的请求长度"}, 400)
            return None
        if length < 0 or length > max_length:
            self._send_json({"success": False, "error": "请求体过大"}, 413)
            return None
        if length == 0:
            return b""
        return self.rfile.read(length)

    def _parse_form(self, body):
        boundary = None
        ct = self.headers.get("Content-Type", "")
        if "boundary=" in ct:
            boundary = ct.split("boundary=")[1].split(";")[0].strip().strip('"')
        if boundary:
            return self._parse_multipart(body, boundary)
        try:
            return {"json": json.loads(body.decode("utf-8"))}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"_parse_error": "无效的 JSON 请求"}

    def _parse_multipart(self, body, boundary):
        result = {}
        parts = body.split(b"--" + boundary.encode())
        for part in parts:
            if b"Content-Disposition" not in part:
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers_raw = part[:header_end].decode("utf-8", errors="replace")
            content = part[header_end + 4:]
            if content.endswith(b"\r\n"):
                content = content[:-2]

            name = None
            filename = None
            for line in headers_raw.split("\r\n"):
                if 'name="' in line:
                    name = line.split('name="')[1].split('"')[0]
                if 'filename="' in line:
                    filename = line.split('filename="')[1].split('"')[0]

            if filename:
                result[name] = {"filename": filename, "data": content}
            elif name:
                result[name] = content.decode("utf-8", errors="replace")

        if "json" in result:
            try:
                result["json"] = json.loads(result["json"])
            except:
                pass
        return result

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._serve_html()
        elif path == "/api/config":
            self._send_json({"success": True, "config": load_config()})
        elif path == "/api/status":
            self._serve_status()
        elif path == "/api/update/check":
            self._check_update()
        elif path == "/api/logo":
            self._serve_logo()
        elif path == "/api/background/password":
            self._serve_uploaded_file(PASSWORD_BACKGROUND_PATH)
        elif path == "/api/background/file":
            self._serve_uploaded_file(FILE_BACKGROUND_PATH)
        elif path == "/api/password-logo":
            self._serve_uploaded_file(PASSWORD_LOGO_PATH)
        elif path.startswith("/api/ad/"):
            slot = path.rsplit("/", 1)[-1]
            if slot in AD_PATHS:
                self._serve_uploaded_file(AD_PATHS[slot])
            else:
                self._send_json({"success": False, "error": "Not found"}, 404)
        elif path.startswith("/static/"): 
            self._serve_static(path[8:])
        else:
            self._send_json({"success": False, "error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        body_limit = MAX_JSON_BODY if path == "/api/config" else MAX_IMAGE_BODY
        body = self._read_body(body_limit)
        if body is None:
            return
        form = self._parse_form(body)

        if path == "/api/config":
            if "_parse_error" in form:
                self._send_json({"success": False, "error": form["_parse_error"]}, 400)
                return
            cfg = form.get("json", form)
            if not isinstance(cfg, dict):
                self._send_json({"success": False, "error": "配置必须是 JSON 对象"}, 400)
                return
            for key, value in cfg.items():
                if key in DEFAULT_CONFIG and type(value) is not type(DEFAULT_CONFIG[key]):
                    self._send_json({"success": False, "error": "配置类型错误: " + key}, 400)
                    return
            current = load_config()
            if isinstance(cfg, dict):
                for k, v in cfg.items():
                    if k != "custom_share_format" and (k in DEFAULT_CONFIG or k.startswith("custom_")):
                        current[k] = v
                save_config(current)
            self._send_json({"success": True, "config": current})

        elif path == "/api/upload-logo":
            logo = form.get("logo")
            if not logo:
                self._send_json({"success": False, "error": "\u8bf7\u63d0\u4f9b\u56fe\u7247\u6587\u4ef6"}, 400)
                return
            data = logo["data"] if isinstance(logo, dict) else b""
            if not valid_image(data, 5 * 1024 * 1024):
                self._send_json({"success": False, "error": "请上传有效的图片文件，大小不能超过 5MB"}, 400)
                return
            os.makedirs(LOGO_DIR, exist_ok=True)
            # 浏览器可直接解码支持的图片，无需把用户文件名拼入可执行代码。
            with open(LOGO_PATH, "wb") as f:
                f.write(data)
            cfg = load_config()
            cfg["logo_uploaded"] = True
            save_config(cfg)
            self._send_json({"success": True, "path": "/api/logo"})

        elif path in ("/api/upload-password-background", "/api/upload-file-background"):
            image = form.get("image")
            if not image:
                self._send_json({"success": False, "error": "请提供图片文件"}, 400)
                return
            data = image.get("data", b"") if isinstance(image, dict) else b""
            if not valid_image(data, 10 * 1024 * 1024):
                self._send_json({"success": False, "error": "请上传有效的背景图片，大小不能超过 10MB"}, 400)
                return
            filename = "password-background.png" if path.endswith("password-background") else "file-background.png"
            with open(os.path.join(STATE_DIR, filename), "wb") as f:
                f.write(data)
            cfg = load_config()
            cfg["password_background_image" if path.endswith("password-background") else "file_background_image"] = True
            save_config(cfg)
            self._send_json({"success": True})

        elif path.startswith("/api/upload-ad/"):
            slot = path.rsplit("/", 1)[-1]
            image = form.get("image")
            if slot not in AD_PATHS or not image:
                self._send_json({"success": False, "error": "请提供有效的广告图片文件"}, 400)
                return
            data = image.get("data", b"") if isinstance(image, dict) else b""
            if not valid_image(data, 10 * 1024 * 1024):
                self._send_json({"success": False, "error": "请上传有效的广告图片，大小不能超过 10MB"}, 400)
                return
            with open(AD_PATHS[slot], "wb") as f:
                f.write(data)
            cfg = load_config()
            cfg["ad_%s_enabled" % slot] = True
            save_config(cfg)
            self._send_json({"success": True, "path": "/api/ad/" + slot})

        elif path == "/api/upload-password-logo":
            image = form.get("image")
            if not image:
                self._send_json({"success": False, "error": "请提供图片文件"}, 400)
                return
            data = image.get("data", b"") if isinstance(image, dict) else b""
            if not valid_image(data, 5 * 1024 * 1024):
                self._send_json({"success": False, "error": "请上传有效的密码页 Logo，大小不能超过 5MB"}, 400)
                return
            with open(PASSWORD_LOGO_PATH, "wb") as f:
                f.write(data)
            cfg = load_config()
            cfg["password_logo_uploaded"] = True
            save_config(cfg)
            self._send_json({"success": True, "path": "/api/password-logo"})

        elif path == "/api/apply":
            try:
                result = subprocess.run(
                    ["bash", os.path.join(os.path.dirname(__file__), "../bin/apply.sh")],
                    capture_output=True, timeout=120)
                ok = result.returncode == 0
                self._send_json({
                    "success": ok,
                    "output": (result.stdout + result.stderr).decode("utf-8", errors="replace")
                })
            except subprocess.TimeoutExpired:
                self._send_json({"success": False, "error": "Apply timeout"}, 500)
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        elif path == "/api/restore":
            try:
                result = subprocess.run(
                    ["bash", os.path.join(os.path.dirname(__file__), "../bin/restore.sh")],
                    capture_output=True, timeout=120)
                ok = result.returncode == 0
                self._send_json({
                    "success": ok,
                    "output": (result.stdout + result.stderr).decode("utf-8", errors="replace")
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 500)

        else:
            self._send_json({"success": False, "error": "Not found"}, 404)

    def _serve_html(self):
        html = self._get_html()
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_status(self):
        config = load_config()
        has_original = os.path.exists(os.path.join(STATE_DIR, "original-index.html"))
        has_custom = os.path.exists(os.path.join(STATE_DIR, "share-index.html"))
        has_logo = os.path.exists(LOGO_PATH)
        service_active = False
        service_name = ""
        for candidate in ("trim_sharelink.service", "trim-sharelink.service"):
            try:
                r = subprocess.run(["systemctl", "is-active", candidate],
                                   capture_output=True, timeout=5)
                if r.stdout.decode().strip() == "active":
                    service_active = True
                    service_name = candidate
                    break
            except Exception:
                continue
        self._send_json({
            "success": True,
            "status": {
                "has_original": has_original,
                "has_custom": has_custom,
                "custom_enabled": has_custom and not os.path.exists(os.path.join(STATE_DIR, "disabled")),
                "has_logo": has_logo,
                "uploaded": {
                    "file_background": os.path.exists(FILE_BACKGROUND_PATH),
                    "password_background": os.path.exists(PASSWORD_BACKGROUND_PATH),
                    "password_logo": os.path.exists(PASSWORD_LOGO_PATH),
                    "ad_top": os.path.exists(AD_PATHS["top"]),
                    "ad_bottom": os.path.exists(AD_PATHS["bottom"]),
                    "ad_left": os.path.exists(AD_PATHS["left"]),
                    "ad_right": os.path.exists(AD_PATHS["right"])
                },
                "service_active": service_active,
                "service_name": service_name,
                "module_dir": MODULE_DIR,
                "app_version": APP_VERSION,
                "config": config
            }
        })

    def _check_update(self):
        """代理 fnOS 更新管理器的 check-update 接口，规避浏览器跨域限制。"""
        url = ("%s/api/check-update?app_key=%s&current_version=%s&channel=%s"
               % (UPDATE_MANAGER_URL, quote(UPDATE_APP_KEY), quote(APP_VERSION), quote(UPDATE_CHANNEL)))
        try:
            with urlopen(Request(url), timeout=8) as resp:
                raw = resp.read().decode("utf-8", "replace")
            try:
                data = json.loads(raw)
            except ValueError:
                data = {"update_available": False, "error": "更新服务器返回异常数据"}
        except HTTPError as e:
            # 404 表示软件尚未在管理器中登记，视为无可用更新而非报错。
            try:
                data = json.loads(e.read().decode("utf-8", "replace"))
            except (ValueError, OSError):
                data = {}
            data = dict(data, update_available=False)
            data.setdefault("error", "更新检查失败 (HTTP %d)" % e.code)
        except (URLError, OSError) as e:
            self._send_json({"success": False, "error": "无法连接更新服务器: %s" % e}, 502)
            return
        if not isinstance(data, dict):
            data = {"update_available": False, "error": "更新服务器返回异常数据"}
        self._send_json({"success": True, "update": data, "current_version": APP_VERSION, "app_key": UPDATE_APP_KEY})

    def _serve_logo(self):
        path = LOGO_PATH
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(__file__), "../server/share-icon.png")
        if not os.path.exists(path):
            self.send_response(404)
            self.end_headers()
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", get_mime(path))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_uploaded_file(self, path):
        if not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", get_mime(path))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, relpath):
        sdir = os.path.join(os.path.dirname(__file__), "static")
        fpath = os.path.normpath(os.path.join(sdir, relpath))
        if not fpath.startswith(os.path.normpath(sdir)):
            self._send_json({"success": False, "error": "Forbidden"}, 403)
            return
        if not os.path.isfile(fpath):
            self._send_json({"success": False, "error": "Not found"}, 404)
            return
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", get_mime(fpath))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _get_html(self):
        tpl_path = os.path.join(os.path.dirname(__file__), "templates/index.html")
        if os.path.exists(tpl_path):
            with open(tpl_path, "r", encoding="utf-8") as f:
                return f.read()
        return "<html><body><h1>Config UI not found</h1></body></html>"

class DualStackHTTPServer(HTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def create_server(host, port):
    try:
        return DualStackHTTPServer((host, port), CustomizerHandler)
    except (OSError, socket.gaierror):
        # 部分 fnOS 安装未启用 IPv6，回退到 IPv4 监听。
        return HTTPServer(("0.0.0.0", port), CustomizerHandler)


def main():
    port = int(os.environ.get("PORT", str(DEFAULT_PORT)))
    host = os.environ.get("HOST", "::")
    server = create_server(host, port)
    print(f"[Share Customizer] Server listening on {server.server_address[0]}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    print("[Share Customizer] Server stopped")


if __name__ == "__main__":
    main()
