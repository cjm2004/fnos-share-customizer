#!/usr/bin/env python3
import base64, os, json, re

with open(os.environ["ORIGINAL_INDEX"], "r", encoding="utf-8") as f:
    html = f.read()

cfg = {}
if os.path.exists(os.environ["CONFIG_FILE"]):
    with open(os.environ["CONFIG_FILE"], "r", encoding="utf-8") as f:
        try:
            cfg = json.load(f)
        except (ValueError, TypeError):
            cfg = {}
if not isinstance(cfg, dict):
    raise ValueError("配置必须是 JSON 对象")
cfg.pop("custom_share_format", None)

download_variant = cfg.get("download_button_variant", "solid")
download_color = cfg.get("download_button_color", "#2b6cff")
download_text = cfg.get("download_button_text_color", "#ffffff")
transfer_variant = cfg.get("transfer_button_variant", "soft")
transfer_color = cfg.get("transfer_button_color", "#e8efff")
transfer_text = cfg.get("transfer_button_text_color", "#2b6cff")
width_layout = cfg.get("button_width_layout", "download_wide")
button_order = cfg.get("button_order", "transfer_left")
title = cfg.get("title_text", "\u6587\u4ef6\u5206\u4eab")
footer = cfg.get("footer_text", "shared by cjm")
browser_title = cfg.get("browser_title", title)
logo_link = cfg.get("logo_link", "https://www.fnnas.com")
logo_new_tab = bool(cfg.get("logo_link_new_tab", False))
bg_color = cfg.get("background_color", "#ffffff")
row_color = cfg.get("file_row_color", "#ffffff")
row_hover = cfg.get("file_row_hover_color", "#f5f7fa")
primary = cfg.get("primary_color", "#2b6cff")
password_title = cfg.get("password_title", "\u8f93\u5165\u5bc6\u7801\u4ee5\u8bbf\u95ee\u6587\u4ef6")
password_hint = cfg.get("password_hint", "\u8bf7\u8f93\u5165\u5206\u4eab\u5bc6\u7801")
password_bg = cfg.get("password_background_color", "#ffffff")
password_button = cfg.get("password_button_color", "#2b6cff")
password_button_text = cfg.get("password_button_text_color", "#ffffff")
password_logo_file = os.environ["PASSWORD_LOGO_FILE"]
password_logo = bool(cfg.get("password_logo_uploaded", False) and os.path.isfile(password_logo_file))
password_footer = cfg.get("password_footer_text", "Copyright © 广州铁刃智造技术有限公司 版权所有")
if password_footer == "Copyright 广州xxx":
    password_footer = "Copyright © 广州铁刃智造技术有限公司 版权所有"
password_image = bool(cfg.get("password_background_image", False))
file_image = bool(cfg.get("file_background_image", False))
ad_slots = [slot for slot in ("top", "bottom", "left", "right") if cfg.get("ad_%s_enabled" % slot) and os.path.isfile(os.path.join(os.path.dirname(os.environ["CONFIG_FILE"]), "ad-%s.png" % slot))]
error_texts = {
    "\u65e0\u6548\u94fe\u63a5\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002": cfg.get("error_invalid_link", "\u65e0\u6548\u94fe\u63a5\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002"),
    "\u8be5\u94fe\u63a5\u8bbf\u95ee\u6b21\u6570\u5df2\u8fbe\u9650\u5236\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002": cfg.get("error_link_exceeded", "\u8be5\u94fe\u63a5\u8bbf\u95ee\u6b21\u6570\u5df2\u8fbe\u9650\u5236\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002"),
    "\u8be5\u94fe\u63a5\u5df2\u8fc7\u671f\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002": cfg.get("error_link_expired", "\u8be5\u94fe\u63a5\u5df2\u8fc7\u671f\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002"),
    "\u6587\u4ef6\u4e0d\u5b58\u5728\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002": cfg.get("error_file_missing", "\u6587\u4ef6\u4e0d\u5b58\u5728\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002"),
    "\u9644\u4ef6\u5df2\u4e22\u5931\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005": cfg.get("error_file_missing", "\u6587\u4ef6\u4e0d\u5b58\u5728\uff0c\u8bf7\u8054\u7cfb\u5206\u4eab\u8005\u3002"),
}
border_radius = cfg.get("button_border_radius", "6px")
show_dl = cfg.get("show_download_all", True)
show_transfer = cfg.get("show_transfer_button", True)
max_width = cfg.get("page_max_width", "800px")
max_width = max_width if max_width in {"640px", "800px", "960px", "1200px", "100%", "100vw"} else "800px"
logo_path = "/s/favicon.ico"

def color(value, default):
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else default

download_color = color(download_color, "#2b6cff")
download_text = color(download_text, "#ffffff")
transfer_color = color(transfer_color, "#e8efff")
transfer_text = color(transfer_text, "#2b6cff")
bg_color = color(bg_color, "#ffffff")
row_color = color(row_color, "#ffffff")
row_hover = color(row_hover, "#f5f7fa")
primary = color(primary, "#2b6cff")
password_bg = color(password_bg, "#ffffff")
password_button = color(password_button, "#2b6cff")
password_button_text = color(password_button_text, "#ffffff")
border_radius = border_radius if border_radius in {"0px", "4px", "6px", "12px", "999px"} else "6px"
download_variant = download_variant if download_variant in {"solid", "soft", "outline", "text"} else "solid"
transfer_variant = transfer_variant if transfer_variant in {"solid", "soft", "outline", "text"} else "soft"
button_order = button_order if button_order in {"download_left", "transfer_left"} else "transfer_left"

