# FILE: get_firebase_auth_data.py

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
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

# ========= 기본 설정 (Firebase / Firestore 전용) =========
OUTPUT_DIR = "firebase_auth_crawled_final"
MAX_PAGES = 800
CRAWL_DELAY_SEC = 1
WAIT_SEC = 20

# ========= 크롤 제한 =========
ALLOW_DOMAINS = {"firebase.google.com"}
ALLOW_PATH_PREFIXES = (
    "/docs/auth",
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
    # if headless:
    #     chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")
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
    css = r"""
@media screen and (max-width: 99999px) {
  body[layout=docs] .devsite-main-content[has-book-nav],
  body[layout=docs] .devsite-main-content[has-book-nav][has-sidebar] {
    grid-template-columns: 269px 1fr 0 !important;
  }
  devsite-snackbar, devsite-toast, .devsite-overflow-tab { display: none !important; }
  main.devsite-main-content, .devsite-article { max-width: 99999px !important; }
}
section[role='tabpanel'] { display: block !important; max-height: none !important; overflow: visible !important; }
"""
    js = """
    var style = document.createElement('style');
    style.type = 'text/css';
    style.appendChild(document.createTextNode(arguments[0]));
    document.head.appendChild(style);
    """
    try:
        driver.execute_script(js, css)
    except Exception:
        pass


# ========= 콘텐츠 추출 =========
def table_to_markdown(table_element):
    try:
        rows = table_element.find_elements(By.TAG_NAME, "tr")
        markdown_rows = []
        for i, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
            if not cells: continue
            cell_texts = [(cell.text or "").strip().replace('\n', ' ').replace('|', '\\|') for cell in cells]
            markdown_rows.append("| " + " | ".join(cell_texts) + " |")
            if i == 0:
                separator = "| " + " | ".join(["---"] * len(cell_texts)) + " |"
                markdown_rows.append(separator)
        return "\n".join(markdown_rows)
    except Exception:
        return ""


def convert_tables_to_markdown(driver, article):
    try:
        tables = article.find_elements(By.TAG_NAME, "table")
        for table in tables:
            try:
                markdown_table = table_to_markdown(table)
                if markdown_table:
                    driver.execute_script(
                        "var table = arguments[0]; var pre = document.createElement('pre'); pre.textContent = arguments[1]; table.parentNode.replaceChild(pre, table);",
                        table, markdown_table
                    )
            except StaleElementReferenceException:
                continue
    except Exception:
        pass


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
    if not text:
        return ""
    # 불필요한 공백 라인 정리
    lines = [line.strip() for line in text.split('\n')]
    compacted_lines = []
    prev_line_empty = True
    for line in lines:
        if line:
            compacted_lines.append(line)
            prev_line_empty = False
        elif not prev_line_empty:
            compacted_lines.append(line)
            prev_line_empty = True
    return '\n'.join(compacted_lines).strip()


def extract_content_with_tabs(driver, article) -> str:
    """
    기사와 그 안의 모든 탭 콘텐츠를 추출합니다.
    """
    # 1. 불필요한 요소 제거 및 탭 그룹 위치에 플레이스홀더 삽입
    base_text_script = """
        var article = arguments[0].cloneNode(true);
        var selectorsToRemove = ['style', 'script', 'noscript', '.devsite-code-buttons', '.devsite-rating', '.devsite-article-meta'];
        selectorsToRemove.forEach(sel => article.querySelectorAll(sel).forEach(el => el.remove()));
        article.querySelectorAll('devsite-selector').forEach((group, idx) => {
            var p = document.createElement('div');
            p.textContent = `__TAB_GROUP_PLACEHOLDER_${idx}__`;
            group.parentNode.replaceChild(p, group);
        });
        return article.textContent || '';
    """
    final_text = driver.execute_script(base_text_script, article)

    # 2. 각 탭 그룹을 순회하며 콘텐츠 추출
    try:
        tab_groups = article.find_elements(By.TAG_NAME, "devsite-selector")
        for i, group in enumerate(tab_groups):
            group_content = []

            # 탭 버튼과 패널을 모두 찾음
            tabs = group.find_elements(By.CSS_SELECTOR, "[role='tab']")
            panels = group.find_elements(By.CSS_SELECTOR, "[role='tabpanel']")

            panel_map = {p.get_attribute('id'): p for p in panels if p.get_attribute('id')}

            for tab in tabs:
                tab_text = (tab.text or "").strip()
                if not tab_text or tab_text == "더보기":
                    continue

                panel_id = tab.get_attribute('aria-controls')
                panel = panel_map.get(panel_id)

                if panel:
                    panel_content = (panel.text or "").strip()
                    if panel_content:
                        # 코드 블록을 마크다운 형식으로 감싸기
                        code_blocks = panel.find_elements(By.CSS_SELECTOR, "pre.devsite-code-highlight, pre code")
                        if code_blocks:
                            extracted_codes = []
                            for block in code_blocks:
                                code_text = (block.text or "").strip()
                                if code_text:
                                    extracted_codes.append(f"```\n{code_text}\n```")
                            panel_content = "\n".join(extracted_codes)

                        group_content.append(f"--- 탭: {tab_text} ---\n{panel_content}")

            if group_content:
                final_text = final_text.replace(f"__TAB_GROUP_PLACEHOLDER_{i}__", "\n\n" + "\n\n".join(group_content))

    except Exception as e:
        print(f"탭 추출 중 오류 발생: {e}")

    # 플레이스홀더가 남아있으면 제거
    final_text = re.sub(r'__TAB_GROUP_PLACEHOLDER_\d+__', '', final_text)
    return final_text


def extract_title_h1(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "h1").text.strip()
    except Exception:
        return (driver.title or "").strip()


# ========= 수집 유틸 =========
def collect_sidebar_links(driver, wait) -> list:
    try:
        nav = wait.until(EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav")))
        return [a.get_attribute("href") for a in nav.find_elements(By.TAG_NAME, "a") if a.get_attribute("href")]
    except Exception:
        return []


def collect_article_links(driver) -> list:
    try:
        article = driver.find_element(By.TAG_NAME, "article")
        return [a.get_attribute("href") for a in article.find_elements(By.TAG_NAME, "a") if a.get_attribute("href")]
    except Exception:
        return []


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
            print(f"\n[{pages_done + 1}/{MAX_PAGES}] GET {url}")

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

            page_text = extract_content_with_tabs(driver, article)
            page_text = clean_extracted_text(page_text)

            title = extract_title_h1(driver)

            filename = safe_filename_from_url(url)
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Source URL: {url}\n")
                if title:
                    f.write(f"Title: {title}\n")
                f.write("\n" + page_text)
            print(f"✅ Saved: {filepath}")

            pages_done += 1
            time.sleep(CRAWL_DELAY_SEC)

            new_links = collect_sidebar_links(driver, wait) + collect_article_links(driver)
            for raw_link in new_links:
                abs_url = urljoin(url, raw_link)
                norm_url = normalize_url(abs_url)
                if norm_url and is_allowed(norm_url) and norm_url not in seen:
                    seen.add(norm_url)
                    q.append(norm_url)

        print(f"\n크롤 완료 — 저장한 페이지 수: {pages_done}")
    except KeyboardInterrupt:
        print("\n⛔️ 사용자가 크롤을 중단했습니다.")
    except Exception as e:
        print(f"\n예상치 못한 오류로 크롤을 종료합니다: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    crawl()