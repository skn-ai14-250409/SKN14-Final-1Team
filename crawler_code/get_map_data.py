# -*- coding: utf-8 -*-
import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode, urldefrag, unquote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

# ========= 기본 설정 (map 전용) =========
OUTPUT_DIR = "map_docs_crawled"
MAX_PAGES = 10000
CRAWL_DELAY_SEC = 1
WAIT_SEC = 20

# ========= 크롤 제한 =========
ALLOW_DOMAINS = {"developers.google.com"}
ALLOW_PATH_PREFIXES = ["/maps"]

START_URLS = [
    "https://developers.google.com/maps?hl=ko",
]

# ========= 유틸: URL 정규화/허용판정 =========
def normalize_url(url: str) -> str:
    if not url:
        return ""
    url, _ = urldefrag(url)
    parsed = urlparse(url)

    scheme = "https"
    netloc = parsed.netloc

    qs = parse_qs(parsed.query)
    qs["hl"] = ["ko"]
    query = urlencode({k: v[-1] for k, v in qs.items()}, doseq=False)

    path = re.sub(r"//+", "/", parsed.path)

    normalized = urlunparse((scheme, netloc, path, "", query, ""))
    return normalized


def is_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.netloc not in ALLOW_DOMAINS:
            return False
        path = parsed.path or "/"

        disallow_substrings = [
            "/products", "/pricing", "/support", "/contact", "/terms", "/about",
            "/blog", "/events", "/press", "/jobs", "/partners"
        ]
        if any(s in path for s in disallow_substrings):
            return False

        return any(path.startswith(prefix) for prefix in ALLOW_PATH_PREFIXES)
    except Exception:
        return False


def safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    base = (parsed.netloc + parsed.path).strip("/")
    if not base:
        base = "index"
    if parsed.query:
        base += "_" + re.sub(r"[^a-zA-Z0-9_=-]", "_", parsed.query)
    base = re.sub(r'[/\\?%*:|"<>]', "_", base).strip("_")
    if not base:
        base = "page"
    return base + ".txt"


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


# ========= 드라이버/레이아웃 주입 =========
def create_driver(headless=True) -> webdriver.Chrome:
    chrome_options = Options()
    # if headless:
    #     chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")

    # 큰 창 + 최대화
    chrome_options.add_argument("--window-size=3840,4000")
    chrome_options.add_argument("--start-maximized")

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        driver.set_window_rect(width=3840, height=4000)
        driver.maximize_window()
    except Exception:
        pass
    return driver


def inject_layout_override(driver):
    """
    DevSite 레이아웃을 넓게 고정하고 탭 패널을 항상 보이도록.
    """
    css = r"""
@media screen and (max-width: 99999px) {
  body[layout=docs] .devsite-main-content[has-book-nav],
  body[layout=docs] .devsite-main-content[has-book-nav][has-sidebar] {
    grid-template-columns: 269px 1fr 0 !important;
  }
  devsite-snackbar, devsite-toast { display: none !important; }
  main.devsite-main-content, .devsite-article { max-width: 99999px !important; }
}
section[role='tabpanel'] { display: block !important; max-height: none !important; overflow: visible !important; }
"""
    js = """
(function(){
  var style = document.createElement('style');
  style.type = 'text/css';
  style.appendChild(document.createTextNode(arguments[0]));
  document.head.appendChild(style);
  try { window.dispatchEvent(new Event('resize')); } catch(e) {}
})();
"""
    try:
        driver.execute_script(js, css)
        time.sleep(0.1)
    except Exception:
        pass


# ========= 표를 마크다운으로 변환 =========
def table_to_markdown(table_element):
    try:
        rows = table_element.find_elements(By.TAG_NAME, "tr")
        if not rows:
            return ""
        markdown_rows = []
        for i, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue
            cell_texts = []
            for cell in cells:
                text = (cell.text or "").strip().replace('\n', ' ').replace('|', '\\|')
                cell_texts.append(text)
            markdown_rows.append("| " + " | ".join(cell_texts) + " |")
            if i == 0:
                separator = "| " + " | ".join(["---"] * len(cell_texts)) + " |"
                markdown_rows.append(separator)
        return "\n".join(markdown_rows)
    except Exception as e:
        print(f"표 변환 오류: {e}")
        return ""


