# -*- coding: utf-8 -*-
import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode, urldefrag

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

# ========= 기본 설정 (Firebase / Firestore 전용) =========
OUTPUT_DIR = "firebase_auth_2"
MAX_PAGES = 800
CRAWL_DELAY_SEC = 1
WAIT_SEC = 20

# ========= 크롤 제한 =========
ALLOW_DOMAINS = {"firebase.google.com"}
ALLOW_PATH_PREFIXES = (
    "/docs/auth",   # firebase.google.com/docs/firestore/**
)

START_URLS = [
    "https://firebase.google.com/docs/auth?hl=ko"
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
    # 헤드리스 사용 원하면 주석 해제
    # if headless:
    #     chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")

    # 창을 매우 크게 + 최대화
    chrome_options.add_argument("--window-size=3840,4000")
    chrome_options.add_argument("--start-maximized")

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # headless에서도 set_window_rect로 최대치 근접
    try:
        driver.set_window_rect(width=3840, height=4000)
        driver.maximize_window()
    except Exception:
        pass
    return driver


def inject_layout_override(driver):
    """
    DevSite의 반응형 레이아웃에서 '더보기(overflow 탭)'가 나오지 않도록
    넓은 그리드 고정 + overflow 탭 숨김을 강제 주입한다.
    """
    css = r"""
/* 화면이 충분히 넓다고 가정하고, 북-본문-사이드의 2열(네비 + 본문) 레이아웃을 강제 */
@media screen and (max-width: 99999px) {
  body[layout=docs] .devsite-main-content[has-book-nav],
  body[layout=docs] .devsite-main-content[has-book-nav][has-sidebar] {
    grid-template-columns: 269px 1fr 0 !important;
  }
  /* 탭의 overflow(더보기) 버튼 숨김 */
  devsite-tabs .devsite-overflow-tab,
  .devsite-overflow-tab { display: none !important; }
  /* 코드/표가 잘리거나 접히는 부가 토스트/스낵바 요소 숨김 */
  devsite-snackbar, devsite-toast { display: none !important; }
  /* 내용 영역 최대폭 넓게 */
  main.devsite-main-content, .devsite-article { max-width: 99999px !important; }
}
/* 탭 영역의 가시 패널은 항상 보이도록(접힘 방지). 숨김된 상태여도 textContent 추출은 되지만, 시각적 확장 보조 */
section[role='tabpanel'] { display: block !important; max-height: none !important; overflow: visible !important; }
"""
    js = """
(function(){
  var style = document.createElement('style');
  style.type = 'text/css';
  style.appendChild(document.createTextNode(arguments[0]));
  document.head.appendChild(style);

  // 레이아웃 재계산을 유도
  try { window.dispatchEvent(new Event('resize')); } catch(e) {}
})();
"""
    try:
        driver.execute_script(js, css)
        time.sleep(0.1)  # 살짝 대기해 레이아웃 반영
    except Exception:
        pass


def expand_overflow_tabs(driver):
    """
    더보기 탭을 안전하게 펼치는 JavaScript 실행
    """
    js_expand_tabs = """
(function() {
  let isProcessing = false;
  function expandAndFixTabs() {
    if (isProcessing) return;
    isProcessing = true;
    try {
      const tabGroups = document.querySelectorAll('devsite-tabs');
      tabGroups.forEach(tabGroup => {
        if (tabGroup.dataset.expanded === 'true') return;
        const overflowMenu = tabGroup.querySelector('.devsite-tabs-overflow-menu');
        const mainTabWrapper = tabGroup.querySelector('.devsite-tabs-wrapper');
        const moreButtonTab = tabGroup.querySelector('.devsite-overflow-tab');
        if (!overflowMenu || !mainTabWrapper || !moreButtonTab) return;

        const hiddenTabs = Array.from(overflowMenu.querySelectorAll('tab'));
        if (hiddenTabs.length === 0) return;

        try {
          const moreButton = tabGroup.querySelector('.devsite-overflow-tab');
          if (moreButton) moreButton.style.display = 'none';
        } catch (e) { /* noop */ }

        hiddenTabs.forEach((originalTab, index) => {
          try {
            const tabLink = originalTab.querySelector('a');
            if (!tabLink) return;
            const tabText = tabLink.textContent || `Tab ${index + 1}`;
            const tabHref = tabLink.getAttribute('href') || '#';
            const newTab = document.createElement('tab');
            newTab.setAttribute('role', 'tab');
            newTab.className = originalTab.className;

            const newLink = document.createElement('a');
            newLink.textContent = tabText;
            newLink.href = tabHref;
            newLink.addEventListener('click', function() {
              try { originalTab.querySelector('a')?.click(); } catch (e) {}
            });

            newTab.appendChild(newLink);
            setTimeout(() => {
              try {
                const wrapperStillExists = tabGroup.querySelector('.devsite-tabs-wrapper');
                if (wrapperStillExists) wrapperStillExists.appendChild(newTab);
              } catch (e) {}
            }, index * 50);
          } catch (e) {}
        });

        tabGroup.dataset.expanded = 'true';
      });
    } catch (e) {
      /* noop */
    } finally {
      isProcessing = false;
    }
  }
  expandAndFixTabs();
  return true;
})();
"""
    try:
        driver.execute_script(js_expand_tabs)
        time.sleep(2)  # 탭 펼치기 완료 대기
    except Exception as e:
        print(f"탭 펼치기 실패: {e}")


# ========= 표를 마크다운으로 변환 =========
def table_to_markdown(table_element):
    """
    HTML table을 마크다운 테이블로 변환
    """
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
    """
    article 내의 모든 표를 마크다운으로 변환하여 교체
    """
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


def clean_extracted_text(text: str) -> str:
    """
    추출된 텍스트에서 불필요한 CSS, JavaScript, 메타데이터 등을 제거
    """
    if not text:
        return ""
    lines = text.split('\n')
    cleaned_lines = []

    skip_block = False
    css_js_patterns = [
        r'^\s*/\*.*\*/',  # CSS 주석
        r'^\s*@media\s+screen',  # CSS 미디어 쿼리
        r'^\s*\.\w+[\w\-]*\s*\{',  # CSS 클래스
        r'^\s*#\w+[\w\-]*\s*\{',  # CSS ID
        r'^\s*[a-zA-Z\-]+\s*:\s*[^;]+;',  # CSS 속성
        r'^\s*\}',  # CSS 닫기
        r'^\s*function\s*\(',  # JavaScript 함수
        r'^\s*var\s+\w+',  # JavaScript 변수
        r'^\s*const\s+\w+',  # JavaScript 상수
        r'^\s*let\s+\w+',  # JavaScript let
        r'^\s*\(\s*function',  # 즉시실행함수
        r'^\s*document\.',  # DOM 조작
        r'^\s*window\.',  # window 객체
        r'^\s*console\.',  # console 로그
        r'^\s*["\']use strict["\']',  # strict mode
        r'^\s*\/\/.*',  # JavaScript 주석
        r'^\s*\/\*.*\*\/',  # 블록 주석
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


def extract_full_tab_text(driver, article) -> str:
    """
    모든 탭의 내용을 추출하되, 중복 없이 수집하고 불필요한 스타일/스크립트 제거
    """
    final_text = ""

    # 기본 텍스트(탭 그룹 제외) 먼저 복제 후 정리
    try:
        article_clone = driver.execute_script("""
            var article = arguments[0];
            var clone = article.cloneNode(true);
            var elementsToRemove = [
                'style', 'script', 'noscript',
                '.devsite-code-buttons',
                '.devsite-code-buttons-container',
                '.devsite-banner',
                '.devsite-snackbar',
                '.devsite-toast',
                'devsite-snackbar',
                'devsite-toast',
                '.devsite-rating',
                '.devsite-article-meta',
                '.devsite-page-rating'
            ];
            elementsToRemove.forEach(function(selector) {
                var elements = clone.querySelectorAll(selector);
                elements.forEach(function(el) { if (el && el.parentNode) el.parentNode.removeChild(el); });
            });
            var tabGroups = clone.querySelectorAll('devsite-selector');
            tabGroups.forEach(function(group, idx) {
                var placeholder = document.createElement('div');
                placeholder.textContent = '[TAB_GROUP_PLACEHOLDER_' + idx + ']';
                group.parentNode.replaceChild(placeholder, group);
            });
            return clone.textContent || '';
        """, article)
        final_text = article_clone
    except Exception:
        final_text = article.text

    # 탭 그룹 개별 처리
    try:
        tab_groups = article.find_elements(By.TAG_NAME, "devsite-selector")
        for group_index, group in enumerate(tab_groups):
            tab_texts = []

            btns = group.find_elements(By.CSS_SELECTOR, "devsite-tabs tab:not(.devsite-overflow-tab)")

            def _name_for(btn):
                txt = (btn.text or "").strip()
                if txt:
                    return txt
                return (
                    btn.get_attribute("aria-controls")
                    or btn.get_attribute("id")
                    or btn.get_attribute("data-tab")
                    or "UNNAMED"
                )

            panels = group.find_elements(By.CSS_SELECTOR, "section[role='tabpanel']")
            panels_by_key = {}
            for p in panels:
                key = p.get_attribute("data-tab")
                if not key:
                    labelledby = p.get_attribute("aria-labelledby") or ""
                    if labelledby.startswith("aria-tab-"):
                        key = labelledby.replace("aria-tab-", "")
                if key:
                    panels_by_key[key] = p

            for btn in btns:
                try:
                    key = btn.get_attribute("data-tab") or btn.get_attribute("id") or ""
                    name = _name_for(btn)
                    panel_text = ""
                    panel = panels_by_key.get(key)

                    if panel is None:
                        try:
                            driver.execute_script("arguments[0].click();", btn)
                            time.sleep(0.2)
                            panel = group.find_element(
                                By.CSS_SELECTOR, f"section[role='tabpanel'][data-tab='{key}']"
                            )
                        except Exception:
                            panel = None

                    if panel is not None:
                        code_text = ""
                        try:
                            code_blocks = panel.find_elements(By.CSS_SELECTOR, "pre.devsite-code-highlight, pre code, .highlight pre")
                            if code_blocks:
                                code_texts = []
                                for code_block in code_blocks:
                                    code_content = code_block.get_attribute("textContent") or ""
                                    if code_content.strip():
                                        code_texts.append(code_content.strip())
                                code_text = "\n\n".join(code_texts)
                        except NoSuchElementException:
                            pass

                        full_panel_text = (panel.get_attribute("textContent") or "").strip()

                        if code_text.strip():
                            other_text = full_panel_text
                            if code_text in other_text:
                                other_text = other_text.replace(code_text, "").strip()
                            if other_text:
                                panel_text = f"{other_text}\n\n```\n{code_text}\n```"
                            else:
                                panel_text = f"```\n{code_text}\n```"
                        else:
                            panel_text = full_panel_text
                    else:
                        panel_text = "(해당 탭의 패널을 찾을 수 없음)"

                    if panel_text.strip():
                        tab_texts.append(f"--- 탭: {name} ---\n{panel_text}")

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

            # === 레이아웃 강제: 더보기/overflow 없이 넓은 화면 유지 ===
            inject_layout_override(driver)

            # === 더보기 탭 펼치기 ===
            expand_overflow_tabs(driver)

            try:
                article = wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
            except TimeoutException:
                print("article 태그를 찾지 못해 스킵")
                continue

            # === 표를 마크다운으로 변환 ===
            convert_tables_to_markdown(driver, article)

            # === 링크에 URL 주석 추가 ===
            annotate_links_in_article(driver, article)

            # === 탭 내용 포함한 전체 텍스트 추출 ===
            page_text = extract_full_tab_text(driver, article)

            # === 불필요한 CSS/JS 제거 ===
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

        # === while 루프 종료 후 ===
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
