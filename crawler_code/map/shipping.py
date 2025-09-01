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
START_URL = "/maps/documentation/mobility?hl=ko"

# 저장할 폴더 이름
OUTPUT_DIR = "shipping"

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
    # 단일 URL 설정
    url = urljoin(BASE_URL, START_URL)
    print(f"🚀 페이지로 이동: {url}")
    driver.get(url)
    
    # 대기 객체 생성
    wait = WebDriverWait(driver, 15)
    
    # 페이지 로드 대기
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)
        print("✅ 페이지 로드 완료")
    except TimeoutException:
        print("⚠️ 페이지 로드 시간 초과, 계속 진행...")
    
    print("=" * 70)
    print(f"📄 크롤링 중: {url}")
    
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
    
    print("\n" + "=" * 70)
    print("🎉 크롤링 완료!")
    print("=" * 70)
    print(f"✅ 성공: 1개")
    print(f"📁 저장 폴더: {OUTPUT_DIR}")
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
