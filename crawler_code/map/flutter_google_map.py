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

# webdriver-manager 추가
from webdriver_manager.chrome import ChromeDriverManager

# ===================== 설정 =====================
BASE_URL = "https://developers.google.com"
START_URLS = [
    "/maps/flutter-package/overview?hl=ko",
]
OUTPUT_DIR = "flutter"
WAIT_SECONDS = 25
REQUEST_DELAY = 0.8
HEADLESS = False  # 디버깅을 위해 일시적으로 False로 설정
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


def is_flutter_maps_url(url: str) -> bool:
    """Flutter용 Google Maps 패키지 문서만 포함."""
    return url.startswith("https://developers.google.com/maps/flutter-package")


def sanitize_filename(path: str) -> str:
    return re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"


def save_text(filepath: str, content: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def expand_all_nav_sections(driver, container):
    """사이드바에 토글이 있으면 가능한 한 모두 펼침."""
    print("🔄 사이드바 섹션 확장 중...")
    
    # 다양한 토글 요소들을 찾아서 확장
    toggle_selectors = [
        "[aria-expanded='false']",
        ".devsite-nav-item-heading[aria-expanded='false']",
        ".devsite-nav-title[aria-expanded='false']",
        "button[aria-expanded='false']"
    ]
    
    expanded_count = 0
    max_tries = 5
    
    for attempt in range(max_tries):
        found_collapsed = False
        
        for selector in toggle_selectors:
            try:
                toggles = container.find_elements(By.CSS_SELECTOR, selector)
                for toggle in toggles:
                    try:
                        if toggle.get_attribute("aria-expanded") == "false":
                            driver.execute_script("arguments[0].click();", toggle)
                            expanded_count += 1
                            found_collapsed = True
                            time.sleep(0.1)
                    except Exception:
                        pass
            except Exception:
                pass
        
        if not found_collapsed:
            break
        
        time.sleep(0.2)
    
    print(f"✅ {expanded_count}개 섹션 확장 완료")


def collect_sidebar_links(driver, wait) -> list:
    """좌측 devsite-book-nav의 모든 링크 수집."""
    links = []
    try:
        print("🔍 사이드바 링크 수집 중...")
        nav = wait.until(EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav")))
        print("✅ 사이드바 발견: devsite-book-nav")
        
        # 토글 확장
        expand_all_nav_sections(driver, nav)
        
        # 모든 링크 수집
        anchors = nav.find_elements(By.TAG_NAME, "a")
        print(f"🔗 총 {len(anchors)}개 링크 발견")
        
        for a in anchors:
            href = a.get_attribute("href")
            if href:
                links.append(href)
                
    except TimeoutException:
        print("⚠️ 사이드바를 찾을 수 없습니다")
    except Exception as e:
        print(f"❗ 사이드바 링크 수집 중 오류: {e}")
    
    return links


def modify_links_in_article(driver, article_element):
    """<article> 내부 모든 <a> 텍스트 뒤에 [href] 추가."""
    try:
        links = article_element.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if href and "javascript:void(0)" not in href:
                driver.execute_script(
                    "arguments[0].textContent = arguments.textContent.trim() + ' [' + arguments.href + ']';",
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

    # webdriver-manager 사용
    print("✅ webdriver-manager로 ChromeDriver 설정 완료")
    
    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,2400")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36")

    # webdriver-manager 사용
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, WAIT_SECONDS)

    try:
        # 초기 URL로 이동
        start_url = ensure_hl_ko(urljoin(BASE_URL, START_URLS[0]))
        print(f"🚀 시작 페이지로 이동: {start_url}")
        
        driver.get(start_url)
        print("✅ 페이지 로드 완료")
        
        # 사이드바에서 모든 링크 수집
        sidebar_links = collect_sidebar_links(driver, wait)
        
        # Flutter용 Google Maps 패키지 관련 링크만 필터링
        all_urls = set()
        for href in sidebar_links:
            abs_url = ensure_hl_ko(urljoin(BASE_URL, href))
            if is_flutter_maps_url(abs_url):
                all_urls.add(abs_url)
        
        # 시작 URL도 추가
        all_urls.add(start_url)
        
        filtered_urls = sorted(all_urls)
        print(f"✅ 총 {len(filtered_urls)}개의 유효한 Flutter Google Maps 패키지 페이지 링크 수집 완료")
        
        # 미리보기 출력
        print("📋 수집된 링크 미리보기 (처음 10개):")
        for i, url in enumerate(filtered_urls[:10], 1):
            print(f"  {i}. {url}")
        if len(filtered_urls) > 10:
            print(f"  ... 그리고 {len(filtered_urls) - 10}개 더")
        
        print(f"🎯 총 {len(filtered_urls)}개 페이지 크롤링 시작")
        print("=" * 14)

        # 실제 크롤링
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
