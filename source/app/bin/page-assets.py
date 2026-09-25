#!/usr/bin/env python3
"""校验分享页入口引用的本地资源，禁止把旧版本入口重新挂载。"""
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.entry = False
        self.custom = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id') == 'fnos-share-customizer':
            self.custom = True
        if tag == 'script' and attrs.get('src'):
            self.urls.append(attrs['src'])
            self.entry = True
        if tag == 'link' and attrs.get('rel') in ('stylesheet', 'modulepreload') and attrs.get('href'):
            self.urls.append(attrs['href'])


def validate(page, module, native=False):
    html = Path(page).read_text(encoding='utf-8')
    parser = Assets()
    parser.feed(html)
    if not parser.entry or '</html>' not in html.lower():
        raise ValueError('分享页不完整或缺少前端入口')
    if native and (parser.custom or '__CUSTOM_CONFIG__' in html):
        raise ValueError('原始页面仍被旧自定义页面覆盖')
    root = Path(module).resolve()
    for url in parser.urls:
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            continue
        asset = (root / unquote(parsed.path).lstrip('/')).resolve()
        if not asset.is_relative_to(root) or not asset.is_file() or not asset.stat().st_size:
            raise ValueError('分享页引用的资源不存在: ' + parsed.path)
    return True


if __name__ == '__main__':
    try:
        validate(sys.argv[1], sys.argv[2], '--native' in sys.argv[3:])
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
