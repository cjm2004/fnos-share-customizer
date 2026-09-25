/* 只增强页面外观，不替换飞牛的路由、认证、下载及转存事件。 */
(function () {
  'use strict';
  var cfg = window.__CUSTOM_CONFIG__ || {};
  var scheduled = false;
  var observer;
  var adHeader = null;
  var adLayout = null;
  var adHeaderObserver = null;
  function syncTopAd(brand) {
    var image = document.getElementById('cjm-ad-top');
    var header = image && brand && brand.closest('.fixed.top-0');
    var layout = header && header.parentElement;
    if (header !== adHeader) {
      if (adHeaderObserver) adHeaderObserver.disconnect();
      if (adLayout) {
        delete adLayout.dataset.cjmAdLayout;
        adLayout.style.removeProperty('--cjm-header-height');
      }
      adHeader = header;
      adLayout = layout;
      if (header && typeof ResizeObserver !== 'undefined') {
        adHeaderObserver = new ResizeObserver(schedule);
        adHeaderObserver.observe(header);
      }
    }
    if (!header) return;
    // 广告必须跟随固定页头，放在品牌和计数栏之间，不能在正文外重复占位。
    var shell = image.parentElement;
    if (shell.parentElement !== header || brand.nextSibling !== shell) header.insertBefore(shell, brand.nextSibling);
    layout.dataset.cjmAdLayout = 'true';
    var height = header.getBoundingClientRect().height + 'px';
    if (layout.style.getPropertyValue('--cjm-header-height') !== height) layout.style.setProperty('--cjm-header-height', height);
  }
  var errors = {
    '无效链接，请联系分享者。': 'error_invalid_link',
    '无效链接': 'error_invalid_link',
    '该链接访问次数已达限制，请联系分享者。': 'error_link_exceeded',
    '该链接访问次数已达限制': 'error_link_exceeded',
    '该链接已过期，请联系分享者。': 'error_link_expired',
    '该链接已过期': 'error_link_expired',
    '文件不存在，请联系分享者。': 'error_file_missing',
    '附件已丢失，请联系分享者': 'error_file_missing'
  };
  function text(el, value) {
    if (el && typeof value === 'string' && el.textContent !== value) el.textContent = value;
  }
  function safeLink(value) {
    try {
      var link = new URL(value, location.href);
      return /^(https?:)$/.test(link.protocol) ? link.href : '';
    } catch (_) { return ''; }
  }
  function patch() {
    var root = document.getElementById('root');
    if (typeof cfg.browser_title === 'string') document.title = cfg.browser_title;
    if (!root) return;
    var field = root.querySelector('input[type="password"], input[data-cjm-password-input]');
    if (field) {
      field.dataset.cjmPasswordInput = 'true';
      var form = field.closest('form') || field.parentElement;
      var panel = form.parentElement || form;
      panel.dataset.cjmPassword = 'true';
      text(panel.querySelector('h1, h2'), cfg.password_title);
      if (typeof cfg.password_hint === 'string') field.placeholder = cfg.password_hint;
      text(root.querySelector('p.mb-2'), cfg.password_footer_text);
      var logo = root.querySelector('img[alt="logo"]');
      if (logo && cfg.password_logo_src && logo.src !== cfg.password_logo_src) logo.src = cfg.password_logo_src;
    }
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var node;
    while ((node = walker.nextNode())) {
      var key = errors[node.nodeValue.trim()];
      if (key && typeof cfg[key] === 'string' && node.nodeValue.trim() !== cfg[key]) node.nodeValue = cfg[key];
    }
    var brand = root.querySelector('a[data-cjm-brand], a[href="https://www.fnnas.com"], a[href="https://www.fnnas.com/"]');
    if (brand) {
      brand.dataset.cjmBrand = 'true';
      if (typeof cfg.logo_link === 'string') {
        var href = cfg.logo_link && safeLink(cfg.logo_link);
        if (href) brand.href = href; else brand.removeAttribute('href');
        brand.target = cfg.logo_link_new_tab ? '_blank' : '_self';
        brand.rel = 'noopener noreferrer';
      }
      var icon = brand.querySelector('img');
      if (icon && cfg.logo_uploaded && icon.getAttribute('src') !== '/s/favicon.ico') icon.src = '/s/favicon.ico';
      var spans = brand.querySelectorAll('span');
      text(spans[0], cfg.title_text);
      text(spans[1], cfg.footer_text);
    }
    root.querySelectorAll('.fixed.bottom-0, [data-cjm-actions]').forEach(function (group) {
      var buttons = Array.from(group.querySelectorAll('button'));
      var download = buttons.find(function (b) { return /下载|download/i.test(b.textContent); });
      var transfer = buttons.find(function (b) { return /转存|transfer|open.*app/i.test(b.textContent); });
      if (!download || !transfer || buttons.length !== 2) return;
      group.dataset.cjmActions = 'true';
      group.classList.add('cjm-actions');
      download.dataset.cjmAction = 'download';
      transfer.dataset.cjmAction = 'transfer';
      download.style.display = cfg.show_download_all === false ? 'none' : '';
      transfer.style.display = cfg.show_transfer_button === false ? 'none' : '';
      group.dataset.cjmEmpty = String(cfg.show_download_all === false && cfg.show_transfer_button === false);
      // 不改按钮内容：保留选中文件后的“下载”语义、图标及 React 子节点。
    });
    var content = root.querySelector('main, .max-w-\\[800px\\]');
    if (content) content.dataset.cjmContent = 'true';
    (cfg.ad_slots || []).forEach(function (slot) {
      var source = cfg.ad_sources && cfg.ad_sources[slot];
      if (!source || document.getElementById('cjm-ad-' + slot)) return;
      var image = document.createElement('img');
      image.id = 'cjm-ad-' + slot;
      image.src = source;
      image.alt = '广告';
      if (slot === 'top') image.addEventListener('load', schedule);
      var side = slot === 'left' || slot === 'right';
      image.className = 'cjm-ad' + (side ? ' cjm-ad-side cjm-ad-' + slot : '');
      if (side) document.body.appendChild(image);
      else {
        var shell = document.createElement('div');
        shell.className = 'cjm-ad-shell';
        shell.appendChild(image);
        if (slot === 'top') document.body.insertBefore(shell, root); else document.body.appendChild(shell);
      }
    });
    syncTopAd(brand);
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(function () {
      scheduled = false;
      observer.disconnect();
      try { patch(); } catch (error) { console.warn('[Share Customizer]', error); }
      finally { observer.observe(document.body, { childList: true, subtree: true, characterData: true }); }
    });
  }
  function start() {
    observer = new MutationObserver(schedule);
    schedule();
    window.addEventListener('resize', schedule);
    window.addEventListener('popstate', schedule);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true }); else start();
})();
