#!/usr/bin/env python3
"""Export base (基建) WebM animations for an Arknights operator from PRTS."""

import argparse
import os
import sys
import urllib.parse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright is required: run 'pip install playwright' first")

LOAD_BTN = "\u70b9\u6b64\u8f7d\u5165\u6a21\u578b"


def find_chrome():
    candidates = [
        os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def select_option(page, select, text):
    select.click()
    page.wait_for_timeout(500)
    options = page.locator(".n-base-select-option", has_text=text)
    found = None
    for i in range(options.count()):
        opt = options.nth(i)
        if opt.is_visible() and opt.inner_text().strip() == text:
            found = opt
            break
    if found is None:
        for i in range(options.count()):
            opt = options.nth(i)
            if opt.is_visible():
                found = opt
                break
    if found is None:
        raise RuntimeError(f"option not found: {text}")
    found.click()
    page.wait_for_timeout(1200)


def find_download_button(page):
    locator = page.locator("button.n-button").filter(
        has=page.locator(
            'svg path[d^="M19 9h-4V3H9v6H5l7 7l7-7z"]'
        )
    )
    if locator.count() == 0:
        raise RuntimeError("WebM download button not found")
    return locator.first


def open_operator_page(page, operator):
    url = "https://prts.wiki/w/" + urllib.parse.quote(operator)
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)
    if page.locator("button", has_text=LOAD_BTN).count() == 0:
        search_url = (
            "https://prts.wiki/index.php?search="
            + urllib.parse.quote(operator)
            + "&fulltext=1"
        )
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
        links = page.locator(".mw-search-result a[href^='/w/']")
        if links.count() == 0:
            raise RuntimeError(f"operator not found on PRTS: {operator}")
        href = links.first.get_attribute("href")
        title = urllib.parse.unquote(href.split("/w/", 1)[1])
        page.goto(
            "https://prts.wiki/w/" + urllib.parse.quote(title),
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(2500)
    if page.locator("button", has_text=LOAD_BTN).count() == 0:
        raise RuntimeError(f"model viewer not found for operator: {operator}")


FORCE_VP8_JS = """
(() => {
    const OrigMR = window.MediaRecorder;
    window.MediaRecorder = function(stream, options) {
        const opts = Object.assign({}, options || {});
        opts.mimeType = 'video/webm;codecs=vp8';
        return new OrigMR(stream, opts);
    };
    window.MediaRecorder.isTypeSupported = OrigMR.isTypeSupported.bind(OrigMR);
    window.MediaRecorder.prototype = OrigMR.prototype;
})();
"""


def get_select_options(page, select):
    select.click()
    page.wait_for_timeout(500)
    seen = {}
    menus = page.locator(".n-base-select-menu")
    vl = None
    for i in range(menus.count()):
        m = menus.nth(i)
        if m.is_visible():
            vl_loc = m.locator(".v-vl")
            if vl_loc.count() > 0:
                vl = vl_loc.first
            break
    for _ in range(80):
        options = page.locator(".n-base-select-option")
        for i in range(options.count()):
            opt = options.nth(i)
            if opt.is_visible():
                t = opt.inner_text().strip()
                if t and t not in seen:
                    seen[t] = len(seen)
        if vl:
            at_bottom = vl.evaluate(
                "el => el.scrollTop >= el.scrollHeight - el.clientHeight - 5"
            )
            if at_bottom and len(seen) > 0:
                break
            vl.evaluate("el => el.scrollTop += 150")
        else:
            break
        page.wait_for_timeout(150)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return sorted(seen.keys(), key=lambda k: seen[k])


def run_export(operator, skin, group, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as p:
        chrome = find_chrome()
        if chrome:
            browser = p.chromium.launch(executable_path=chrome, headless=True)
        else:
            browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1400, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(FORCE_VP8_JS)
        page = context.new_page()
        try:
            open_operator_page(page, operator)
            load_btn = page.locator("button", has_text=LOAD_BTN).first
            load_btn.scroll_into_view_if_needed()
            load_btn.click()
            page.wait_for_timeout(5000)

            skin_select = page.locator(".n-select").nth(0)
            select_option(page, skin_select, skin or "\u9ed8\u8ba4")
            model_select = page.locator(".n-select").nth(1)
            select_option(page, model_select, group)

            anim_select = page.locator(".n-select").nth(2)
            animations = get_select_options(page, anim_select)
            print("ANIMATIONS", animations)

            skin_label = skin or "\u9ed8\u8ba4"
            for anim in animations:
                anim_select = page.locator(".n-select").nth(2)
                select_option(page, anim_select, anim)
                page.wait_for_timeout(2000)
                download = find_download_button(page)
                with page.expect_download(timeout=120000) as info:
                    download.click()
                dl = info.value
                fname = dl.suggested_filename if isinstance(dl.suggested_filename, str) else dl.suggested_filename()
                ext = os.path.splitext(fname)[1] or ".webm"
                out_path = os.path.join(
                    out_dir, f"{operator}-{skin_label}-{group}-{anim}-x1{ext}"
                )
                dl.save_as(out_path)
                print(
                    "EXPORTED",
                    anim,
                    "=>",
                    out_path,
                    os.path.getsize(out_path),
                )
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operator", help="Arknights operator name")
    parser.add_argument("--skin", default=None, help="skin name; default = 默认")
    parser.add_argument("--group", default="基建", help="model group; e.g. 基建, 正面")
    parser.add_argument("--out", default="prts_webm", help="output directory")
    args = parser.parse_args()
    run_export(args.operator, args.skin, args.group, args.out)


if __name__ == "__main__":
    main()