def convert_tables_to_markdown(driver, article):
    try:
        tables = article.find_elements(By.TAG_NAME, "table")
        for table in tables:
            try:
                markdown_table = table_to_markdown(table)
                if markdown_table:
                    driver.execute_script("""
                        var table = arguments[0];
                        var markdownText = arguments[1];
                        var pre = document.createElement('pre');
                        pre.textContent = markdownText;
                        pre.style.backgroundColor = '#f8f9fa';
                        pre.style.padding = '10px';
                        pre.style.border = '1px solid #e1e4e8';
                        pre.style.borderRadius = '6px';
                        pre.style.fontFamily = 'monospace';
                        pre.setAttribute('data-markdown-table', 'true');
                        table.parentNode.replaceChild(pre, table);
                    """, table, markdown_table)
            except StaleElementReferenceException:
                continue
            except Exception as e:
                print(f"개별 표 변환 실패: {e}")
                continue
    except Exception as e:
        print(f"표 변환 과정에서 오류: {e}")


# ========= 링크에 URL 주석 추가 =========
def annotate_links_in_article(driver, article):
    try:
        a_tags = article.find_elements(By.TAG_NAME, "a")
        for a in a_tags:
            href = a.get_attribute("href")
            if href and "javascript:void(0)" not in href:
                try:
                    driver.execute_script(
                        "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                        a
                    )
                except StaleElementReferenceException:
                    continue
    except Exception:
        pass


