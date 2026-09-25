"""浏览器测试共用一个 Playwright 生命周期，避免嵌套同步事件循环。"""
import pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope='session')
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        yield browser
        browser.close()

