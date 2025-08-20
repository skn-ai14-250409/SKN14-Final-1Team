import os
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode

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
)

# ===================== 설정 =====================
BASE_URL = "https://developers.google.com"
START_URLS = [
    "/people/api/rest?hl=ko",
    "/people?hl=ko",
    "/people/support?hl=ko",
]
OUTPUT_DIR = "people_docs_crawled"
WAIT_SECONDS = 25
REQUEST_DELAY = 0.8
HEADLESS = True
# ===============================================

def ensure_hl_ko(url: str) -> str:
    """모든 URL이 ?hl=ko 파라미터를 유지하도록 강제."""
    try:
        p = urlparse(url)
        q = parse_qs(p.query)
        q["hl"] = ["ko"]
        new_q = urlencode({k: v[0] if isinstance(v, list) else v for k, v in q.items()})
        return urlunparse(p._replace(query=new_q))
    except Exception:
        return url

def is_people_url(url: str) -> bool:
    """People 문서만 포함."""
    return url.startswith("https://developers.google.com/people")

def sanitize_filename(path: str) -> str:
    return re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"

def save_text(filepath: str, content: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def expand_all_nav_sections(driver, container):
    """사이드바에 토글이 있으면 가능한 한 모두 펼침(없어도 무해)."""
    # aria-expanded가 있는 버튼/요소 클릭
    toggles = container.find_elements(By.CSS_SELECTOR, "[aria-expanded]")
    changed = True
    tries = 0
    while changed and tries < 4:
        changed = False
        tries += 1
        for t in toggles:
            try:
                expanded = (t.get_attribute("aria-expanded") or "").lower()
                if expanded in ("false", "0"):
                    driver.execute_script("arguments[0].click();", t)
                    changed = True
                    time.sleep(0.05)
            except Exception:
                pass

def collect_sidebar_links(driver, wait) -> list:
    """좌측 devsite-book-nav의 모든 링크 수집(숨김 포함)."""
    links = []
    try:
        nav = wait.until(EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav")))
        # 토글이 있다면 펼쳐서 DOM에 더 많아질 가능성에 대비
        expand_all_nav_sections(driver, nav)
        anchors = nav.find_elements(By.TAG_NAME, "a")
        for a in anchors:
            href = a.get_attribute("href")
            if href:
                links.append(href)
    except TimeoutException:
        # 어떤 페이지는 사이드바가 없을 수 있음
        pass
    return links

def modify_links_in_article(driver, article_element):
    """<article> 내부 모든 <a> 텍스트 뒤에 [href] 추가."""
    try:
        links = article_element.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and "javascript:void(0)" not in href:
                driver.execute_script(
                    "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                    link,
                )
    except StaleElementReferenceException:
        print("링크 수정 중 DOM 변경으로 일부 링크를 처리하지 못했습니다.")
    except Exception as e:
        print(f"링크 처리 중 예외: {e}")

def expand_tabs_and_collect_text(article_element) -> str:
    """devsite-selector 탭 콘텐츠를 펼쳐 최종 텍스트에 반영."""
    final_page_text = article_element.text
    tab_groups = article_element.find_elements(By.TAG_NAME, "devsite-selector")

    for tab_group in tab_groups:
        tab_texts = []

        tab_buttons = tab_group.find_elements(
            By.CSS_SELECTOR, "devsite-tabs tab:not(.devsite-overflow-tab)"
        )

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

        tab_panels = tab_group.find_elements(By.CSS_SELECTOR, "section[role='tabpanel']")
        panels_by_key = {}
        for p in tab_panels:
            key = p.get_attribute("data-tab")
            if not key:
                labelledby = p.get_attribute("aria-labelledby") or ""
                if labelledby.startswith("aria-tab-"):
                    key = labelledby.replace("aria-tab-", "")
            if key:
                panels_by_key[key] = p

        for btn in tab_buttons:
            tab_key = btn.get_attribute("data-tab") or btn.get_attribute("id") or ""
            tab_name = _name_for(btn)

            panel_text = ""
            panel = panels_by_key.get(tab_key)

            if panel is None:
                try:
                    btn.click()
                    time.sleep(0.1)
                    panel = tab_group.find_element(
                        By.CSS_SELECTOR, f"section[role='tabpanel'][data-tab='{tab_key}']"
                    )
                except Exception:
                    panel = None

            if panel is not None:
                try:
                    code_block = panel.find_element(By.CSS_SELECTOR, "pre.devsite-code-highlight")
                    panel_text = code_block.get_attribute("textContent").strip()
                except NoSuchElementException:
                    panel_text = (panel.get_attribute("textContent") or "").strip()
            else:
                panel_text = "(해당 탭의 패널을 찾을 수 없음)"

            tab_texts.append(f"--- 탭: {tab_name} ---\n{panel_text}")

        formatted = "\n\n".join(tab_texts)
        if tab_group.text and formatted:
            final_page_text = final_page_text.replace(tab_group.text, formatted, 1)

    return final_page_text

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,2400")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36")

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, WAIT_SECONDS)

    try:
        # BFS: 방문하면서 매 페이지의 사이드바에서 새 링크를 계속 추가 -> 하위목록까지 전부
        to_visit = deque()
        seen = set()
        all_urls = set()

        for u in START_URLS:
            fu = ensure_hl_ko(urljoin(BASE_URL, u))
            to_visit.append(fu)
            all_urls.add(fu)

        print("사이드바 전체를 따라가며 링크를 수집합니다...")
        while to_visit:
            url = to_visit.popleft()
            if url in seen:
                continue
            seen.add(url)

            try:
                driver.get(url)
                time.sleep(0.1)
                sidebar_links = collect_sidebar_links(driver, wait)
                for href in sidebar_links:
                    abs_url = ensure_hl_ko(urljoin(BASE_URL, href))
                    if is_people_url(abs_url) and abs_url not in all_urls:
                        all_urls.add(abs_url)
                        to_visit.append(abs_url)
            except Exception as e:
                print(f"사이드바 링크 수집 중 오류: {url} - {e}")

        filtered_urls = sorted(all_urls)
        print(f"✅ 총 {len(filtered_urls)}개의 People 문서 링크를 수집했습니다.")

        # 이제 실제 본문 크롤링
        for i, url in enumerate(filtered_urls, start=1):
            try:
                print(f"\n({i}/{len(filtered_urls)}) 크롤링: {url}")
                driver.get(url)
                article = wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))

                # 링크 텍스트 뒤에 [href] 덧붙이기
                modify_links_in_article(driver, article)

                # 탭/코드블록 포함 최종 텍스트 만들기
                final_text = expand_tabs_and_collect_text(article)

                # 파일 경로 생성
                path_no_query = url.split("?")[0].replace(BASE_URL, "")
                filename = sanitize_filename(path_no_query)
                filepath = os.path.join(OUTPUT_DIR, filename)

                # 저장
                content = f"Source URL: {url}\n\n{final_text}"
                save_text(filepath, content)
                print(f"✅ 저장 완료: {filepath}")

            except TimeoutException:
                print(f"⏱️ 타임아웃: {url} - article을 찾지 못했습니다.")
            except Exception as e:
                print(f"❗ 페이지 처리 중 오류: {url} - {e}")

            time.sleep(REQUEST_DELAY)

    finally:
        driver.quit()
        print("\n크롤링 완료! 브라우저를 종료합니다.")

if __name__ == "__main__":
    main()
