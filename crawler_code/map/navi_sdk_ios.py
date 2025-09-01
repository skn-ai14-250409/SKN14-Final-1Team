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
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException

# 시작 URL
BASE_URL = "https://developers.google.com"
START_URL = "/maps/documentation/navigation/ios-sdk?hl=ko"

# 저장할 폴더 이름
OUTPUT_DIR = "navi_sdk_ios"

# 결과 저장 폴더 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 셀레니움 옵션 설정
chrome_options = Options()
# chrome_options.add_argument("--headless")  # 브라우저 창을 보지 않고 실행하려면 주석 해제
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

# 로그 메시지 숨기기 옵션들
chrome_options.add_argument("--disable-logging")
chrome_options.add_argument("--disable-logging-redirect")
chrome_options.add_argument("--log-level=3")  # INFO = 0, WARNING = 1, ERROR = 2, FATAL = 3
chrome_options.add_argument("--silent")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-plugins")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--disable-features=VizDisplayCompositor")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
chrome_options.add_experimental_option('useAutomationExtension', False)

# 추가 로그 제거 옵션
import logging
logging.getLogger('selenium').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# 웹 드라이버 서비스 설정 및 실행
try:
    from webdriver_manager.chrome import ChromeDriverManager
    service = ChromeService(ChromeDriverManager().install())
    print("✅ webdriver-manager로 ChromeDriver 설정 완료")
except ImportError:
    service = ChromeService()
    print("✅ 시스템 ChromeDriver 사용")

driver = webdriver.Chrome(service=service, options=chrome_options)

def expand_sidebar_sections(driver, wait):
    """사이드바의 접힌 섹션들을 모두 펼치기"""
    try:
        print("🔄 사이드바 섹션 확장 중...")
        
        # 다양한 확장 버튼 선택자들
        expand_selectors = [
            'button[aria-expanded="false"]',
            '.devsite-nav-toggle',
            'button[aria-controls]',
            '[data-category="referencenav"]',
            '.devsite-nav-item-toggle',
            '.devsite-nav-expandable > button',
            '.devsite-nav-item.devsite-nav-expandable'
        ]
        
        expanded_count = 0
        max_attempts = 3  # 최대 시도 횟수 제한
        
        for attempt in range(max_attempts):
            try:
                for selector in expand_selectors:
                    try:
                        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                        for button in buttons:
                            try:
                                if button.is_displayed() and button.is_enabled():
                                    # 이미 확장된 버튼인지 확인
                                    aria_expanded = button.get_attribute('aria-expanded')
                                    if aria_expanded != 'true':
                                        driver.execute_script("arguments[0].click();", button)
                                        expanded_count += 1
                                        time.sleep(0.1)  # 대기 시간 단축
                            except Exception:
                                continue
                    except Exception:
                        continue
                
                if expanded_count > 0:
                    break  # 확장된 버튼이 있으면 중단
                    
            except Exception:
                continue
        
        print(f"✅ {expanded_count}개 섹션 확장 완료")
        time.sleep(1)  # 확장 후 안정화 대기 시간 단축
        
    except Exception as e:
        print(f"⚠️ 섹션 확장 중 오류: {e}")

