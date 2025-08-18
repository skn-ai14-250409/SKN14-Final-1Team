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

# 시작 URL
BASE_URL = "https://developers.google.com"
START_URL = "/youtube/v3/getting-started?hl=ko"

# 저장할 폴더 이름
OUTPUT_DIR = "youtube_docs_crawled"

# 결과 저장 폴더 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 셀레니움 옵션 설정
chrome_options = Options()
chrome_options.add_argument(
    "--headless"
)  # 브라우저 창을 보지 않고 실행하려면 주석 해제

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

    urls_to_crawl = sorted(
        list(
            dict.fromkeys(
                url
                for url in urls_to_crawl
                if "developers.google.com/youtube" in url and "/v3/" in url
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

            # ======================= MODIFICATION START =======================
            # 목표: <article> 내의 모든 <a> 태그를 찾아 텍스트 뒤에 href 주소를 [주소] 형태로 추가합니다.
            # 방법: Selenium의 execute_script를 사용해 브라우저의 DOM을 직접 조작합니다.
            #       이렇게 하면, .text나 .get_attribute('textContent')로 텍스트를 추출할 때
            #       수정된 내용이 반영되어 나옵니다.
            try:
                links_in_article = article_element.find_elements(By.TAG_NAME, "a")
                for link in links_in_article:
                    href = link.get_attribute("href")
                    # href가 유효하고, 클릭 시 페이지 이동을 하는 링크만 대상으로 함
                    if href and "javascript:void(0)" not in href:
                        driver.execute_script(
                            # link.textContent에 '[href]'를 추가합니다.
                            "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                            link
                        )
            except StaleElementReferenceException:
                # DOM이 변경되는 도중 StaleElementReferenceException이 발생할 수 있습니다.
                # 이 경우, 링크 수정을 건너뛰고 텍스트만이라도 수집하도록 계속 진행합니다.
                print("링크 수정 중 DOM이 변경되어 일부 링크를 처리하지 못했습니다.")
            except Exception as e:
                print(f"링크 처리 중 예기치 않은 오류 발생: {e}")
            # ======================== MODIFICATION END ========================


            # 먼저 article 전체의 기본 텍스트를 가져옴 (DOM 수정 후)
            final_page_text = article_element.text

            # article 내의 모든 'devsite-selector' (탭 그룹)를 직접 찾음
            tab_groups = article_element.find_elements(By.TAG_NAME, "devsite-selector")

            # 각 탭 그룹을 순회하며, 숨겨진 탭 내용을 포함한 전체 탭 콘텐츠를 추출
            for tab_group in tab_groups:
                tab_texts = []

                # 1) 탭 버튼과 이름 수집
                tab_buttons = tab_group.find_elements(
                    By.CSS_SELECTOR, "devsite-tabs tab:not(.devsite-overflow-tab)"
                )

                # 버튼의 표시 텍스트가 비어있을 수 있어서 보강
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

                # 2) 모든 패널 수집 (활성/비활성 포함)
                tab_panels = tab_group.find_elements(
                    By.CSS_SELECTOR, "section[role='tabpanel']"
                )

                # 3) 패널을 data-tab 기준으로 매핑
                panels_by_key = {}
                for p in tab_panels:
                    key = p.get_attribute("data-tab")
                    if not key:
                        labelledby = p.get_attribute("aria-labelledby") or ""
                        if labelledby.startswith("aria-tab-"):
                            key = labelledby.replace("aria-tab-", "")
                    if key:
                        panels_by_key[key] = p

                # 4) 각 버튼(=각 탭)에 대응하는 패널에서 내용 추출
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
                            time.sleep(0.1) # 클릭 후 패널이 나타날 시간을 짧게 줌
                            panel = tab_group.find_element(
                                By.CSS_SELECTOR,
                                f"section[role='tabpanel'][data-tab='{tab_key}']",
                            )
                        except Exception:
                            panel = None

                    if panel is not None:
                        try:
                            # 코드블록이 있으면 우선적으로 코드블록 텍스트 사용
                            code_block = panel.find_element(
                                By.CSS_SELECTOR, "pre.devsite-code-highlight"
                            )
                            panel_text = code_block.get_attribute("textContent").strip()
                        except NoSuchElementException:
                            # 숨김 상태여도 textContent로 전부 읽힘
                            panel_text = (
                                panel.get_attribute("textContent") or ""
                            ).strip()
                    else:
                        panel_text = "(해당 탭의 패널을 찾을 수 없음)"

                    tab_texts.append(f"--- 탭: {tab_name} ---\n{panel_text}")

                # 5. 기본 텍스트에서 해당 탭 그룹의 단순 텍스트를 -> 완전한 형식의 탭 콘텐츠로 교체
                formatted_tab_content = "\n\n".join(tab_texts)
                if tab_group.text and formatted_tab_content:
                    final_page_text = final_page_text.replace(
                        tab_group.text, formatted_tab_content, 1
                    )

            path = url.split("?")[0].replace(BASE_URL, "")
            filename = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)

            # 파일에 저장할 내용을 "Source URL: [URL]\n\n[본문]" 형식으로 구성
            content_to_save = f"Source URL: {url}\n\n{final_page_text}"

            # 파일로 저장
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            print(f"✅ 저장 완료: {filepath}")

        except Exception as e:
            print(f"페이지 처리 중 오류 발생: {url} - {e}")

        time.sleep(1)

finally:
    driver.quit()
    print("\n크롤링 완료! 브라우저를 종료합니다.")