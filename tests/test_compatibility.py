"""隔离测试：不修改真实系统服务、分享文件或用户配置。"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'source/app/bin'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv('FNOS_CUSTOM_STATE_DIR', str(tmp_path))
    module = load_module(ROOT / 'source/app/server/server.py', 'customizer_test')
    http = HTTPServer(('127.0.0.1', 0), module.CustomizerHandler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield module, f'http://127.0.0.1:{http.server_port}'
    http.shutdown()
    http.server_close()
    thread.join()


def request(base, path, data=None, content_type='application/json'):
    req = Request(base + path, data=data, headers={'Content-Type': content_type})
    try:
        response = urlopen(req)
    except HTTPError as response_error:
        response = response_error
    return response.status, response.read()




@pytest.fixture
def render(tmp_path):
    def run(config=None, body='', scripts='', assets=None):
        source = tmp_path / 'original.html'
        source.write_text('<!doctype html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原始</title></head><body><div id="root">' + body + '</div>' + scripts + '</body></html>')
        (tmp_path / 'web-config.json').write_text(json.dumps(config or {}))
        # 固定的有效图片，避免网络依赖。
        import base64
        image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aY1cAAAAASUVORK5CYII=')
        for asset in ['password-logo', 'ad-top', 'ad-bottom', 'ad-left', 'ad-right']:
            data = (assets or {}).get(asset, image)
            if data is not None:
                (tmp_path / (asset + '.png')).write_bytes(data)
        out = tmp_path / 'custom.html'
        env = dict(os.environ, ORIGINAL_INDEX=str(source), CUSTOM_INDEX=str(out), CONFIG_FILE=str(tmp_path / 'web-config.json'), PASSWORD_LOGO_FILE=str(tmp_path / 'password-logo.png'))
        subprocess.run([sys.executable, str(BIN / 'render-page.py')], env=env, check=True)
        return out.read_text()
    return run


def open_page(browser, html, width=390):
    context = browser.new_context(viewport={'width': width, 'height': 844}, is_mobile=width < 700, has_touch=width < 700)
    context.route('**/*', lambda route: route.fulfill(status=200, content_type='text/html', body=html) if route.request.resource_type == 'document' else route.abort())
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://localhost/s/test')
    page.wait_for_timeout(120)
    return context, page, errors


BODY = '<main class="max-w-[800px]"><p data-file-name="测试.zip">测试.zip 12 MB</p><a href="https://www.fnnas.com"><img><span>飞牛</span><span>原始页脚</span></a><div class="fixed bottom-0"><button onclick="window.downloads=(window.downloads||0)+1"><span>下载全部</span></button><button onclick="window.transfers=(window.transfers||0)+1"><span>打开 App 转存</span></button></div></main>'


@pytest.mark.parametrize('width', [320, 375, 390, 430, 768, 1440])
def test_layout_actions_and_ads(browser, render, width):
    cfg = {'browser_title': '测试分享', 'title_text': '自定义标题', 'footer_text': '自定义页脚', 'button_order': 'download_left', 'ad_top_enabled': True, 'ad_bottom_enabled': True, 'ad_left_enabled': True, 'ad_right_enabled': True}
    context, page, errors = open_page(browser, render(cfg, BODY), width)
    assert page.title() == '测试分享'
    assert page.locator('[data-cjm-brand] span').all_text_contents() == ['自定义标题', '自定义页脚']
    download = page.locator('[data-cjm-action="download"]')
    transfer = page.locator('[data-cjm-action="transfer"]')
    assert download.locator('span').count() == 1
    assert download.bounding_box()['x'] < transfer.bounding_box()['x']
    box = page.locator('.cjm-actions').bounding_box()
    assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1
    assert page.locator('#cjm-ad-left').is_visible() == (width > 680)
    assert page.locator('#cjm-ad-top').count() == 1
    assert page.locator('#cjm-ad-bottom').count() == 1
    for slot in ('top', 'bottom', 'left', 'right'):
        assert page.locator('#cjm-ad-' + slot).evaluate('(img) => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0')
    download.click()
    transfer.click()
    assert page.evaluate('window.downloads') == 1
    assert page.evaluate('window.transfers') == 1
    assert not errors
    context.close()


@pytest.mark.parametrize('mime', ['image/png', 'image/jpeg', 'image/gif', 'image/webp'])
def test_ad_image_formats(browser, render, mime):
    import base64
    if mime == 'image/gif':
        image = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
    else:
        generator = browser.new_page()
        uri = generator.evaluate('''(mime) => {
            const canvas = document.createElement('canvas');
            canvas.width = 12; canvas.height = 6;
            canvas.getContext('2d').fillRect(0, 0, 12, 6);
            return canvas.toDataURL(mime);
        }''', mime)
        generator.close()
        assert uri.startswith('data:' + mime + ';base64,')
        image = base64.b64decode(uri.split(',', 1)[1])
    html = render({'ad_top_enabled': True}, BODY, assets={'ad-top': image})
    context, page, errors = open_page(browser, html)
    ad = page.locator('#cjm-ad-top')
    assert ad.get_attribute('src') == 'data:' + mime + ';base64,' + base64.b64encode(image).decode('ascii')
    assert ad.evaluate('(img) => img.complete && img.naturalWidth > 0')
    assert not errors
    context.close()


@pytest.mark.parametrize('enabled,present', [(False, True), (True, False)])
def test_disabled_or_missing_ad(browser, render, enabled, present):
    html = render({'ad_top_enabled': enabled, 'ad_sources': {'top': 'https://invalid.example/ad.png'}}, BODY,
                  assets=None if present else {'ad-top': None})
    context, page, errors = open_page(browser, html)
    assert page.locator('.cjm-ad').count() == 0
    assert page.evaluate('window.__CUSTOM_CONFIG__.ad_sources') == {}
    assert not errors
    context.close()


@pytest.mark.parametrize('download,transfer', [(True, True), (False, True), (True, False), (False, False)])
def test_action_visibility(browser, render, download, transfer):
    context, page, errors = open_page(browser, render({'show_download_all': download, 'show_transfer_button': transfer}, BODY))
    assert page.locator('[data-cjm-action="download"]').is_visible() == download
    assert page.locator('[data-cjm-action="transfer"]').is_visible() == transfer
    assert not errors
    context.close()


def test_password_page_ignores_removed_share_format(browser, render):
    cfg = {'password_title': '请输入提取码', 'password_hint': '四位密码', 'password_footer_text': '测试版权', 'password_logo_uploaded': True, 'custom_share_format': '{文件名}|{文件大小}|{分享链接}|{密码}'}
    body = '<img alt="logo"><section><h1>输入密码以访问文件</h1><form><input type="password"><button type="button">确定</button></form></section><p class="mb-2">版权</p>'
    context, page, errors = open_page(browser, render(cfg, body))
    assert page.locator('h1').inner_text() == '请输入提取码'
    assert page.locator('input').get_attribute('placeholder') == '四位密码'
    assert page.locator('img').get_attribute('src').startswith('data:image/png;base64,')
    assert page.locator('p.mb-2').inner_text() == '测试版权'
    page.locator('input').fill('1234')
    page.evaluate('(body) => document.getElementById("root").innerHTML = body', BODY)
    page.wait_for_timeout(120)
    assert page.locator('#cjm-share-format').count() == 0
    assert page.locator('[data-cjm-password-input]').count() == 0
    assert page.evaluate('window.__CUSTOM_CONFIG__.custom_share_format') is None
    assert page.evaluate('sessionStorage.length') == 0
    assert page.evaluate('window.__CJM_SHARE_CLIPBOARD_PATCHED__') is None
    assert not errors
    context.close()


@pytest.mark.parametrize('message,key', [('无效链接', 'error_invalid_link'), ('该链接已过期', 'error_link_expired'), ('该链接访问次数已达限制', 'error_link_exceeded'), ('文件不存在，请联系分享者。', 'error_file_missing')])
def test_error_text(browser, render, message, key):
    context, page, errors = open_page(browser, render({key: '自定义错误'}, '<h1>' + message + '</h1>'))
    assert page.locator('h1').inner_text() == '自定义错误'
    assert not errors
    context.close()


def test_script_injection_and_missing_root(browser, render):
    html = render({'browser_title': '</script><script>window.attacked=true</script>'}, BODY)
    context, page, errors = open_page(browser, html)
    assert page.evaluate('window.attacked') is None
    assert not errors
    page.evaluate('document.getElementById("root").remove()')
    page.wait_for_timeout(80)
    assert not errors
    context.close()


def test_observer_stops_mutating_and_preserves_native_changes(browser, render):
    context, page, errors = open_page(browser, render({}, BODY))
    page.evaluate('window.mutations=0; new MutationObserver(rs=>window.mutations+=rs.length).observe(document.body,{subtree:true,childList:true,characterData:true}); document.querySelector("button span").textContent="下载"')
    page.wait_for_timeout(100)
    count = page.evaluate('window.mutations')
    page.wait_for_timeout(200)
    assert page.evaluate('window.mutations') == count
    assert page.locator('button span').first.inner_text() == '下载'
    assert not errors
    context.close()


def test_asset_version_validation(tmp_path):
    module = load_module(BIN / 'page-assets.py', 'assets_test')
    assets = tmp_path / 's/static/1.0.16'
    assets.mkdir(parents=True)
    (assets / 'main.js').write_text('console.log(1)')
    page = tmp_path / 'index.html'
    page.write_text('<html><script src="/s/static/1.0.14/old.js"></script></html>')
    with pytest.raises(ValueError, match='资源不存在'):
        module.validate(page, tmp_path)
    page.write_text('<html><script src="/s/static/1.0.16/main.js"></script></html>')
    assert module.validate(page, tmp_path, native=True)
    page.write_text(page.read_text().replace('</html>', '<script id="fnos-share-customizer"></script></html>'))
    with pytest.raises(ValueError, match='覆盖'):
        module.validate(page, tmp_path, native=True)


@pytest.mark.parametrize('config', [[], None, {'title_text': 1}, {'show_download_all': 'false'}])
def test_invalid_config(server, config):
    _, base = server
    assert request(base, '/api/config', json.dumps(config).encode())[0] == 400


def test_config_roundtrip_and_management_page(server, browser):
    _, base = server
    status, data = request(base, '/api/config', json.dumps({'title_text': '手机测试', 'show_download_all': False}).encode())
    assert status == 200 and json.loads(data)['config']['show_download_all'] is False
    assert json.loads(request(base, '/api/config')[1])['config']['title_text'] == '手机测试'
    page = browser.new_page(viewport={'width': 390, 'height': 844})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base)
    page.wait_for_timeout(300)
    assert page.locator('#titleText').input_value() == '手机测试'
    assert page.locator('#customShareFormat').count() == 0
    assert '分享链接格式' not in page.content()
    page.get_by_role('button', name='文字内容', exact=True).click()
    page.locator('#titleText').fill('保存测试')
    with page.expect_response('**/api/config') as saved:
        page.get_by_role('button', name='保存配置', exact=True).click()
    assert saved.value.status == 200
    assert json.loads(request(base, '/api/config')[1])['config']['title_text'] == '保存测试'
    assert not errors
    page.close()


@pytest.mark.parametrize('endpoint,field', [('/api/upload-logo', 'logo'), ('/api/upload-password-logo', 'image'), ('/api/upload-password-background', 'image'), ('/api/upload-file-background', 'image'), ('/api/upload-ad/top', 'image'), ('/api/upload-ad/bottom', 'image'), ('/api/upload-ad/left', 'image'), ('/api/upload-ad/right', 'image')])
def test_image_uploads(server, endpoint, field):
    module, base = server
    # WebP 末尾的换行和连字符必须原样保存，不能被 multipart rstrip 剥掉。
    image = b'RIFF' + (16).to_bytes(4, 'little') + b'WEBPVP8 ' + b'abcd\r\n--'
    boundary = 'test-boundary'
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="' + field + '"; filename="test.webp"\r\nContent-Type: image/webp\r\n\r\n').encode() + image + ('\r\n--' + boundary + '--\r\n').encode()
    status, data = request(base, endpoint, body, 'multipart/form-data; boundary="' + boundary + '"')
    assert status == 200, data
    if endpoint.endswith('background'):
        filename = endpoint.removeprefix('/api/upload-') + '.png'
        assert (Path(module.STATE_DIR) / filename).read_bytes() == image
    else:
        path = json.loads(data)['path']
        assert request(base, path)[1] == image


def test_missing_logo_does_not_crash(server):
    _, base = server
    assert request(base, '/api/upload-logo', b'{}')[0] == 400
    assert request(base, '/api/config')[0] == 200


def test_removed_share_format_is_discarded(server):
    module, base = server
    Path(module.CONFIG_FILE).write_text(json.dumps({
        'custom_share_format': '旧分享文案', 'title_text': '保留标题',
        'ad_top_enabled': True, 'custom_other': '保留扩展配置',
    }))
    loaded = json.loads(request(base, '/api/config')[1])['config']
    assert 'custom_share_format' not in loaded
    assert 'custom_share_format' not in module.DEFAULT_CONFIG
    assert loaded['title_text'] == '保留标题'
    status, data = request(base, '/api/config', json.dumps({
        'custom_share_format': '导入旧文案', 'footer_text': '保留页脚',
    }).encode())
    assert status == 200
    saved = json.loads(data)['config']
    assert 'custom_share_format' not in saved
    assert saved['ad_top_enabled'] is True
    assert saved['title_text'] == '保留标题'
    assert saved['footer_text'] == '保留页脚'
    assert saved['custom_other'] == '保留扩展配置'
    assert 'custom_share_format' not in json.loads(Path(module.CONFIG_FILE).read_text())


@pytest.mark.parametrize('width', [390, 1440])
def test_native_copy_is_not_intercepted(browser, render, width):
    body = BODY + """<button id="native-copy" onclick="navigator.clipboard.writeText('原生分享文案');window.nativeCopies=(window.nativeCopies||0)+1">复制分享链接</button>"""
    html = render({'custom_share_format': '不应复制的旧文案'}, body)
    assert 'custom_share_format' not in html
    context, page, errors = open_page(browser, html, width)
    page.evaluate("Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {writeText: value => {window.copiedText = value; return Promise.resolve();}}})")
    page.locator('#native-copy').click()
    assert page.evaluate('window.nativeCopies') == 1
    assert page.evaluate('window.copiedText') == '原生分享文案'
    assert page.locator('#cjm-share-format').count() == 0
    assert not errors
    context.close()