def collect_sidebar_links(driver, wait):
    """사이드바에서 모든 링크 수집"""
    try:
        print("🔍 사이드바 링크 수집 중...")
        
        # 사이드바 확장 시도 (타임아웃 방지)
        try:
            expand_sidebar_sections(driver, wait)
        except KeyboardInterrupt:
            print("⚠️ 사이드바 확장 중단됨, 기본 상태로 진행")
        except Exception as e:
            print(f"⚠️ 사이드바 확장 오류, 기본 상태로 진행: {e}")
        
        # 다양한 사이드바 선택자 시도
        sidebar_selectors = [
            'devsite-book-nav',
            '.devsite-nav-list',
            '.devsite-section-nav',
            '[role="navigation"]',
            '.devsite-nav',
            'nav.devsite-nav'
        ]
        
        nav_container = None
        for selector in sidebar_selectors:
            try:
                nav_container = driver.find_element(By.CSS_SELECTOR, selector)
                if nav_container:
                    print(f"✅ 사이드바 발견: {selector}")
                    break
            except NoSuchElementException:
                continue
        
        if not nav_container:
            print("⚠️ 특정 사이드바를 찾을 수 없어 전체 페이지에서 검색")
            nav_container = driver.find_element(By.TAG_NAME, "body")
        
        # 모든 링크 수집
        link_elements = nav_container.find_elements(By.TAG_NAME, "a")
        print(f"🔗 총 {len(link_elements)}개 링크 발견")
        
        urls_to_crawl = []
        for elem in link_elements:
            href = elem.get_attribute("href")
            if href and "/maps/documentation/navigation" in href and "developers.google.com" in href:
                # 한국어 파라미터 추가
                if "?hl=ko" not in href:
                    if "?" in href:
                        href = href + "&hl=ko"
                    else:
                        href = href + "?hl=ko"
                urls_to_crawl.append(href)
        
        # 시작 URL도 포함
        full_start_url = urljoin(BASE_URL, START_URL)
        urls_to_crawl.insert(0, full_start_url)
        
        # 중복 제거 및 정렬
        urls_to_crawl = sorted(list(dict.fromkeys(urls_to_crawl)))
        
        # Google Maps Navigation API 관련 URL만 필터링
        filtered_urls = [
            url for url in urls_to_crawl 
            if "developers.google.com/maps/documentation/navigation" in url
        ]
        
        print(f"✅ 총 {len(filtered_urls)}개의 유효한 Maps Navigation API 페이지 링크 수집 완료")
        
        # 처음 10개 링크 미리보기
        print("\n📋 수집된 링크 미리보기 (처음 10개):")
        for i, url in enumerate(filtered_urls[:10], 1):
            print(f"  {i}. {url}")
        if len(filtered_urls) > 10:
            print(f"  ... 그리고 {len(filtered_urls) - 10}개 더")
        
        return filtered_urls
        
    except Exception as e:
        print(f"❌ 사이드바 링크 수집 오류: {e}")
        return []

def process_tabs_in_article(driver, article_element):
    """article 내의 탭 그룹 처리"""
    try:
        # article 내의 모든 'devsite-selector' (탭 그룹)를 찾음
        tab_groups = article_element.find_elements(By.TAG_NAME, "devsite-selector")
        
        if not tab_groups:
            return article_element.text
        
        print(f"🎯 {len(tab_groups)}개 탭 그룹 발견, 처리 중...")
        
        final_page_text = article_element.text
        
        for tab_group_idx, tab_group in enumerate(tab_groups):
            tab_texts = []
            
            # 탭 버튼들 찾기
            tab_buttons = tab_group.find_elements(
                By.CSS_SELECTOR, "devsite-tabs tab:not(.devsite-overflow-tab)"
            )
            
            if not tab_buttons:
                continue
            
            def get_tab_name(btn):
                txt = (btn.text or "").strip()
                if txt:
                    return txt
                return (
                    btn.get_attribute("aria-controls")
                    or btn.get_attribute("id")
                    or btn.get_attribute("data-tab")
                    or f"UNNAMED_TAB_{tab_group_idx}"
                )
            
            # 모든 탭 패널 수집
            tab_panels = tab_group.find_elements(
                By.CSS_SELECTOR, "section[role='tabpanel']"
            )
            
            # 패널을 data-tab 기준으로 매핑
            panels_by_key = {}
            for p in tab_panels:
                key = p.get_attribute("data-tab")
                if not key:
                    labelledby = p.get_attribute("aria-labelledby") or ""
                    if labelledby.startswith("aria-tab-"):
                        key = labelledby.replace("aria-tab-", "")
                if key:
                    panels_by_key[key] = p
            
            # 각 탭 처리
            for btn_idx, btn in enumerate(tab_buttons):
                tab_key = (
                    btn.get_attribute("data-tab") 
                    or btn.get_attribute("id") 
                    or f"tab_{btn_idx}"
                )
                tab_name = get_tab_name(btn)
                
                panel_text = ""
                panel = panels_by_key.get(tab_key)
                
                # 패널이 없으면 클릭해서 활성화
                if panel is None:
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(0.5)
                        panel = tab_group.find_element(
                            By.CSS_SELECTOR,
                            f"section[role='tabpanel'][data-tab='{tab_key}']",
                        )
                    except Exception:
                        panel = None
                
                # 패널 내용 추출
                if panel is not None:
                    try:
                        # 코드 블록 우선 확인
                        code_block = panel.find_element(
                            By.CSS_SELECTOR, "pre.devsite-code-highlight"
                        )
                        panel_text = code_block.get_attribute("textContent").strip()
                    except NoSuchElementException:
                        # 일반 텍스트 내용
                        panel_text = (panel.get_attribute("textContent") or "").strip()
                else:
                    panel_text = "(패널을 찾을 수 없음)"
                
                tab_texts.append(f"--- 탭: {tab_name} ---\n{panel_text}")
            
            # 탭 그룹의 기본 텍스트를 완전한 형식으로 교체
            formatted_tab_content = "\n\n".join(tab_texts)
            if tab_group.text and formatted_tab_content:
                final_page_text = final_page_text.replace(
                    tab_group.text, formatted_tab_content, 1
                )
        
        return final_page_text
        
    except Exception as e:
        print(f"⚠️ 탭 처리 중 오류: {e}")
        return article_element.text

