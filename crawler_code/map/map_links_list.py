# 1차. 링크 먼저 수집
import os, time
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

ROOT_URL = "https://developers.google.com/maps?hl=ko"
BASE = "https://developers.google.com"

OUT_DIR = "map_discovery"
os.makedirs(OUT_DIR, exist_ok=True)
OUT_SECTIONS = os.path.join(OUT_DIR, "_sections.txt")
OUT_SIDEBAR  = os.path.join(OUT_DIR, "_sidebar_links.txt")

def create_driver(headless=True):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=ko-KR")
    driver = webdriver.Chrome(service=ChromeService(), options=opts)
    try:
        driver.set_window_size(1366, 900)  # 화면 크기 고정 (모바일/책 메뉴 접힘 방지)
    except Exception:
        pass
    return driver

def abs_url(u: str) -> str:
    if not u:
        return ""
    try:
        return urljoin(BASE, u)
    except Exception:
        return u

def wait_for_article(driver, sec=20):
    return WebDriverWait(driver, sec).until(
        EC.presence_of_element_located((By.TAG_NAME, "article"))
    )

# === 접힌 메뉴 전부 펼치기 ===
def expand_all_expandables(root, driver, max_rounds=4, pause=0.06):
    for _ in range(max_rounds):
        toggles = root.find_elements(By.CSS_SELECTOR, ".devsite-expandable-nav .devsite-nav-toggle")
        if not toggles:
            break
        changed = False
        for t in toggles:
            try:
                driver.execute_script("arguments[0].click();", t)
                time.sleep(pause)
                changed = True
            except Exception:
                continue
        if not changed:
            break

# === 사이드바 링크 수집 ===
def sidebar_links(driver, sec=12):
    wait = WebDriverWait(driver, sec)
    try:
        nav = wait.until(EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav")))
    except TimeoutException:
        return []
    try:
        expand_all_expandables(nav, driver)
    except Exception:
        pass
    links = []
    for a in nav.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = a.get_attribute("href")
        if href:
            links.append(abs_url(href))
    return links

# === 책/모바일 메뉴 링크 수집 ===
def book_menu_links(driver):
    got = []
    for sel in [".devsite-mobile-nav-bottom", 'ul[menu="_book"]', "devsite-book-nav"]:
        try:
            root = driver.find_element(By.CSS_SELECTOR, sel) if sel != "devsite-book-nav" else driver.find_element(By.TAG_NAME, sel)
            expand_all_expandables(root, driver)  
            for a in root.find_elements(By.CSS_SELECTOR, "a[href]"):
                href = a.get_attribute("href")
                if href:
                    absu = abs_url(href)
                    # print(f"[book_menu_links] found: {absu}")  
                    got.append(absu)
        except NoSuchElementException:
            continue

    # /maps 링크만 유지
    return [u for u in got if urlparse(u).netloc == "developers.google.com" and "/maps" in urlparse(u).path]

def current_sidebar_sig(driver):
    try:
        nav = driver.find_element(By.TAG_NAME, "devsite-book-nav")
        return hash(nav.get_attribute("innerHTML"))
    except Exception:
        return None

# === 탭 순회하며 수집 ===
def click_lower_tabs_and_collect(driver):
    """상단 탭 순회 → 사이드바 + 책/모바일 메뉴 모두 수집"""
    collected = []
    try:
        tabs_root = driver.find_element(By.CSS_SELECTOR, "devsite-tabs.lower-tabs, devsite-tabs[class*='lower-tabs']")
    except NoSuchElementException:
        collected.extend(sidebar_links(driver))
        collected.extend(book_menu_links(driver))
        return collected

    def list_tabs():
        tabs = tabs_root.find_elements(By.CSS_SELECTOR, "nav.devsite-tabs-wrapper tab:not(.devsite-overflow-tab)")
        try:
            overflow = tabs_root.find_element(By.CSS_SELECTOR, "tab.devsite-overflow-tab")
            driver.execute_script("arguments[0].click();", overflow)
            time.sleep(0.1)
            tabs.extend(tabs_root.find_elements(By.CSS_SELECTOR, ".devsite-tabs-overflow-menu tab"))
        except NoSuchElementException:
            pass
        return tabs

    tabs = list_tabs()
    if not tabs:
        collected.extend(sidebar_links(driver))
        collected.extend(book_menu_links(driver))
        return collected

    for tab in tabs:
        try:
            sig_before = current_sidebar_sig(driver)
            driver.execute_script("arguments[0].click();", tab)
            for _ in range(40):
                sig_after = current_sidebar_sig(driver)
                if sig_after is not None and sig_after != sig_before:
                    break
                time.sleep(0.05)
            collected.extend(sidebar_links(driver))
            collected.extend(book_menu_links(driver))  # 탭별로 수집
        except StaleElementReferenceException:
            tabs = list_tabs()
        except Exception:
            continue

    collected.extend(sidebar_links(driver))
    collected.extend(book_menu_links(driver))
    return collected

def open_docs_dropdown_and_collect_section_links(driver):
    """루트에서 '문서' 드롭다운 → 섹션 링크 수집"""
    driver.get(ROOT_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    docs_btn = None
    candidates = driver.find_elements(By.CSS_SELECTOR, "button[aria-haspopup='menu'], button.devsite-tabs-dropdown-toggle")
    for b in candidates:
        label = (b.get_attribute("aria-label") or b.text or "").strip()
        if any(k in label for k in ["문서", "Docs", "documentation", "문서 메뉴"]):
            docs_btn = b
            break
    if docs_btn is None:
        try:
            docs_btn = driver.find_element(By.XPATH, "//button[contains(., '문서') or contains(., 'Docs')]")
        except NoSuchElementException:
            raise RuntimeError("상단 '문서' 버튼을 찾지 못했습니다.")

    driver.execute_script("arguments[0].click();", docs_btn)
    time.sleep(0.2)

    section_links = []
    menus = driver.find_elements(By.CSS_SELECTOR, "div[role='menu'], .devsite-tabs-dropdown-menu")
    for menu in menus:
        for a in menu.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = a.get_attribute("href")
            if href:
                absu = abs_url(href)
                if urlparse(absu).netloc == "developers.google.com" and "/maps" in urlparse(absu).path:
                    section_links.append(absu)

    section_links = list(dict.fromkeys(section_links))
    return section_links

def main():
    driver = create_driver(headless=True)
    all_sidebar = []
    try:
        # 1) 드롭다운 섹션 수집
        sections = open_docs_dropdown_and_collect_section_links(driver)
        print(f"🔎 드롭다운 섹션 {len(sections)}개 수집")
        with open(OUT_SECTIONS, "w", encoding="utf-8") as f:
            f.write("\n".join(sections))
        print(f"저장: {OUT_SECTIONS}")

        # 2) 각 섹션 페이지 → 탭 순회 → 링크 수집
        for i, url in enumerate(sections, 1):
            try:
                print(f"[{i}/{len(sections)}] open: {url}")
                driver.get(url)
                wait_for_article(driver)
                got = click_lower_tabs_and_collect(driver)
                got = [u for u in got if urlparse(u).netloc == "developers.google.com" and "/maps" in urlparse(u).path]
                print(f"  ↳ sidebar links: {len(got)}")
                all_sidebar.extend(got)
            except Exception as e:
                print(f"  ! 실패: {e}")

        ordered_unique = list(dict.fromkeys(all_sidebar))
        with open(OUT_SIDEBAR, "w", encoding="utf-8") as f:
            f.write("\n".join(ordered_unique))
        print(f"\n✅ 최종 사이드바 링크 {len(ordered_unique)}개 저장: {OUT_SIDEBAR}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
