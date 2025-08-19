import os
import re
import time
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException

# 시작 URL
BASE_URL = "https://cloud.google.com"
START_URL = "/bigquery/docs/reference/rest"

# 저장할 폴더 이름
OUTPUT_DIR = "../GOOGLE_API_DATA/bigquery_docs_crawled"

# 결과 저장 폴더 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"📁 '{OUTPUT_DIR}' 폴더를 생성했습니다.")

# 셀레니움 옵션 설정
chrome_options = Options()
chrome_options.add_argument("--headless")  # 백그라운드 실행
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

# 웹 드라이버 서비스 설정 및 실행
print("🚀 Chrome 드라이버를 시작합니다...")
service = ChromeService()
driver = webdriver.Chrome(service=service, options=chrome_options)


def clean_filename(url):
    """URL을 파일명으로 변환"""
    path = url.replace(BASE_URL, "").replace("https://", "").replace("http://", "")
    # 특수 문자를 언더스코어로 치환
    filename = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_")
    # 파일명이 너무 길면 자르기
    if len(filename) > 200:
        filename = filename[:200]
    return filename + ".txt"


def extract_page_content(driver, url):
    """페이지 내용을 추출하는 함수"""
    try:
        # 페이지 로드 대기
        wait = WebDriverWait(driver, 15)

        # main 또는 article 태그 찾기 (Google Cloud 문서 구조)
        content_element = None

        # 여러 가능한 콘텐츠 컨테이너를 시도
        content_selectors = [
            "article",
            "main",
            "[role='main']",
            ".devsite-article",
            ".devsite-main-content",
            "#gc-wrapper"
        ]

        for selector in content_selectors:
            try:
                content_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if content_element:
                    print(f"  ✓ 콘텐츠 영역 발견: {selector}")
                    break
            except TimeoutException:
                continue

        if not content_element:
            print("  ⚠️ 콘텐츠 영역을 찾을 수 없습니다. 전체 body를 사용합니다.")
            content_element = driver.find_element(By.TAG_NAME, "body")

        # 링크에 URL 주소 추가 (YouTube 크롤러와 동일한 방식)
        try:
            links_in_content = content_element.find_elements(By.TAG_NAME, "a")
            for link in links_in_content:
                href = link.get_attribute("href")
                if href and "javascript:void(0)" not in href and "#" not in href:
                    # JavaScript를 사용해 링크 텍스트 뒤에 URL 추가
                    driver.execute_script(
                        "if (arguments[0].textContent && !arguments[0].textContent.includes('[http')) {"
                        "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';"
                        "}",
                        link
                    )
        except Exception as e:
            print(f"  ⚠️ 링크 처리 중 오류: {e}")

        # 수정된 텍스트 가져오기
        final_page_text = content_element.text

        # 코드 블록 특별 처리 (Google Cloud 문서는 코드 예제가 많음)
        try:
            code_blocks = content_element.find_elements(By.CSS_SELECTOR,
                                                        "pre, code.devsite-code-highlight, .prettyprint")
            for code_block in code_blocks:
                code_text = code_block.get_attribute("textContent")
                if code_text and len(code_text.strip()) > 0:
                    # 코드 블록을 명확하게 표시
                    formatted_code = f"\n```\n{code_text.strip()}\n```\n"
                    # 원본 텍스트에서 해당 부분 교체
                    if code_block.text in final_page_text:
                        final_page_text = final_page_text.replace(code_block.text, formatted_code, 1)
        except Exception as e:
            print(f"  ⚠️ 코드 블록 처리 중 오류: {e}")

        # 탭 콘텐츠 처리 (Google Cloud 문서의 탭 구조)
        try:
            tab_groups = content_element.find_elements(By.CSS_SELECTOR, ".devsite-tabs, [role='tablist']")

            for tab_group in tab_groups:
                tab_contents = []

                # 탭 버튼 찾기
                tab_buttons = tab_group.find_elements(By.CSS_SELECTOR, "[role='tab'], .tab-button, button[data-tab]")

                for btn in tab_buttons:
                    try:
                        tab_name = btn.text.strip() or btn.get_attribute("aria-label") or "탭"

                        # 탭 클릭하여 활성화
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.3)

                        # 해당 탭의 패널 찾기
                        panel_id = btn.get_attribute("aria-controls") or btn.get_attribute("data-tab")
                        if panel_id:
                            panel = driver.find_element(By.ID, panel_id)
                        else:
                            # 다음 형제 요소에서 패널 찾기
                            panel = driver.find_element(By.XPATH, "following-sibling::*[@role='tabpanel'][1]")

                        panel_text = panel.get_attribute("textContent").strip()
                        tab_contents.append(f"\n--- 탭: {tab_name} ---\n{panel_text}")
                    except Exception:
                        continue

                if tab_contents:
                    formatted_tabs = "\n".join(tab_contents)
                    # 기존 탭 그룹 텍스트를 포맷된 버전으로 교체
                    if tab_group.text:
                        final_page_text = final_page_text.replace(tab_group.text, formatted_tabs, 1)
        except Exception as e:
            print(f"  ⚠️ 탭 처리 중 오류: {e}")

        return final_page_text

    except Exception as e:
        print(f"  ❌ 페이지 콘텐츠 추출 실패: {e}")
        return None


