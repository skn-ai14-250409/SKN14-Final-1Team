import os
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

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
    JavascriptException,
)

# ===== 설정 =====
BASE_URL = "https://developers.google.com"
START_URL = "/workspace/sheets/api/reference/rest?hl=ko"  # Sheets REST (ko)

OUTPUT_DIR = "sheets_rest_txt"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===== 셀레니움 =====
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1400,1800")
chrome_options.add_argument("--lang=ko-KR")

service = ChromeService()
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 20)

# ===== 유틸 =====
def ensure_hl_ko(u: str) -> str:
    parts = list(urlparse(u))
    q = parse_qs(parts[4], keep_blank_values=True)
    q["hl"] = ["ko"]
    parts[4] = urlencode({k: v[0] for k, v in q.items()}, doseq=True)
    return urlunparse(parts)

def normalize_url(href: str, base: str) -> str:
    return ensure_hl_ko(urljoin(base, (href or "").split("#")[0]))

def is_sheets_rest(u: str) -> bool:
    if "developers.google.com" not in u:
        return False
    p = urlparse(u).path or ""
    # 필요 시 다른 버전이 섞일 때 여기서 배제 가능 (v4 외엔 거의 없음)
    return p.startswith("/workspace/sheets/api/reference/rest/") or \
           p == "/workspace/sheets/api/reference/rest"

def safe_filename(u: str) -> str:
    path = u.split("?")[0].replace(BASE_URL, "")
    fname = re.sub(r'[/\\?%*:|\"<>]', "_", path).strip("_") or "index"
    return (fname[:180] + ".txt")

def get_shadow_root(el):
    try:
        return driver.execute_script("return arguments[0].shadowRoot", el)
    except JavascriptException:
        return None

def qsa_in_shadow(root, selector: str):
    return driver.execute_script("""
        const root = arguments[0];
        const sel = arguments[1];
        if (!root) return [];
        if (root.querySelectorAll) return Array.from(root.querySelectorAll(sel));
        const sr = root.shadowRoot || null;
        if (!sr) return [];
        return Array.from(sr.querySelectorAll(sel));
    """, root, selector)

# ===== 사이드바 링크 수집(Shadow DOM) =====
def collect_sidebar_links():
    links = []
    try:
        nav_host = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "devsite-book-nav")))
    except TimeoutException:
        return links

    def reopen_shadow():
        host = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "devsite-book-nav")))
        return get_shadow_root(host)

    shadow = get_shadow_root(nav_host)

    # 접힌 항목 펼치기
    if shadow:
        for _ in range(2):
            try:
                toggles = qsa_in_shadow(shadow, "button[aria-expanded='false']")
                if not toggles:
                    break
                for btn in toggles:
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.05)
                    except Exception:
                        pass
                shadow = reopen_shadow()  # 리렌더 후 갱신
            except StaleElementReferenceException:
                shadow = reopen_shadow()

    anchors = qsa_in_shadow(shadow, "a[href]") if shadow else nav_host.find_elements(By.CSS_SELECTOR, "a[href]")
    for a in anchors:
        try:
            href = a.get_attribute("href")
        except StaleElementReferenceException:
            shadow = reopen_shadow()
            anchors = qsa_in_shadow(shadow, "a[href]") if shadow else \
                      wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "devsite-book-nav"))).find_elements(By.CSS_SELECTOR, "a[href]")
            continue
        if href:
            u = normalize_url(href, BASE_URL)
            if is_sheets_rest(u):
                links.append(u)

    return sorted(list(dict.fromkeys(links)))

# ===== 탭 포함 본문 추출(devsite-selector: Shadow DOM) =====
def extract_page_text():
    article = wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
    final_texts = []

    # 링크 텍스트 뒤에 [href] 덧붙이기 (가독성)
    try:
        links_in_article = article.find_elements(By.TAG_NAME, "a")
        for link in links_in_article:
            href = link.get_attribute("href")
            if href and "javascript:void(0)" not in href:
                driver.execute_script(
                    "arguments[0].textContent = (arguments[0].textContent || '').trim() + ' [' + arguments[0].href + ']';",
                    link
                )
    except Exception:
        pass

    # 기본 article 텍스트
    base_text = (article.text or "").strip()
    final_texts.append(base_text)

    # 탭 그룹 처리
    tab_groups = article.find_elements(By.TAG_NAME, "devsite-selector")
    for tg in tab_groups:
        tab_block = []

        sel_shadow = get_shadow_root(tg)
        if not sel_shadow:
            t = (tg.text or "").strip()
            if t:
                tab_block.append(t)
            final_texts.append("\n\n".join(tab_block))
            continue

        tab_btn_sel = "tab a, .devsite-tabs-wrapper tab a"
        tab_buttons = qsa_in_shadow(sel_shadow, tab_btn_sel)

        tab_names = []
        for btn in tab_buttons:
            nm = btn.text or btn.get_attribute("textContent") or ""
            tab_names.append(nm.strip() or "탭")

        for idx in range(len(tab_names)):
            # 클릭 직전 재조회(리렌더 대비)
            tab_buttons = qsa_in_shadow(sel_shadow, tab_btn_sel)
            if idx >= len(tab_buttons):
                break
            btn = tab_buttons[idx]
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.35)

            panels = qsa_in_shadow(sel_shadow, "section[role='tabpanel']")
            active = ""
            for p in panels:
                cls = p.get_attribute("class") or ""
                aria = p.get_attribute("aria-hidden") or ""
                if "devsite-active" in cls or aria == "false":
                    try:
                        active = driver.execute_script("return arguments[0].textContent;", p) or ""
                        active = active.strip()
                    except Exception:
                        active = (p.text or "").strip()
                    break

            tab_block.append(f"--- 탭: {tab_names[idx]} ---\n{active}")

        if tab_block:
            final_texts.append("\n\n".join(tab_block))

    return "\n\n".join([t for t in final_texts if t])

# ===== 메인 =====
try:
    full_start_url = ensure_hl_ko(urljoin(BASE_URL, START_URL))
    driver.get(full_start_url)

    print("사이드바의 링크를 수집 중…")
    urls_to_crawl = collect_sidebar_links()
    urls_to_crawl.insert(0, full_start_url)
    urls_to_crawl = sorted(list(dict.fromkeys(urls_to_crawl)))
    print(f"총 {len(urls_to_crawl)}개의 유효한 페이지 링크를 수집했습니다.")

    for i, url in enumerate(urls_to_crawl, 1):
        try:
            print(f"\n({i}/{len(urls_to_crawl)}) 크롤링 중: {url}")
            driver.get(url)

            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
            except TimeoutException:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            final_page_text = extract_page_text()

            # 파일 저장
            path = url.split("?")[0].replace(BASE_URL, "")
            filename = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Source URL: {url}\n\n{final_page_text}")
            print(f"저장 완료: {filepath}")

        except Exception as e:
            print(f"페이지 처리 중 오류 발생: {url} - {e}")

        time.sleep(0.8)

finally:
    driver.quit()
    print("\n크롤링 완료! 브라우저를 종료합니다.")
