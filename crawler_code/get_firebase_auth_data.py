# FILE: get_firebase_auth_data.py (데드락 문제 해결 최종본)

# -*- coding: utf-8 -*-
import os
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode, urldefrag
import multiprocessing

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

# ========= 기본 설정 (Firebase Auth 전용) =========
OUTPUT_DIR = "../GOOGLE_API_DATA/firebase_auth_crawled"
MAX_PAGES = 800
CRAWL_DELAY_SEC = 1
WAIT_SEC = 20
RESTART_DRIVER_AFTER_PAGES = 50
NUM_WORKERS = 4

# ========= 크롤 제한 =========
ALLOW_DOMAINS = {"firebase.google.com"}
ALLOW_PATH_PREFIXES = ("/docs/auth",)
START_URLS = ["https://firebase.google.com/docs/auth?hl=ko"]


# ... (이전과 동일한 모든 헬퍼 함수들: normalize_url, is_allowed, etc.) ...
def normalize_url(url: str) -> str:
    if not url: return ""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc
    qs = parse_qs(parsed.query)
    qs["hl"] = ["ko"]
    query = urlencode({k: v[-1] for k, v in qs.items()}, doseq=False)
    path = re.sub(r"//+", "/", parsed.path)
    return urlunparse((scheme, netloc, path, "", query, ""))


def is_allowed(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.netloc not in ALLOW_DOMAINS: return False
        path = parsed.path or "/"
        disallow = ["/products", "/pricing", "/support", "/contact", "/terms", "/about", "/blog", "/events", "/press",
                    "/jobs", "/partners"]
        if any(s in path for s in disallow): return False
        return any(path.startswith(prefix) for prefix in ALLOW_PATH_PREFIXES)
    except Exception:
        return False


def safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    base = (parsed.netloc + parsed.path).strip("/") or "index"
    if parsed.query: base += "_" + re.sub(r"[^a-zA-Z0-9_=-]", "_", parsed.query)
    base = re.sub(r'[/\\?%*:|"<>]', "_", base).strip("_") or "page"
    return base + ".txt"


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)


def create_driver(headless=True) -> webdriver.Chrome:
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    service = ChromeService()
    return webdriver.Chrome(service=service, options=chrome_options)


def inject_layout_override(driver):
    css = r"""
    @media screen and (max-width: 99999px) {
      body[layout=docs] .devsite-main-content[has-book-nav],
      body[layout=docs] .devsite-main-content[has-book-nav][has-sidebar] { grid-template-columns: 269px 1fr 0 !important; }
      devsite-snackbar, devsite-toast, .devsite-overflow-tab { display: none !important; }
      main.devsite-main-content, .devsite-article { max-width: 99999px !important; }
    }
    section[role='tabpanel'] { display: block !important; max-height: none !important; overflow: visible !important; }
    """
    try:
        driver.execute_script(
            "var style=document.createElement('style');style.type='text/css';style.appendChild(document.createTextNode(arguments[0]));document.head.appendChild(style);",
            css)
    except Exception:
        pass


def table_to_markdown(table_element):
    try:
        rows = table_element.find_elements(By.TAG_NAME, "tr")
        markdown_rows = []
        for i, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "th") + row.find_elements(By.TAG_NAME, "td")
            if not cells: continue
            cell_texts = [(cell.text or "").strip().replace('\n', ' ').replace('|', '\\|') for cell in cells]
            markdown_rows.append("| " + " | ".join(cell_texts) + " |")
            if i == 0: markdown_rows.append("| " + " | ".join(["---"] * len(cell_texts)) + " |")
        return "\n".join(markdown_rows)
    except Exception:
        return ""


def convert_tables_to_markdown(driver, article):
    try:
        tables = article.find_elements(By.TAG_NAME, "table")
        for table in tables:
            try:
                markdown_table = table_to_markdown(table)
                if markdown_table: driver.execute_script(
                    "var table=arguments[0];var pre=document.createElement('pre');pre.textContent=arguments[1];table.parentNode.replaceChild(pre,table);",
                    table, markdown_table)
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
                        "arguments[0].textContent=arguments[0].textContent.trim()+' ['+arguments[0].href+']';", a)
                except StaleElementReferenceException:
                    continue
    except Exception:
        pass


def clean_extracted_text(text: str) -> str:
    if not text: return ""
    lines = [line.strip() for line in text.split('\n')]
    compacted, prev_empty = [], True
    for line in lines:
        if line:
            compacted.append(line)
            prev_empty = False
        elif not prev_empty:
            compacted.append(line)
            prev_empty = True
    return '\n'.join(compacted).strip()