def collect_sidebar_links(driver, wait):
    """사이드바에서 모든 링크 수집"""
    links = set()

    # Google Cloud 문서 사이드바 셀렉터들
    sidebar_selectors = [
        "devsite-book-nav",  # 기본
        ".devsite-nav",
        "nav.devsite-book-nav",
        "[role='navigation']",
        ".devsite-section-nav",
        "#gc-sidebar"
    ]

    sidebar_found = False

    for selector in sidebar_selectors:
        try:
            sidebar = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            if sidebar:
                print(f"✓ 사이드바 발견: {selector}")
                sidebar_found = True

                # 사이드바 내의 모든 링크 수집
                link_elements = sidebar.find_elements(By.TAG_NAME, "a")

                for elem in link_elements:
                    href = elem.get_attribute("href")
                    if href:
                        # BigQuery REST API 관련 링크만 필터링
                        if "/bigquery/docs/reference/rest" in href:
                            full_url = urljoin(BASE_URL, href)
                            # URL 파라미터 제거 (중복 방지)
                            clean_url = full_url.split("?")[0].split("#")[0]
                            links.add(clean_url)

                if links:
                    break

        except TimeoutException:
            continue

    if not sidebar_found:
        print("⚠️ 사이드바를 찾을 수 없습니다. 현재 페이지의 링크만 수집합니다.")

        # 페이지 전체에서 BigQuery REST API 링크 찾기
        all_links = driver.find_elements(By.TAG_NAME, "a")
        for elem in all_links:
            href = elem.get_attribute("href")
            if href and "/bigquery/docs/reference/rest" in href:
                full_url = urljoin(BASE_URL, href)
                clean_url = full_url.split("?")[0].split("#")[0]
                links.add(clean_url)

    return list(links)


# 메인 크롤링 로직
try:
    # 시작 페이지로 이동
    full_start_url = urljoin(BASE_URL, START_URL)
    print(f"\n📍 시작 URL: {full_start_url}")
    driver.get(full_start_url)

    # 페이지 로드 대기
    time.sleep(3)

    # 쿠키 동의 팝업 처리 (있을 경우)
    try:
        cookie_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), '동의')]")
        cookie_button.click()
        print("쿠키 동의 팝업을 처리했습니다.")
        time.sleep(1)
    except:
        pass

    # 사이드바 링크 수집
    print("\n🔍 사이드바에서 링크를 수집 중...")
    wait = WebDriverWait(driver, 15)

    urls_to_crawl = collect_sidebar_links(driver, wait)

    # 시작 URL도 포함
    if full_start_url not in urls_to_crawl:
        urls_to_crawl.insert(0, full_start_url)

    # 중복 제거 및 정렬
    urls_to_crawl = sorted(list(set(urls_to_crawl)))

    print(f"\n✅ 총 {len(urls_to_crawl)}개의 페이지를 발견했습니다.")

    # 크롤링할 URL 목록 출력
    print("\n📋 크롤링할 페이지 목록:")
    for i, url in enumerate(urls_to_crawl[:10], 1):  # 처음 10개만 표시
        print(f"  {i}. {url}")
    if len(urls_to_crawl) > 10:
        print(f"  ... 외 {len(urls_to_crawl) - 10}개")

    # 각 페이지 크롤링
    successful_count = 0
    failed_urls = []

    for i, url in enumerate(urls_to_crawl, 1):
        try:
            print(f"\n📄 ({i}/{len(urls_to_crawl)}) 크롤링 중: {url}")
            driver.get(url)
            time.sleep(2)  # 페이지 로드 대기

            # 페이지 내용 추출
            content = extract_page_content(driver, url)

            if content and len(content.strip()) > 100:  # 최소 100자 이상의 내용이 있을 때만 저장
                # 파일명 생성
                filename = clean_filename(url)
                filepath = os.path.join(OUTPUT_DIR, filename)

                # 저장할 내용 구성
                content_to_save = f"Source URL: {url}\n" + "=" * 80 + f"\n\n{content}"

                # 파일로 저장
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content_to_save)

                print(f"  ✅ 저장 완료: {filename} ({len(content)} 문자)")
                successful_count += 1
            else:
                print(f"  ⚠️ 콘텐츠가 너무 짧거나 비어있음")
                failed_urls.append(url)

        except Exception as e:
            print(f"  ❌ 페이지 처리 실패: {e}")
            failed_urls.append(url)

        # 서버 부하 방지를 위한 대기
        time.sleep(1)

    # 크롤링 결과 요약
    print("\n" + "=" * 60)
    print("📊 크롤링 완료 요약")
    print("=" * 60)
    print(f"✅ 성공: {successful_count}개 페이지")
    print(f"❌ 실패: {len(failed_urls)}개 페이지")

    if failed_urls:
        print("\n실패한 URL 목록:")
        for url in failed_urls[:5]:
            print(f"  - {url}")
        if len(failed_urls) > 5:
            print(f"  ... 외 {len(failed_urls) - 5}개")

    print(f"\n📁 모든 파일이 '{OUTPUT_DIR}' 폴더에 저장되었습니다.")

except Exception as e:
    print(f"\n❌ 크롤링 중 치명적 오류 발생: {e}")

finally:
    driver.quit()
    print("\n🔌 브라우저를 종료했습니다.")
    print("✨ 크롤링 작업이 완료되었습니다!")