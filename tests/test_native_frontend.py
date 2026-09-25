"""可选集成测试：使用本机飞牛真实前端，接口以隔离响应替代，不访问用户分享。"""
import json
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = Path(os.environ.get('FNOS_TEST_MODULE_DIR', '/usr/trim/www/modules/trim_sharelink'))
ASSETS = MODULE / 's/static'


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('state', ['password', 'invalid', 'expired', 'exceeded', 'files', 'many_files'])
@pytest.mark.parametrize('top_ad', [False, True])
def test_native_frontend(tmp_path, browser, width, state, top_ad):
    if not ASSETS.is_dir():
        pytest.skip('本机没有飞牛前端资源')
    entries = [p for p in ASSETS.glob('*/*.js') if 'getElementById("root")' in p.read_text(errors='replace')]
    assert entries, '未识别到飞牛前端入口'
    entry = max(entries, key=lambda p: p.stat().st_mtime)
    styles = ''.join('<link rel="stylesheet" href="/' + str(p.relative_to(MODULE)) + '">' for p in entry.parent.glob('index-*.css'))
    files_state = state in ('files', 'many_files')
    codes = {'password': 3000008, 'invalid': 3000006, 'expired': 3000007, 'exceeded': 3000007, 'files': 0, 'many_files': 0}
    data = {'code': codes[state], 'data': {'token': 'isolated-test-token'} if files_state else {}, 'msg': 'expired' if state == 'expired' else 'exceed' if state == 'exceeded' else ''}
    source = tmp_path / 'native.html'
    source.write_text('<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + styles + '<script type="module" src="/' + str(entry.relative_to(MODULE)) + '"></script></head><body><div id="root"></div><script id="share-data" type="application/json">' + json.dumps(data) + '</script><script id="link-type" type="application/json">1</script></body></html>')
    config = {'browser_title': '集成测试', 'title_text': '自定义分享标题', 'footer_text': '分享说明', 'logo_link': 'https://example.com/brand', 'password_title': '测试提取码', 'password_hint': '请输入测试密码', 'error_invalid_link': '测试无效链接', 'error_link_expired': '测试过期链接', 'error_link_exceeded': '测试次数超限'}
    # 真实横幅尺寸，避免 1×1 图片掩盖顶部重叠与列表空白。
    import struct
    import zlib
    def chunk(kind, value):
        return struct.pack('!I', len(value)) + kind + value + struct.pack('!I', zlib.crc32(kind + value))
    image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 1200, 180, 8, 2, 0, 0, 0))
    image += chunk(b'IDAT', zlib.compress((b'\x00' + b'\x40\x80\xc0' * 1200) * 180)) + chunk(b'IEND', b'')
    (tmp_path / 'ad-top.png').write_bytes(image)
    config['ad_top_enabled'] = top_ad
    cfg = tmp_path / 'config.json'
    cfg.write_text(json.dumps(config))
    output = tmp_path / 'custom.html'
    env = dict(os.environ, ORIGINAL_INDEX=str(source), CUSTOM_INDEX=str(output), CONFIG_FILE=str(cfg), PASSWORD_LOGO_FILE=str(tmp_path / 'password-logo.png'))
    subprocess.run([sys.executable, str(ROOT / 'source/app/bin/render-page.py')], env=env, check=True)
    requests = []
    context = browser.new_context(viewport={'width': width, 'height': 844}, is_mobile=width < 700, has_touch=width < 700, locale='zh-CN', user_agent='Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36' if width < 700 else None)
    def route_request(route):
        path = urlsplit(route.request.url).path
        if route.request.resource_type == 'document':
            route.fulfill(content_type='text/html', body=output.read_text())
        elif path.startswith('/s/static/'):
            file = MODULE / path.lstrip('/')
            if file.is_file():
                route.fulfill(content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream', body=file.read_bytes())
            else:
                route.fulfill(status=404)
        elif '/api/v1/share/' in path:
            requests.append(path)
            if path.endswith('/pwd'):
                route.fulfill(json={'code': 3000009, 'msg': '', 'data': {}})
            else:
                route.fulfill(json={'code': 0, 'data': {'files': [{'file': '兼容性测试.txt' if i == 0 else f'文件{i:03d}.txt', 'size': 12, 'isDir': 0, 'fileId': i + 1, 'path': '/', 'modTime': 1720000000} for i in range(100 if state == 'many_files' else 1)]}, 'msg': ''})
        else:
            route.fulfill(status=404)
    context.route('**/*', route_request)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda message: print(message.text) if message.type == 'error' else None)
    page.goto('http://localhost/s/isolated-compatibility-test')
    page.wait_for_timeout(1000)
    assert not errors, errors
    assert page.locator('#root').inner_text().strip(), '真实前端仍然空白'
    assert page.title() == '集成测试'
    if top_ad:
        assert page.locator('#cjm-ad-top').evaluate('(img) => img.complete && img.naturalWidth == 1200')
    else:
        assert page.locator('#cjm-ad-top').count() == 0
    if state == 'password':
        assert page.locator('h1').inner_text() == '测试提取码'
        page.locator('input[type="password"]').fill('wrong')
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(500)
        assert any(path.endswith('/pwd') for path in requests)
        assert '密码错误' in page.locator('#root').inner_text()
    elif not files_state:
        assert {'invalid': '测试无效链接', 'expired': '测试过期链接', 'exceeded': '测试次数超限'}[state] in page.locator('#root').inner_text()
    else:
        assert '兼容性测试.txt' in page.locator('#root').inner_text()
        if width < 700:
            assert page.locator('[data-cjm-action="download"]').count() == 1
            assert page.locator('[data-cjm-action="transfer"]').count() == 1
            brand = page.locator('[data-cjm-brand]')
            assert brand.locator('span').all_text_contents() == ['自定义分享标题', '分享说明']
            assert brand.get_attribute('href') == 'https://example.com/brand'
            assert brand.locator('img').evaluate('(img) => img.complete && img.naturalWidth > 0')
            # 点击命中原 Logo/标题，不被广告层挡住。
            brand.click(trial=True)
            header = brand.locator('..')
            def check_layout():
                brand_box = brand.bounding_box()
                header_box = header.bounding_box()
                file_box = page.get_by_text('兼容性测试.txt', exact=True).bounding_box()
                assert 0 <= file_box['y'] - (header_box['y'] + header_box['height']) <= 16
                if top_ad:
                    ad_box = page.locator('#cjm-ad-top').bounding_box()
                    assert ad_box['y'] >= brand_box['y'] + brand_box['height']
                    counter_box = page.get_by_text(f'共 {100 if state == "many_files" else 1} 项', exact=True).bounding_box()
                    assert counter_box['y'] >= ad_box['y'] + ad_box['height']
                    assert page.locator('#cjm-ad-top').count() == 1
            check_layout()
            if top_ad:
                # 模拟图片延迟加载/高度改变，页头与列表应自动重新对齐。
                page.locator('#cjm-ad-top').evaluate("img => { img.style.height = '90px'; }")
                page.wait_for_timeout(200)
                check_layout()
                page.locator('#cjm-ad-top').evaluate("img => img.style.removeProperty('height')")
                page.wait_for_timeout(200)
                check_layout()
            page.set_viewport_size({'width': 430, 'height': 844})
            page.wait_for_timeout(200)
            check_layout()
            if state == 'many_files':
                page.evaluate('window.scrollTo(0, 1800)')
                page.wait_for_timeout(200)
                assert page.get_by_text('文件035.txt', exact=True).count() == 1
                page.evaluate('window.scrollTo(0, 0)')
                page.wait_for_timeout(200)
                check_layout()
            else:
                # 原生全选点击及 React 重渲染仍正常。
                header.locator('img').last.click()
                page.wait_for_timeout(200)
                assert '已选择' in header.inner_text() or '已选' in header.inner_text()
                assert page.locator('#cjm-ad-top').count() == int(top_ad)
                brand.click(trial=True)
    assert not errors
    context.close()