def extract_content_with_tabs(driver, article) -> str:
    script = """
        var article = arguments[0].cloneNode(true);
        ['style','script','noscript','.devsite-code-buttons','.devsite-rating','.devsite-article-meta'].forEach(sel=>article.querySelectorAll(sel).forEach(el=>el.remove()));
        article.querySelectorAll('devsite-selector').forEach((g,i)=>{var p=document.createElement('div');p.textContent=`__TAB_GROUP_${i}__`;g.parentNode.replaceChild(p,g);});
        return article.textContent||'';
    """
    final_text = driver.execute_script(script, article)
    try:
        for i, group in enumerate(article.find_elements(By.TAG_NAME, "devsite-selector")):
            content = []
            tabs = group.find_elements(By.CSS_SELECTOR, "[role='tab']")
            panels = group.find_elements(By.CSS_SELECTOR, "[role='tabpanel']")
            panel_map = {p.get_attribute('id'): p for p in panels if p.get_attribute('id')}
            for tab in tabs:
                tab_text = (tab.text or "").strip()
                if not tab_text or tab_text == "더보기": continue
                panel = panel_map.get(tab.get_attribute('aria-controls'))
                if panel:
                    panel_content = "\n".join([f"```\n{(b.text or '').strip()}\n```" for b in
                                               panel.find_elements(By.CSS_SELECTOR,
                                                                   "pre.devsite-code-highlight, pre code") if
                                               (b.text or '').strip()]) or (panel.text or "").strip()
                    if panel_content: content.append(f"--- 탭: {tab_text} ---\n{panel_content}")
            if content: final_text = final_text.replace(f"__TAB_GROUP_{i}__", "\n\n" + "\n\n".join(content))
    except Exception as e:
        print(f"탭 추출 오류: {e}")
    return re.sub(r'__TAB_GROUP_\d+__', '', final_text)


def extract_title_h1(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "h1").text.strip()
    except Exception:
        return (driver.title or "").strip()


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


def crawl_worker(pid, url_queue, seen_urls, pages_done_counter, counter_lock):
    driver = create_driver(headless=True)
    wait = WebDriverWait(driver, WAIT_SEC)
    pages_crawled_by_worker = 0

    while True:
        try:
            url = url_queue.get()
            if url is None:
                break

            with counter_lock:
                if pages_done_counter.value >= MAX_PAGES:
                    break  # MAX_PAGES에 도달하면 루프 탈출
                pages_done_counter.value += 1
                current_page_count = pages_done_counter.value

            print(f"[Worker-{pid} | Page-{current_page_count}/{MAX_PAGES}] GET {url}")

            driver.get(url)
            inject_layout_override(driver)
            article = wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))

            convert_tables_to_markdown(driver, article)
            annotate_links_in_article(driver, article)
            page_text = extract_content_with_tabs(driver, article)
            page_text = clean_extracted_text(page_text)
            title = extract_title_h1(driver)

            filepath = os.path.join(OUTPUT_DIR, safe_filename_from_url(url))
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Source URL: {url}\nTitle: {title}\n\n{page_text}")

            pages_crawled_by_worker += 1
            if pages_crawled_by_worker % RESTART_DRIVER_AFTER_PAGES == 0:
                print(f"[Worker-{pid}] 드라이버 재시작...")
                driver.quit()
                driver = create_driver(headless=True)
                wait = WebDriverWait(driver, WAIT_SEC)

            time.sleep(CRAWL_DELAY_SEC)

            new_links = collect_sidebar_links(driver, wait) + collect_article_links(driver)
            for link in new_links:
                norm_url = normalize_url(urljoin(url, link))
                if norm_url and is_allowed(norm_url) and norm_url not in seen_urls:
                    seen_urls[norm_url] = True
                    url_queue.put(norm_url)
        except WebDriverException as e:
            print(f"[Worker-{pid}] 드라이버 오류 발생: {e}. 재시작합니다.")
            driver.quit();
            driver = create_driver(headless=True);
            wait = WebDriverWait(driver, WAIT_SEC)
            url_queue.put(url)
        except Exception as e:
            print(f"[Worker-{pid}] URL {url} 처리 중 오류: {e}")
            continue
        finally:
            # --- ▼▼▼ 여기가 수정된 부분입니다 (1/2) ▼▼▼ ---
            # 작업이 성공하든 실패하든, 큐에 작업이 끝났다고 알려줌
            url_queue.task_done()
            # --- ▲▲▲ 여기가 수정된 부분입니다 (1/2) ▲▲▲ ---

    driver.quit()


def crawl():
    ensure_output_dir()

    # multiprocessing.Manager 대신 JoinableQueue 사용
    manager = multiprocessing.Manager()
    url_queue = multiprocessing.JoinableQueue()
    seen_urls = manager.dict()
    pages_done_counter = manager.Value('i', 0)
    counter_lock = manager.Lock()

    for url in START_URLS:
        norm_url = normalize_url(url)
        if is_allowed(norm_url) and norm_url not in seen_urls:
            url_queue.put(norm_url)
            seen_urls[norm_url] = True

    processes = []
    for i in range(NUM_WORKERS):
        p = multiprocessing.Process(target=crawl_worker,
                                    args=(i + 1, url_queue, seen_urls, pages_done_counter, counter_lock))
        p.start()
        processes.append(p)

    # --- ▼▼▼ 여기가 수정된 부분입니다 (2/2) ▼▼▼ ---
    # 큐의 모든 작업이 task_done()으로 처리될 때까지 기다림
    url_queue.join()

    # 모든 작업이 끝났으므로, 워커들에게 종료 신호(None)를 보냄
    for _ in range(NUM_WORKERS):
        url_queue.put(None)
    # --- ▲▲▲ 여기가 수정된 부분입니다 (2/2) ▲▲▲ ---

    for p in processes:
        p.join()

    print(f"\n크롤 완료 — 저장한 페이지 수: {pages_done_counter.value}")


if __name__ == "__main__":
    crawl()