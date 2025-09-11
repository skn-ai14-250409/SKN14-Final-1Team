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
OUT_SIDEBAR = os.path.join(OUT_DIR, "_sidebar_links.txt")


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
        driver.set_window_size(1366, 900)
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


def expand_all_expandables(root, driver, max_rounds=5, pause=0.05):
    for _ in range(max_rounds):
        # aria-expanded="false"인 토글만 클릭하도록 개선
        toggles = root.find_elements(By.CSS_SELECTOR,
                                     ".devsite-expandable-nav .devsite-nav-toggle[aria-expanded='false']")
        if not toggles:
            break
        for t in toggles:
            try:
                driver.execute_script("arguments[0].click();", t)
                time.sleep(pause)
            except Exception:
                continue


# === 모든 탐색 링크 수집 (통합된 함수) ===
def collect_all_nav_links(driver, sec=12):
    """
    devsite-book-nav 컨테이너를 찾아 모든 하위 메뉴를 펼치고 링크를 수집합니다.
    이 함수는 sidebar_links와 book_menu_links를 대체합니다.
    """
    links = []
    try:
        nav_container = WebDriverWait(driver, sec).until(
            EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav"))
        )
        expand_all_expandables(nav_container, driver)

        for a in nav_container.find_elements(By.CSS_SELECTOR, "a[href]"):
            href = a.get_attribute("href")
            if href:
                links.append(abs_url(href))
    except TimeoutException:
        # 페이지에 탐색 메뉴가 없을 수 있음
        pass

    # /maps 경로를 포함하는 유효한 링크만 필터링
    valid_links = [
        u for u in links
        if urlparse(u).netloc == "developers.google.com" and "/maps" in urlparse(u).path
    ]
    return list(dict.fromkeys(valid_links))  # 중복 제거 후 반환


def current_sidebar_sig(driver):
    try:
        nav = driver.find_element(By.TAG_NAME, "devsite-book-nav")
        return hash(nav.get_attribute("innerHTML"))
    except Exception:
        return None


# === 탭 순회하며 수집 ===
def click_lower_tabs_and_collect(driver):
    """상단 탭 순회 → 통합된 함수로 모든 탐색 링크 수집"""
    collected = []
    try:
        tabs_root = driver.find_element(By.CSS_SELECTOR, "devsite-tabs.lower-tabs, devsite-tabs[class*='lower-tabs']")
    except NoSuchElementException:
        return collect_all_nav_links(driver)

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
        return collect_all_nav_links(driver)

    for i in range(len(tabs)):
        try:
            current_tabs = list_tabs()  # StaleElement 방지를 위해 매번 목록을 다시 가져옴
            if i >= len(current_tabs): break
            tab = current_tabs[i]

            sig_before = current_sidebar_sig(driver)
            driver.execute_script("arguments[0].click();", tab)

            # 사이드바가 변경될 때까지 대기
            WebDriverWait(driver, 10).until(
                lambda d: current_sidebar_sig(d) is not None and current_sidebar_sig(d) != sig_before
            )
            collected.extend(collect_all_nav_links(driver))
        except (StaleElementReferenceException, TimeoutException):
            continue  # 다음 탭으로 넘어감
        except Exception:
            continue

    collected.extend(collect_all_nav_links(driver))
    return collected


def open_docs_dropdown_and_collect_section_links(driver):
    """루트에서 '문서' 드롭다운 → 섹션 링크 수집"""
    driver.get(ROOT_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    docs_btn = None
    candidates = driver.find_elements(By.CSS_SELECTOR,
                                      "button[aria-haspopup='menu'], button.devsite-tabs-dropdown-toggle")
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

    return list(dict.fromkeys(section_links))


def main():
    driver = create_driver(headless=True)
    all_links = []
    try:
        sections = open_docs_dropdown_and_collect_section_links(driver)
        print(f"🔎 드롭다운 섹션 {len(sections)}개 수집")
        with open(OUT_SECTIONS, "w", encoding="utf-8") as f:
            f.write("\n".join(sections))
        print(f"저장: {OUT_SECTIONS}")

        all_links.extend(sections)

        for i, url in enumerate(sections, 1):
            try:
                print(f"[{i}/{len(sections)}] open: {url}")
                driver.get(url)
                wait_for_article(driver)
                got = click_lower_tabs_and_collect(driver)
                print(f"  ↳ nav links: {len(got)}")
                all_links.extend(got)
            except Exception as e:
                print(f"  ! 실패: {e}")

        ordered_unique = list(dict.fromkeys(all_links))
        with open(OUT_SIDEBAR, "w", encoding="utf-8") as f:
            f.write("\n".join(ordered_unique))
        print(f"\n✅ 최종 탐색 링크 {len(ordered_unique)}개 저장: {OUT_SIDEBAR}")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()