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

# ===== 설정값 =====
BASE_URL = "https://developers.google.com"
START_URL = "/people?hl=ko"  # ✅ People API 시작 URL
OUTPUT_DIR = "craweld2"      # ✅ 저장 폴더명 변경

# 결과 저장 폴더 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 셀레니움 옵션 설정
chrome_options = Options()
chrome_options.add_argument("--headless")  # 브라우저 창 없이 실행하려면 유지

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

    # 수집된 링크들을 절대경로로 변환
    urls_to_crawl = [
        urljoin(BASE_URL, elem.get_attribute("href"))
        for elem in link_elements
        if elem.get_attribute("href")
    ]
    # 시작 URL을 맨 앞에 추가
    urls_to_crawl.insert(0, full_start_url)

    # People API 문서 링크만 선별 (YouTube 전용이던 /v3/ 필터 제거)
    urls_to_crawl = sorted(
        list(
            dict.fromkeys(
                url
                for url in urls_to_crawl
                if "developers.google.com/people" in url  # ✅ 필터 조건 변경
            )
        )
    )
    print(f"✅ 총 {len(urls_to_crawl)}개의 유효한 페이지 링크를 수집했습니다.")

    for i, url in enumerate(urls_to_crawl):
        try:
            print(f"\n({i+1}/{len(urls_to_crawl)}) 크롤링 중: {url}")
            driver.get(url)

            # article 영역 대기
            article_element = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "article"))
            )

            # ======================= MODIFICATION START =======================
            # <article> 내 모든 링크 텍스트 뒤에 [href] 추가 (텍스트 추출 시 링크 표시 강화)
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
            # ======================== MODIFICATION END ========================

            # DOM 수정 후 article 전체 텍스트
            final_page_text = article_element.text

            # 탭 컴포넌트(devsite-selector) 처리: 숨겨진 탭 내용까지 모두 포함
            tab_groups = article_element.find_elements(By.TAG_NAME, "devsite-selector")

            for tab_group in tab_groups:
                tab_texts = []

                # 탭 버튼 수집
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

                # 탭 패널 수집
                tab_panels = tab_group.find_elements(
                    By.CSS_SELECTOR, "section[role='tabpanel']"
                )

                # 패널 매핑
                panels_by_key = {}
                for p in tab_panels:
                    key = p.get_attribute("data-tab")
                    if not key:
                        labelledby = p.get_attribute("aria-labelledby") or ""
                        if labelledby.startswith("aria-tab-"):
                            key = labelledby.replace("aria-tab-", "")
                    if key:
                        panels_by_key[key] = p

                # 각 탭 내용 추출
                for btn in tab_buttons:
                    tab_key = (
                        btn.get_attribute("data-tab") or btn.get_attribute("id") or ""
                    )
                    tab_name = _name_for(btn)

                    panel_text = ""
                    panel = panels_by_key.get(tab_key)

                    if panel is None:
                        try:
                            btn.click()
                            time.sleep(0.1)  # 패널 표시 대기
                            panel = tab_group.find_element(
                                By.CSS_SELECTOR,
                                f"section[role='tabpanel'][data-tab='{tab_key}']",
                            )
                        except Exception:
                            panel = None

                    if panel is not None:
                        try:
                            code_block = panel.find_element(
                                By.CSS_SELECTOR, "pre.devsite-code-highlight"
                            )
                            panel_text = code_block.get_attribute("textContent").strip()
                        except NoSuchElementException:
                            panel_text = (panel.get_attribute("textContent") or "").strip()
                    else:
                        panel_text = "(해당 탭의 패널을 찾을 수 없음)"

                    tab_texts.append(f"--- 탭: {tab_name} ---\n{panel_text}")

                # 기본 텍스트에서 탭 그룹의 단순 텍스트를 완전한 탭 콘텐츠로 교체
                formatted_tab_content = "\n\n".join(tab_texts)
                if tab_group.text and formatted_tab_content:
                    final_page_text = final_page_text.replace(
                        tab_group.text, formatted_tab_content, 1
                    )

            # 저장 파일 경로 계산
            path = url.split("?")[0].replace(BASE_URL, "")
            filename = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            # 저장 내용 구성
            content_to_save = f"Source URL: {url}\n\n{final_page_text}"

            # 파일 저장
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            print(f"✅ 저장 완료: {filepath}")

        except Exception as e:
            print(f"페이지 처리 중 오류 발생: {url} - {e}")

        time.sleep(1)

finally:
    driver.quit()
    print("\n크롤링 완료! 브라우저를 종료합니다.")
