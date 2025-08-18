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
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException

# ======================= 설정 변경 =======================
# 시작 URL
BASE_URL = "https://developers.google.com"
START_URL = "/identity/protocols/oauth2?hl=ko"

# 저장할 폴더 이름
OUTPUT_DIR = "google_identity_docs_crawled"
# =======================================================


# 결과 저장 폴더 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 셀레니움 옵션 설정
chrome_options = Options()
chrome_options.add_argument("--headless")  # 브라우저 창을 보지 않고 실행

# 웹 드라이버 서비스 설정 및 실행
service = ChromeService()
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    # 시작 페이지로 이동
    full_start_url = urljoin(BASE_URL, START_URL)
    driver.get(full_start_url)

    # 왼쪽 사이드바(<devsite-book-nav>)가 나타날 때까지 대기
    print("왼쪽 사이드바의 링크를 수집 중...")
    wait = WebDriverWait(driver, 15)

    # <devsite-book-nav> 태그 안의 모든 <a> 링크를 찾기
    nav_container = wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "devsite-book-nav"))
    )
    link_elements = nav_container.find_elements(By.TAG_NAME, "a")

    urls_to_crawl = [
        urljoin(BASE_URL, elem.get_attribute("href"))
        for elem in link_elements
        if elem.get_attribute("href")
    ]
    urls_to_crawl.insert(0, full_start_url)

    # ===== 수집할 URL 필터링 조건 변경 =====
    urls_to_crawl = sorted(
        list(
            dict.fromkeys(
                url
                for url in urls_to_crawl
                if "developers.google.com/identity" in url
            )
        )
    )
    print(f"✅ 총 {len(urls_to_crawl)}개의 유효한 페이지 링크를 수집했습니다.")

    for i, url in enumerate(urls_to_crawl):
        try:
            print(f"\n({i+1}/{len(urls_to_crawl)}) 크롤링 중: {url}")
            driver.get(url)
            article_element = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )

            # article 내의 모든 <a> 태그를 찾아 텍스트 뒤에 href 주소를 [주소] 형태로 추가
            try:
                links_in_article = article_element.find_elements(By.TAG_NAME, "a")
                for link in links_in_article:
                    href = link.get_attribute("href")
                    if href and "javascript:void(0)" not in href:
                        driver.execute_script(
                            "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                            link
                        )
            except StaleElementReferenceException:
                print("링크 수정 중 DOM이 변경되어 일부 링크를 처리하지 못했습니다.")
            except Exception as e:
                print(f"링크 처리 중 예기치 않은 오류 발생: {e}")

            # DOM 수정 후 article 전체의 텍스트를 가져옴
            final_page_text = article_element.text

            # article 내의 모든 'devsite-selector' (탭 그룹)를 직접 찾음
            tab_groups = article_element.find_elements(By.TAG_NAME, "devsite-selector")

            # 각 탭 그룹을 순회하며 전체 탭 콘텐츠를 추출
            for tab_group in tab_groups:
                tab_texts = []

                def _name_for(btn):
                    txt = (btn.text or "").strip()
                    if txt: return txt
                    return (btn.get_attribute("aria-controls") or btn.get_attribute("id") or btn.get_attribute("data-tab") or "UNNAMED")

                tab_buttons = tab_group.find_elements(By.CSS_SELECTOR, "devsite-tabs tab:not(.devsite-overflow-tab)")
                tab_panels = tab_group.find_elements(By.CSS_SELECTOR, "section[role='tabpanel']")

                panels_by_key = {}
                for p in tab_panels:
                    key = p.get_attribute("data-tab")
                    if not key:
                        labelledby = p.get_attribute("aria-labelledby") or ""
                        if labelledby.startswith("aria-tab-"): key = labelledby.replace("aria-tab-", "")
                    if key: panels_by_key[key] = p

                for btn in tab_buttons:
                    tab_key = (btn.get_attribute("data-tab") or btn.get_attribute("id") or "")
                    tab_name = _name_for(btn)
                    panel_text = "(해당 탭의 패널을 찾을 수 없음)"
                    panel = panels_by_key.get(tab_key)

                    if panel is not None:
                        try:
                            code_block = panel.find_element(By.CSS_SELECTOR, "pre.devsite-code-highlight")
                            panel_text = code_block.get_attribute("textContent").strip()
                        except NoSuchElementException:
                            panel_text = (panel.get_attribute("textContent") or "").strip()
                    
                    tab_texts.append(f"--- 탭: {tab_name} ---\n{panel_text}")

                formatted_tab_content = "\n\n".join(tab_texts)
                if tab_group.text and formatted_tab_content:
                    final_page_text = final_page_text.replace(tab_group.text, formatted_tab_content, 1)

            path = url.split("?")[0].replace(BASE_URL, "")
            filename = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            content_to_save = f"Source URL: {url}\n\n{final_page_text}"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            print(f"✅ 저장 완료: {filepath}")

        except Exception as e:
            print(f"페이지 처리 중 오류 발생: {url} - {e}")

        time.sleep(1)

finally:
    driver.quit()
    print("\n크롤링 완료! 브라우저를 종료합니다.")