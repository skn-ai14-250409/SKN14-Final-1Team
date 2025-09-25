import os
import re
import time
from urllib.parse import urljoin
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================
# 설정값 모음
# ==========================
CONFIGS = {
    "identity": {
        "START_URL": "/identity/protocols/oauth2?hl=ko",
        "PATTERNS": ["developers.google.com/identity"],
        "OUTPUT_DIR": "GOOGLE_API_DATA/google_identity_docs_crawled",
    }#,
    # "youtube": {
    #     "START_URL": "/youtube/v3/getting-started?hl=ko",
    #     "PATTERNS": ["developers.google.com/youtube", "/v3/"],
    #     "OUTPUT_DIR": "GOOGLE_API_DATA/youtube_docs_crawled",
    # },
    # "gmail": {
    #     "START_URL": "/workspace/gmail/api/auth/scopes?hl=ko",
    #     "PATTERNS": ["developers.google.com/workspace/gmail"],
    #     "OUTPUT_DIR": "GOOGLE_API_DATA/gmail_docs_crawled",
    # },
    # "calendar": {
    #     "START_URL": "/workspace/calendar/api/v3/reference?hl=ko",
    #     "PATTERNS": ["developers.google.com/workspace/calendar"],
    #     "OUTPUT_DIR": "GOOGLE_API_DATA/calendar_docs_crawled",
    # },
}

BASE_URL = "https://developers.google.com"
THRESHOID_DATE = "2000-01-01"

