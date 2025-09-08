# 2차. 수집된 링크로 본문 내용 크롤링
import os
import re
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

# ================== 설정 ==================
BASE_URL = "https://developers.google.com"
INPUT_LIST = "map_discovery/_sidebar_links.txt"   # 디스커버리 1차 출력 파일
OUTPUT_DIR = "map_docs_crawled"                   # 본문 저장 폴더
HEADLESS = False                                  # 필요시 True
WAIT_SEC = 20
CRAWL_DELAY_SEC = 0.5

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ================== 드라이버 ==================
def create_driver():
    chrome_options = Options()
    if HEADLESS:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--lang=ko-KR")
    chrome_options.add_argument("--window-size=1600,2000")
    service = ChromeService()
    return webdriver.Chrome(service=service, options=chrome_options)


# ================== 유틸 ==================
def safe_filename_from_url(url: str) -> str:
    """
    원래 스타일 유지:
      - ? 뒤 제거
      - BASE_URL 제거
      - 경로를 파일명화
      - 루트면 index로 보정
    """
    path = url.split("?")[0].replace(BASE_URL, "")
    name = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_")
    if not name:
        name = "index"
    return name + ".txt"


# ================== 본문 크롤링 ==================
def crawl_page_content(driver, wait, url: str) -> str:
    """
    - <article> 대기
    - <article> 내 모든 <a>에 '[href]' 덧붙임
    - devsite-selector 탭 패널의 숨김 내용까지 포함해서 텍스트로 치환
    - 최종 텍스트 반환
    """
    driver.get(url)

    # article 대기
    try:
        article_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
    except TimeoutException:
        return ""

    # <a>에 [URL] 덧붙이기
    try:
        links_in_article = article_element.find_elements(By.TAG_NAME, "a")
        for link in links_in_article:
            href = link.get_attribute("href")
            if href and "javascript:void(0)" not in href:
                try:
                    driver.execute_script(
                        "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                        link
                    )
                except StaleElementReferenceException:
                    continue
    except Exception:
        pass

    # 기본 텍스트
    final_page_text = article_element.text

    # 탭 그룹(devsite-selector) 처리
    tab_groups = article_element.find_elements(By.TAG_NAME, "devsite-selector")
    for tab_group in tab_groups:
        tab_texts = []

        # 탭 버튼 수집
        tab_buttons = tab_group.find_elements(
            By.CSS_SELECTOR, "devsite-tabs tab:not(.devsite-overflow-tab), [role='tab']"
        )

        # 탭 패널 매핑
        panels_by_key = {}
        for p in tab_group.find_elements(By.CSS_SELECTOR, "section[role='tabpanel']"):
            key = p.get_attribute("data-tab")
            if not key:
                labelledby = p.get_attribute("aria-labelledby") or ""
                if labelledby.startswith("aria-tab-"):
                    key = labelledby.replace("aria-tab-", "")
            if key:
                panels_by_key[key] = p

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

        # 각 탭의 패널 텍스트 수집
        for btn in tab_buttons:
            tab_key = btn.get_attribute("data-tab") or btn.get_attribute("id") or ""
            tab_name = _name_for(btn)

            panel = panels_by_key.get(tab_key)
            if panel is None:
                try:
                    btn.click()
                    time.sleep(0.15)
                    panel = tab_group.find_element(
                        By.CSS_SELECTOR, f"section[role='tabpanel'][data-tab='{tab_key}']"
                    )
                except Exception:
                    panel = None

            if panel is not None:
                try:
                    # 코드블록 우선
                    code_block = panel.find_element(By.CSS_SELECTOR, "pre.devsite-code-highlight")
                    panel_text = (code_block.get_attribute("textContent") or "").strip()
                except NoSuchElementException:
                    panel_text = (panel.get_attribute("textContent") or "").strip()
            else:
                panel_text = "(해당 탭의 패널을 찾을 수 없음)"

            tab_texts.append(f"--- 탭: {tab_name} ---\n{panel_text}")

        # 원문 탭 영역 텍스트를 수집한 텍스트로 치환
        formatted = "\n\n".join(tab_texts)
        if tab_group.text and formatted:
            final_page_text = final_page_text.replace(tab_group.text, formatted, 1)

    return final_page_text


# ================== 메인 ==================
def main():
    # 입력 URL 목록 읽기
    if not os.path.exists(INPUT_LIST):
        raise FileNotFoundError(f"입력 목록 파일이 없습니다: {INPUT_LIST}")
    with open(INPUT_LIST, "r", encoding="utf-8") as f:
        raw_urls = [line.strip() for line in f if line.strip()]

    # 중복 제거
    urls_to_crawl = list(dict.fromkeys(raw_urls))
    print(f"총 {len(urls_to_crawl)}개 문서 크롤링 시작")

    driver = create_driver()
    wait = WebDriverWait(driver, WAIT_SEC)

    try:
        for i, url in enumerate(urls_to_crawl, 1):
            try:
                print(f"({i}/{len(urls_to_crawl)}) CR: {url}")
                final_page_text = crawl_page_content(driver, wait, url)

                content_to_save = f"Source URL: {url}\n\n{final_page_text}"

                filename = safe_filename_from_url(url)
                filepath = os.path.join(OUTPUT_DIR, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content_to_save)

                print(f"✅ 저장 완료: {filepath}")
            except Exception as e:
                print(f"   ! 실패: {e}")

            time.sleep(CRAWL_DELAY_SEC)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        print("\n크롤링 완료! 브라우저를 종료합니다.")


if __name__ == "__main__":
    main()