def button_style(variant, color, text):
    if variant == "outline":
        return f"background:transparent !important;color:{text} !important;border:1px solid {color} !important"
    if variant == "text":
        return f"background:transparent !important;color:{text} !important;border:1px solid transparent !important"
    return f"background:{color} !important;color:{text} !important;border:1px solid {color} !important"

download_flex, transfer_flex = {
    "equal": ("1 1 0%", "1 1 0%"),
    "transfer_wide": ("1 1 0%", "2 1 0%"),
}.get(width_layout, ("2 1 0%", "1 1 0%"))
dbtn = button_style(download_variant, download_color, download_text)
tbtn = button_style(transfer_variant, transfer_color, transfer_text)
download_order, transfer_order = ("1", "2") if button_order == "download_left" else ("2", "1")
password_background = "background-image:url('/s/password-background.png');background-size:cover;background-position:center;" if password_image else ""
file_background = "background-image:url('/s/file-background.png');background-size:cover;background-position:center;" if file_image else ""
ad_css = ""
if ad_slots:
    ad_css = ".cjm-ad-shell{position:relative;z-index:25;width:100%;display:flex;flex-direction:column;align-items:center;gap:12px;padding:12px 16px;box-sizing:border-box;visibility:visible}.cjm-ad{max-width:100%;height:auto;display:block;object-fit:contain;visibility:visible}.cjm-ad-side{position:fixed;display:block;visibility:visible;top:50%;transform:translateY(-50%);width:180px;max-height:600px;z-index:25}.cjm-ad-left{left:12px}.cjm-ad-right{right:12px}@media(max-width:680px){.cjm-ad-shell{padding:8px 10px;gap:8px}.cjm-ad-side{display:none;visibility:hidden}}"

action_css = """
.cjm-actions{position:fixed!important;left:50%!important;right:auto!important;bottom:max(16px,env(safe-area-inset-bottom))!important;transform:translateX(-50%)!important;width:min(680px,calc(100vw - 32px))!important;max-width:680px!important;display:flex!important;align-items:stretch!important;justify-content:center!important;gap:12px!important;padding:12px!important;margin:0!important;box-sizing:border-box!important;z-index:30!important}
.cjm-actions > button{min-width:0!important;min-height:44px!important;flex:1 1 0!important;white-space:normal!important;line-height:1.35!important;overflow-wrap:anywhere!important}
.cjm-actions > button[style*="display: none"]{display:none!important}
.cjm-actions[data-cjm-empty="true"]{display:none!important}
@media(max-width:520px){.cjm-actions{width:calc(100vw - 20px)!important;bottom:max(8px,env(safe-area-inset-bottom))!important;gap:8px!important;padding:8px!important}.cjm-actions > button{font-size:14px!important;padding:10px 8px!important}}
"""

style_extra = f"""
<style>
{ad_css}
{action_css}
:root {{ --semi-color-primary: {primary}; }}
[data-cjm-content] {{ max-width:{max_width} !important; }}
[data-cjm-ad-layout] {{ padding-top:calc(var(--cjm-header-height) + 8px) !important; }}
[data-cjm-ad-layout] .fixed[class~="top-[119px]"] {{ top:calc(var(--cjm-header-height) + 8px) !important; }}#root {{ padding-bottom:100px; }}
body {{ background-color: {bg_color} !important; }}
body{{{file_background}}}
button[data-cjm-action="download"]{{{dbtn};flex:{download_flex} !important;order:{download_order} !important;border-radius:{border_radius} !important;}}
button[data-cjm-action="transfer"]{{{tbtn};flex:{transfer_flex} !important;order:{transfer_order} !important;border-radius:{border_radius} !important;}}
.semi-table-tbody .semi-table-row,.semi-table-tbody .semi-table-row-cell{{background-color:{row_color} !important;}}
.semi-table-tbody .semi-table-row:hover,.semi-table-tbody .semi-table-row:hover .semi-table-row-cell{{background-color:{row_hover} !important;}}
[data-cjm-password],[data-cjm-password] > div{{background-color:{password_bg} !important;{password_background}}}
[data-cjm-password] button{{background-color:{password_button} !important;color:{password_button_text} !important;border-color:{password_button} !important;}}
</style>"""

def image_source(path):
    with open(path, "rb") as f:
        data = f.read()
    mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg" if data.startswith(b"\xff\xd8") else "image/gif" if data.startswith(b"GIF") else "image/webp"
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")


# 分享服务不会将任意 /s/*.png 映射到磁盘文件，内嵌广告避免返回 HTML 导致破图。
cfg.update({"password_logo_src": None, "ad_slots": ad_slots, "ad_sources": {}})
if password_logo:
    cfg["password_logo_src"] = image_source(password_logo_file)
for slot in ad_slots:
    cfg["ad_sources"][slot] = image_source(os.path.join(os.path.dirname(os.environ["CONFIG_FILE"]), "ad-%s.png" % slot))
js_config = json.dumps(cfg, ensure_ascii=True).replace("<", "\\u003c")
with open(os.path.join(os.path.dirname(__file__), "customize.js"), encoding="utf-8") as f:
    script = '<script id="fnos-share-customizer">window.__CUSTOM_CONFIG__=' + js_config + ";\n" + f.read() + "</script>"

html = re.sub(r'<meta name="description" content="[^"]*"/>',
              '<meta name="description" content="\u6587\u4ef6\u5206\u4eab shared by cjm"/>', html)
if '</head>' in html:
    html = html.replace('</head>', style_extra + '</head>')
if '</body>' in html:
    html = html.replace('</body>', script + '</body>')

with open(os.environ["CUSTOM_INDEX"], "w", encoding="utf-8") as f:
    f.write(html)
