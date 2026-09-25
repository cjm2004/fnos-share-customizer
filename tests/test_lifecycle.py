"""用隔离的 systemctl/mount 替身验证生命周期，不触碰宿主挂载。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / 'source/app/bin'
MOCK = r'''#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
root = Path(os.environ['MOCK_ROOT'])
mountfile = root / 'mounts.json'
mounts = json.loads(mountfile.read_text()) if mountfile.exists() else {}
with (root / 'calls.log').open('a') as f:
    f.write(name + ' ' + ' '.join(args) + '\n')
if name == 'id':
    print('0')
elif name == 'sleep':
    pass
elif name == 'systemctl':
    pass
elif name == 'mountpoint':
    sys.exit(0 if args[-1] in mounts else 1)
elif name == 'mount':
    source, target = args[-2:]
    if os.environ.get('FAIL_MOUNT') == Path(target).name:
        sys.exit(1)
    if target in mounts:
        raise RuntimeError('重复绑定挂载')
    backup = root / ('saved-' + str(len(mounts)))
    shutil.copy2(target, backup)
    mounts[target] = str(backup)
    shutil.copy2(source, target)
elif name == 'umount':
    target = args[-1]
    if target not in mounts:
        sys.exit(1)
    shutil.copy2(mounts.pop(target), target)
mountfile.write_text(json.dumps(mounts))
'''


@pytest.fixture
def env(tmp_path):
    module = tmp_path / 'module'
    assets = module / 's/static/1.0.16'
    assets.mkdir(parents=True)
    (assets / 'main.js').write_text('console.log("new")')
    (module / 'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><script type="module" src="/s/static/1.0.16/main.js"></script></head><body><div id="root"></div></body></html>')
    (module / 'favicon.ico').write_bytes(b'native-icon')
    state = tmp_path / 'state'
    state.mkdir()
    (state / 'web-config.json').write_text('{}')
    (state / 'original-index.html').write_text('旧版本备份不能恢复')
    mockbin = tmp_path / 'mockbin'
    mockbin.mkdir()
    for name in ['id', 'sleep', 'systemctl', 'mountpoint', 'mount', 'umount']:
        file = mockbin / name
        file.write_text(MOCK)
        file.chmod(0o755)
    return dict(os.environ, PATH=str(mockbin) + ':' + os.environ['PATH'], MOCK_ROOT=str(tmp_path), FNOS_CUSTOM_STATE_DIR=str(state), FNOS_CUSTOM_SYSTEMD_DIR=str(tmp_path / 'systemd'), FNOS_SHARE_MODULE_DIR=str(module))


def run(script, env, check=True):
    result = subprocess.run(['bash', str(BIN / script), '0'], env=env, text=True, capture_output=True)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def mounts(env):
    path = Path(env['MOCK_ROOT']) / 'mounts.json'
    return json.loads(path.read_text()) if path.exists() else {}


def test_apply_remount_upgrade_and_restore(env):
    state, module = Path(env['FNOS_CUSTOM_STATE_DIR']), Path(env['FNOS_SHARE_MODULE_DIR'])
    native = (module / 'index.html').read_text()
    (state / 'ad-top.png').write_bytes(b'img')
    run('apply.sh', env)
    assert 'fnos-share-customizer' in (module / 'index.html').read_text()
    assert (state / 'original-index.html').read_text() == native
    assert len(mounts(env)) == 2
    override = Path(env['FNOS_CUSTOM_SYSTEMD_DIR']) / 'trim_sharelink.service.d/custom-share-page.conf'
    assert override.exists()
    assert (state / 'customize.js').exists()
    run('mount-assets.sh', env)
    assert len(mounts(env)) == 2
    # 模拟系统升级：服务停止后卸载，发布新资源和入口，重新启动。
    subprocess.run(['umount', str(module / 'index.html')], env=env, check=True)
    next_assets = module / 's/static/1.0.17'
    next_assets.mkdir()
    (next_assets / 'next.js').write_text('console.log("next")')
    new_native = native.replace('1.0.16/main.js', '1.0.17/next.js')
    (module / 'index.html').write_text(new_native)
    shutil.rmtree(module / 's/static/1.0.16')
    run('mount-assets.sh', env)
    assert '1.0.17/next.js' in (module / 'index.html').read_text()
    assert '1.0.16' not in (module / 'index.html').read_text()
    run('restore.sh', env)
    assert not mounts(env)
    assert (module / 'index.html').read_text() == new_native
    assert not override.exists()
    assert (state / 'disabled').exists()
    run('mount-assets.sh', env)
    assert not mounts(env)
    run('apply.sh', env)
    assert not (state / 'disabled').exists()
    assert 'fnos-share-customizer' in (module / 'index.html').read_text()


def test_fail_closed_on_stale_assets(env):
    module = Path(env['FNOS_SHARE_MODULE_DIR'])
    (module / 's/static/1.0.16/main.js').unlink()
    result = run('mount-assets.sh', env, check=False)
    assert result.returncode != 0
    assert not mounts(env)
    assert 'fnos-share-customizer' not in (module / 'index.html').read_text()


def test_rolls_back_partial_mount(env):
    state, module = Path(env['FNOS_CUSTOM_STATE_DIR']), Path(env['FNOS_SHARE_MODULE_DIR'])
    (state / 'custom-logo.png').write_bytes(b'logo')
    env['FAIL_MOUNT'] = 'favicon.ico'
    result = run('mount-assets.sh', env, check=False)
    assert result.returncode != 0
    assert not mounts(env)
    assert 'fnos-share-customizer' not in (module / 'index.html').read_text()


def test_malformed_config_does_not_mount(env):
    state = Path(env['FNOS_CUSTOM_STATE_DIR'])
    (state / 'web-config.json').write_text('[]')
    assert run('mount-assets.sh', env, check=False).returncode != 0
    assert not mounts(env)


def test_restored_mode_is_a_noop(env):
    state = Path(env['FNOS_CUSTOM_STATE_DIR'])
    (state / 'disabled').touch()
    run('mount-assets.sh', env)
    assert not mounts(env)
    assert not (state / 'share-index.html').exists()