# 셀레니움 옵션 설정
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
service = ChromeService()
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    # ==========================
    # 모든 TARGET 순회
    # ==========================
    for TARGET, cfg in CONFIGS.items():
        print(f"\n {TARGET} 크롤링 시작")

        # 결과 저장 폴더 생성
        if not os.path.exists(cfg["OUTPUT_DIR"]):
            os.makedirs(cfg["OUTPUT_DIR"])

        try:
            full_start_url = urljoin(BASE_URL, cfg["START_URL"])
            driver.get(full_start_url)

            # 상단바 사이드바가 나타날 때까지 대기
            wait = WebDriverWait(driver, 15)

            # nav 안의 모든 a 태그 선택
            links = driver.find_elements(
                By.CSS_SELECTOR, "nav.devsite-tabs-wrapper tab a"
            )

            # 상단바 링크 수집
            top_links = [
                link.get_attribute("href")
                for link in links
                if link.get_attribute("href")
            ]
            print(f"✅ 상단바에서 {len(top_links)}개의 링크를 수집했습니다.")

            top_links = sorted(
                list(
                    dict.fromkeys(
                        url
                        for url in (top_links)
                        if all(p in url for p in cfg["PATTERNS"])
                    )
                )
            )
            print(f"✅ 중복제거 후 {len(top_links)}개의 링크를 수집했습니다.")

            all_side_links = []
            for link in top_links:
                driver.get(link)
                try:
                    nav_container = wait.until(
                        EC.presence_of_element_located(
                            (By.TAG_NAME, "devsite-book-nav")
                        )
                    )
                    link_elements = nav_container.find_elements(By.TAG_NAME, "a")
                    side_links = [
                        urljoin(BASE_URL, elem.get_attribute("href"))
                        for elem in link_elements
                        if elem.get_attribute("href")
                    ]
                    all_side_links.extend(side_links)
                except Exception as e:
                    print(f"사이드바를 찾지 못함: {link} / {e}")

            # 필터링
            urls_to_crawl = sorted(
                list(
                    dict.fromkeys(
                        url
                        for url in (top_links + all_side_links)
                        if all(p in url for p in cfg["PATTERNS"])
                    )
                )
            )
            print(f"✅ 총 {len(urls_to_crawl)}개의 유효한 페이지 링크를 수집했습니다.")

            # 각 페이지 처리
            for i, url in enumerate(urls_to_crawl):
                try:
                    print(f"\n({i+1}/{len(urls_to_crawl)}) 크롤링 중: {url}")
                    driver.get(url)

                    # footer에서 last_updated 추출
                    footer_paragraphs = driver.find_elements(
                        By.CSS_SELECTOR, "devsite-content-footer p"
                    )
                    last_updated = None
                    for p in footer_paragraphs:
                        text = p.text.strip()
                        # '업데이트' 또는 'updated'가 포함된 경우
                        if "업데이트" in text or "updated" in text.lower():
                            # 날짜 추출 (YYYY-MM-DD)
                            match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                            if match:
                                last_updated = match.group(1)
                                break

                    execute_code = False
                    if last_updated:
                        updated_date = datetime.strptime(
                            last_updated, "%Y-%m-%d"
                        ).date()
                        threshold_date = datetime.strptime(
                            THRESHOID_DATE, "%Y-%m-%d"
                        ).date()
                        if updated_date >= threshold_date:
                            execute_code = True
                    else:
                        execute_code = True

                    if execute_code:
                        article_element = wait.until(
                            EC.presence_of_element_located((By.TAG_NAME, "article"))
                        )

                        # 링크 href를 본문에 추가
                        try:
                            links_in_article = article_element.find_elements(
                                By.TAG_NAME, "a"
                            )
                            for link in links_in_article:
                                href = link.get_attribute("href")
                                # href가 유효하고, 클릭 시 페이지 이동을 하는 링크만 대상으로 함
                                if href and "javascript:void(0)" not in href:
                                    driver.execute_script(
                                        # link.textContent에 '[href]'를 추가.
                                        "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                                        link,
                                    )
                        except Exception as e:
                            print(f"링크 처리 중 예기치 않은 오류 발생: {e}")
                            print("링크 수정 중 DOM 변경 발생")

                        final_page_text = article_element.text

                        # article 내의 모든 'devsite-selector' (탭 그룹)를 직접 찾음
                        tab_groups = article_element.find_elements(
                            By.TAG_NAME, "devsite-selector"
                        )

                        # 각 탭 그룹을 순회하며, 숨겨진 탭 내용을 포함한 전체 탭 콘텐츠를 추출
                        for tab_group in tab_groups:
                            tab_texts = []

                            # 탭 버튼과 이름 수집
                            tab_buttons = tab_group.find_elements(
                                By.CSS_SELECTOR,
                                "devsite-tabs tab:not(.devsite-overflow-tab)",
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

                            # 모든 패널 수집 (활성/비활성 포함)
                            tab_panels = tab_group.find_elements(
                                By.CSS_SELECTOR, "section[role='tabpanel']"
                            )

                            # 패널을 data-tab 기준으로 매핑
                            panels_by_key = {}
                            for p in tab_panels:
                                key = p.get_attribute("data-tab")
                                if not key:
                                    labelledby = (
                                        p.get_attribute("aria-labelledby") or ""
                                    )
                                    if labelledby.startswith("aria-tab-"):
                                        key = labelledby.replace("aria-tab-", "")
                                if key:
                                    panels_by_key[key] = p

                            # 각 버튼(=각 탭)에 대응하는 패널에서 내용 추출
                            for btn in tab_buttons:
                                tab_key = (
                                    btn.get_attribute("data-tab")
                                    or btn.get_attribute("id")
                                    or ""
                                )
                                tab_name = _name_for(btn)

                                panel_text = ""
                                panel = panels_by_key.get(tab_key)

                                if panel is None:
                                    try:
                                        btn.click()
                                        time.sleep(0.1)
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
                                            By.CSS_SELECTOR,
                                            "pre.devsite-code-highlight",
                                        )
                                        panel_text = code_block.get_attribute(
                                            "textContent"
                                        ).strip()
                                    except Exception:
                                        # 숨김 상태여도 textContent로 전부 읽힘
                                        panel_text = (
                                            panel.get_attribute("textContent") or ""
                                        ).strip()
                                else:
                                    panel_text = "(해당 탭의 패널을 찾을 수 없음)"

                                tab_texts.append(
                                    f"--- 탭: {tab_name} ---\n{panel_text}"
                                )

                            formatted_tab_content = "\n\n".join(tab_texts)
                            if tab_group.text and formatted_tab_content:
                                final_page_text = final_page_text.replace(
                                    tab_group.text, formatted_tab_content, 1
                                )

                        path = url.split("?")[0].replace(BASE_URL, "")
                        filename = (
                            re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"
                        )
                        filepath = os.path.join(cfg["OUTPUT_DIR"], filename)

                        # 파일에 저장할 내용을 "[0000-00-00] Source URL: [URL]\n\n[본문]" 형식으로 구성
                        content_to_save = (
                            f"[{last_updated}] Source URL: {url}\n\n{final_page_text}"
                        )

                        # 파일로 저장
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(content_to_save)
                        print(f"✅ 저장 완료: {filepath}")

                except Exception as e:
                    print(f"페이지 처리 중 오류 발생: {url} - {e}")
                time.sleep(1)

        finally:
            # 타겟이 끝날 때마다 쿠키 초기화 (세션 충돌 방지)
            driver.delete_all_cookies()
            print(f"✅ {TARGET} 크롤링 완료")

finally:
    driver.quit()
    print("\n크롤링 완료! 브라우저 종료.")