def add_links_to_text(driver, article_element):
    """article 내의 모든 링크에 [URL] 형태로 주소 추가"""
    try:
        links_in_article = article_element.find_elements(By.TAG_NAME, "a")
        link_count = 0
        
        for link in links_in_article:
            href = link.get_attribute("href")
            if href and "javascript:void(0)" not in href and href.startswith("http"):
                try:
                    driver.execute_script(
                        "arguments[0].textContent = arguments[0].textContent.trim() + ' [' + arguments[0].href + ']';",
                        link
                    )
                    link_count += 1
                except Exception:
                    continue
        
        if link_count > 0:
            print(f"🔗 {link_count}개 링크에 URL 주소 추가 완료")
            
    except StaleElementReferenceException:
        print("⚠️ 링크 수정 중 DOM 변경으로 일부 링크 처리 불가")
    except Exception as e:
        print(f"⚠️ 링크 처리 중 오류: {e}")

try:
    # 시작 페이지로 이동
    full_start_url = urljoin(BASE_URL, START_URL)
    print(f"🚀 시작 페이지로 이동: {full_start_url}")
    driver.get(full_start_url)
    
    # 대기 객체 생성
    wait = WebDriverWait(driver, 15)
    
    # 페이지 로드 대기
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        print("✅ 페이지 로드 완료")
    except TimeoutException:
        print("⚠️ 페이지 로드 시간 초과, 계속 진행...")
    
    # 사이드바에서 모든 링크 수집
    urls_to_crawl = collect_sidebar_links(driver, wait)
    
    if not urls_to_crawl:
        print("❌ 크롤링할 URL이 없습니다.")
        exit(1)
    
    print(f"\n🎯 총 {len(urls_to_crawl)}개 페이지 크롤링 시작")
    print("=" * 70)
    
    successful_count = 0
    failed_count = 0
    
    for i, url in enumerate(urls_to_crawl):
        try:
            print(f"\n📄 ({i+1}/{len(urls_to_crawl)}) 크롤링 중: {url}")
            
            driver.get(url)
            
            # article 요소 대기
            try:
                article_element = wait.until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
            except TimeoutException:
                # article이 없으면 main이나 다른 컨테이너 시도
                try:
                    article_element = wait.until(
                        EC.presence_of_element_located((By.TAG_NAME, "main"))
                    )
                except TimeoutException:
                    article_element = driver.find_element(By.TAG_NAME, "body")
            
            # 링크에 URL 주소 추가
            add_links_to_text(driver, article_element)
            
            # 탭 처리 및 최종 텍스트 추출
            final_page_text = process_tabs_in_article(driver, article_element)
            
            # 파일명 생성
            path = url.split("?")[0].replace(BASE_URL, "")
            filename = re.sub(r'[/\\?%*:|"<>]', "_", path).strip("_") + ".txt"
            filepath = os.path.join(OUTPUT_DIR, filename)
            
            # 내용 구성
            content_to_save = f"Source URL: {url}\n\n{final_page_text}"
            
            # 파일 저장
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            
            file_size = len(content_to_save)
            print(f"✅ 저장 완료: {filename} ({file_size:,} 글자)")
            successful_count += 1
            
        except Exception as e:
            print(f"❌ 페이지 처리 오류: {url} - {e}")
            failed_count += 1
        
        # 서버 부하 방지를 위한 대기
        time.sleep(1.5)
    
    print("\n" + "=" * 70)
    print("🎉 크롤링 완료!")
    print("=" * 70)
    print(f"✅ 성공: {successful_count}개")
    print(f"❌ 실패: {failed_count}개")
    print(f"📁 저장 폴더: {OUTPUT_DIR}")
    print(f"📊 총 처리: {len(urls_to_crawl)}개")
    print("=" * 70)

except Exception as e:
    print(f"💥 치명적 오류 발생: {e}")

finally:
    try:
        if 'driver' in locals():
            driver.quit()
    except Exception as e:
        print(f"⚠️ 브라우저 종료 중 오류 (무시 가능): {e}")
    print("\n🔚 브라우저를 종료합니다.")