# ========= 텍스트 클린업 =========
def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    lines = text.split('\n')
    cleaned_lines = []

    skip_block = False
    css_js_patterns = [
        r'^\s*/\*.*\*/',
        r'^\s*@media\s+screen',
        r'^\s*\.\w+[\w\-]*\s*\{',
        r'^\s*#\w+[\w\-]*\s*\{',
        r'^\s*[a-zA-Z\-]+\s*:\s*[^;]+;',
        r'^\s*\}',
        r'^\s*function\s*\(',
        r'^\s*var\s+\w+',
        r'^\s*const\s+\w+',
        r'^\s*let\s+\w+',
        r'^\s*\(\s*function',
        r'^\s*document\.',
        r'^\s*window\.',
        r'^\s*console\.',
        r'^\s*["\']use strict["\']',
        r'^\s*\/\/.*',
        r'^\s*\/\*.*\*\/',
    ]

    for line in lines:
        line = line.strip()
        if not line:
            if not skip_block:
                cleaned_lines.append('')
            continue

        if any(re.match(pattern, line, re.IGNORECASE) for pattern in css_js_patterns):
            skip_block = True
            continue

        if skip_block:
            if (
                line == '}' or
                line.endswith('});') or
                (line.endswith(';') and not line.startswith(('color:', 'background:', 'font:', 'margin:', 'padding:'))) or
                (re.match(r'^\s*[a-zA-Z]', line) and ':' not in line and '{' not in line)
            ):
                skip_block = False
                if re.match(r'^[A-Z].*[a-z]', line) and len(line) > 10:
                    cleaned_lines.append(line)
                continue
            else:
                continue

        skip_patterns = [
            r'^Source URL:',
            r'^Title:',
            r'^\s*\*\s*$',
            r'^\s*•\s*$',
            r'^\.devsite-',
            r'^@media',
            r'^\s*\{',
            r'^\s*\}',
            r'^\s*\)\s*;?\s*$',
        ]
        if any(re.match(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        cleaned_lines.append(line)

    result_lines = []
    prev_empty = False
    for line in cleaned_lines:
        if not line.strip():
            if not prev_empty:
                result_lines.append('')
            prev_empty = True
        else:
            result_lines.append(line)
            prev_empty = False

    return '\n'.join(result_lines).strip()


# ========= 핵심: fragment에서 언어명만 추출 (+ c → c# 보정) =========
def derive_lang_from_link(link: str, fallback_name: str) -> str:
    """
    링크 fragment(#...)에서 '_' 앞까지만 언어명으로 사용. (없으면 전체 fragment)
    fragment 없으면 마지막 path segment.
    'c' 단독은 'c#'으로 보정.
    """
    try:
        if not link:
            return (fallback_name or "").strip() or "코드"
        pu = urlparse(link)
        slug = pu.fragment.strip() if pu.fragment else pu.path.split("/")[-1].strip()
        slug = unquote(slug or "").strip()

        # '#go_4' → 'go' / '#ios+_2' → 'ios+' / '#c' → 'c'
        if "_" in slug:
            slug = slug.split("_", 1)[0]

        # 보정: '#c' 또는 '#c_4' → 'c#'
        if slug.lower() == "c":
            slug = "c#"

        return slug or ((fallback_name or "").strip() or "코드")
    except Exception:
        return (fallback_name or "").strip() or "코드"


# ========= devsite 탭 처리 (링크 fragment 기반 라벨/헤더) =========
def extract_full_tab_text(driver, article) -> str:
    final_text = ""

    # 탭 그룹을 플레이스홀더로 치환한 기본 텍스트
    try:
        article_clone = driver.execute_script("""
            var article = arguments[0];
            var clone = article.cloneNode(true);
            var rm = [
                'style','script','noscript','.devsite-code-buttons','.devsite-code-buttons-container',
                '.devsite-banner','.devsite-snackbar','.devsite-toast','devsite-snackbar','devsite-toast',
                '.devsite-rating','.devsite-article-meta','.devsite-page-rating'
            ];
            rm.forEach(function(sel){ clone.querySelectorAll(sel).forEach(function(el){el.remove();}); });
            var groups = clone.querySelectorAll('devsite-selector');
            groups.forEach(function(group, idx){
                var ph = document.createElement('div');
                ph.textContent = '[TAB_GROUP_PLACEHOLDER_' + idx + ']';
                group.parentNode.replaceChild(ph, group);
            });
            return clone.textContent || '';
        """, article)
        final_text = article_clone
    except Exception:
        final_text = article.text

    # 실제 탭 그룹 처리
    try:
        tab_groups = article.find_elements(By.TAG_NAME, "devsite-selector")
        for group_index, group in enumerate(tab_groups):
            tab_texts = []

            btns = group.find_elements(
                By.CSS_SELECTOR,
                "devsite-tabs [role='tab']:not(.devsite-overflow-tab), "
                "devsite-tabs .devsite-tabs-overflow-menu [role='tab']"
            )
            current_page = driver.current_url.split("#")[0]

            def _index_panels():
                panels = group.find_elements(By.CSS_SELECTOR, "section[role='tabpanel']")
                return (
                    { (p.get_attribute("id") or "").strip(): p for p in panels },
                    { (p.get_attribute("data-tab") or "").strip(): p for p in panels },
                    { (p.get_attribute("aria-labelledby") or "").strip(): p for p in panels },
                )

            panels_by_id, panels_by_datatab, panels_by_label = _index_panels()

            for btn in btns:
                try:
                    tab_id = (btn.get_attribute("id") or "").strip()
                    data_tab = (btn.get_attribute("data-tab") or "").strip()
                    aria_controls = (btn.get_attribute("aria-controls") or "").strip()

                    # 버튼에서 fragment 포함 href 강제 추출
                    href = driver.execute_script("""
                        (function(btn, currentPage){
                          function abs(u){ try{ return new URL(u, location.href).href; } catch(e){ return u; } }
                          // 1) 버튼 내부 링크
                          let a = btn.querySelector('a[href*="#"]');
                          if (a && a.getAttribute('href')) return abs(a.getAttribute('href'));
                          // 2) aria-controls → 패널 id를 fragment로 사용
                          const ac = btn.getAttribute('aria-controls') || '';
                          if (ac) return abs('#' + ac);
                          // 3) data-tab / id 로 대체 fragment
                          const dt = btn.getAttribute('data-tab') || '';
                          if (dt) return abs('#' + dt);
                          const bid = btn.getAttribute('id') || '';
                          if (bid) return abs('#' + bid);
                          // 4) 최후: 현재 페이지
                          return currentPage;
                        })(arguments[0], arguments[1]);
                    """, btn, current_page)

                    # 언어 라벨은 fragment에서 '_' 앞까지만 + c → c#
                    name = derive_lang_from_link(href, (btn.text or "").strip() or "UNNAMED")

                    # 패널 찾기
                    panel = None
                    if aria_controls and aria_controls in panels_by_id:
                        panel = panels_by_id[aria_controls]
                    if panel is None and data_tab and data_tab in panels_by_datatab:
                        panel = panels_by_datatab[data_tab]
                    if panel is None and tab_id and tab_id in panels_by_label:
                        panel = panels_by_label[tab_id]

                    if panel is None:
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.25)
                        panels_by_id, panels_by_datatab, panels_by_label = _index_panels()
                        if aria_controls and aria_controls in panels_by_id:
                            panel = panels_by_id[aria_controls]
                        if panel is None and data_tab and data_tab in panels_by_datatab:
                            panel = panels_by_datatab[data_tab]
                        if panel is None and tab_id and tab_id in panels_by_label:
                            panel = panels_by_label[tab_id]

                    if panel is None:
                        continue

                    # 코드 + 본문 추출 (코드블록은 언어 라벨을 앞에 붙여 다중 블록 분리)
                    labeled_blocks = []
                    full_panel_text = (panel.get_attribute("textContent") or "").strip()
                    try:
                        code_blocks = panel.find_elements(By.CSS_SELECTOR, "pre.devsite-code-highlight, pre code, .highlight pre")
                        for ci, cb in enumerate(code_blocks, 1):
                            raw = (cb.get_attribute("textContent") or "").strip()
                            if not raw:
                                continue
                            label = f"언어: {name} · 셀#{ci}"
                            labeled_blocks.append(f"{label}\n```\n{raw}\n```")
                    except NoSuchElementException:
                        pass

                    if labeled_blocks:
                        # 코드 원문을 느슨히 제거하고 라벨된 블록 추가
                        other_text = full_panel_text
                        for block in labeled_blocks:
                            body = block.split("```", 1)[-1].rstrip("`").strip()
                            if body:
                                other_text = other_text.replace(body, "")
                        other_text = other_text.strip()
                        panel_text = other_text + ("\n\n" if other_text else "") + "\n\n".join(labeled_blocks)
                    else:
                        panel_text = full_panel_text

                    if panel_text.strip():
                        header = f"--- 탭: {name} [{href}] ---"
                        tab_texts.append(f"{header}\n{panel_text}")

                except Exception as e:
                    print(f"탭 처리 중 오류: {e}")
                    continue

            if tab_texts:
                formatted = "\n\n".join(tab_texts)
                placeholder = f"[TAB_GROUP_PLACEHOLDER_{group_index}]"
                if placeholder in final_text:
                    final_text = final_text.replace(placeholder, formatted)
                else:
                    final_text += f"\n\n=== 탭 그룹 {group_index + 1} ===\n" + formatted

    except Exception as e:
        print(f"탭 추출 중 오류: {e}")

    return final_text


def extract_title_h1(driver) -> str:
    try:
        h1 = driver.find_element(By.TAG_NAME, "h1")
        text = (h1.text or "").strip()
        if text:
            return text
    except Exception:
        pass
    try:
        title = driver.title or ""
        return title.strip()
    except Exception:
        return ""


# ========= 수집 유틸 =========
def collect_sidebar_links(driver, wait) -> list:
    links = []
    try:
        nav = wait.until(EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav")))
        a_tags = nav.find_elements(By.TAG_NAME, "a")
        for a in a_tags:
            href = a.get_attribute("href")
            if href:
                links.append(href)
    except TimeoutException:
        pass
    except Exception:
        pass
    return links


def collect_article_links(driver) -> list:
    links = []
    try:
        article = driver.find_element(By.TAG_NAME, "article")
        a_tags = article.find_elements(By.TAG_NAME, "a")
        for a in a_tags:
            href = a.get_attribute("href")
            if href:
                links.append(href)
    except Exception:
        pass
    return links


# ========= 메인 크롤러 =========
def crawl():
    ensure_output_dir()
    driver = create_driver(headless=True)
    wait = WebDriverWait(driver, WAIT_SEC)

    q = deque()
    seen = set()

    for s in START_URLS:
        u = normalize_url(s)
        if is_allowed(u):
            q.append(u)
            seen.add(u)

    pages_done = 0

    try:
        while q and pages_done < MAX_PAGES:
            url = q.popleft()
            print(f"\n[{pages_done+1}/{MAX_PAGES}] GET {url}")

            try:
                driver.get(url)
            except WebDriverException as e:
                print(f"로드 실패: {e}")
                continue

            inject_layout_override(driver)

            try:
                article = wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
            except TimeoutException:
                print("article 태그를 찾지 못해 스킵")
                continue

            convert_tables_to_markdown(driver, article)
            annotate_links_in_article(driver, article)

            page_text = extract_full_tab_text(driver, article)
            page_text = clean_extracted_text(page_text)

            title = extract_title_h1(driver)

            filename = safe_filename_from_url(url)
            filepath = os.path.join(OUTPUT_DIR, filename)
            payload = f"Source URL: {url}\n"
            if title:
                payload += f"Title: {title}\n"
            payload += "\n" + page_text

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(payload)
            print(f"✅ Saved: {filepath}")

            pages_done += 1
            time.sleep(CRAWL_DELAY_SEC)

            # 내부 링크 확장
            new_links = []
            try:
                new_links.extend(collect_sidebar_links(driver, wait))
            except Exception:
                pass
            try:
                new_links.extend(collect_article_links(driver))
            except Exception:
                pass

            for raw in new_links:
                abs_url = raw
                if raw.startswith("/"):
                    abs_url = urljoin(f"{urlparse(url).scheme}://{urlparse(url).netloc}", raw)
                norm = normalize_url(abs_url)
                if norm and is_allowed(norm) and norm not in seen:
                    seen.add(norm)
                    q.append(norm)

        print(f"\n크롤 완료 — 저장한 페이지 수: {pages_done}, 남은 대기열: {len(q)}")

    except KeyboardInterrupt:
        print("\n⛔️ 사용자가 크롤을 중단했습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류로 크롤을 종료합니다: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    crawl()
