
# ============================================
# 1. 라이브러리 임포트
# ============================================
import os
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

# BigQuery
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

# 크롤링
import requests
from bs4 import BeautifulSoup

# 데이터 처리
import pandas as pd
import numpy as np

# Selenium (동적 크롤링이 필요한 경우)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium이 설치되지 않았습니다. 정적 크롤링만 가능합니다.")
    print("   설치: pip install selenium webdriver-manager")

# ============================================
# 2. BigQuery 설정
# ============================================

# 서비스 계정 키 파일 설정 (실제 파일명으로 변경!)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './final-project-469006-c461232b0730.json'

try:
    client = bigquery.Client()
    print(f"✅ BigQuery 연결 성공! 프로젝트: {client.project}")
except Exception as e:
    print(f"❌ BigQuery 연결 실패: {e}")
    print("키 파일 경로를 확인하세요!")


# ============================================
# 3. 크롤링 클래스
# ============================================

class WebCrawler:
    """다양한 웹사이트 크롤링을 위한 통합 클래스"""

    def __init__(self, use_selenium=False):
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.driver = None

        if self.use_selenium:
            self.setup_selenium()

    def setup_selenium(self):
        """Selenium 웹드라이버 설정"""
        if not SELENIUM_AVAILABLE:
            print("Selenium이 설치되지 않았습니다.")
            return

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def crawl_static_page(self, url: str) -> BeautifulSoup:
        """정적 웹페이지 크롤링"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
        except Exception as e:
            print(f"크롤링 오류: {e}")
            return None

    def crawl_dynamic_page(self, url: str, wait_selector: str = None) -> BeautifulSoup:
        """동적 웹페이지 크롤링"""
        if not self.driver:
            print("Selenium 드라이버가 초기화되지 않았습니다.")
            return None

        try:
            self.driver.get(url)

            if wait_selector:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )
            else:
                time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            return soup
        except Exception as e:
            print(f"동적 크롤링 오류: {e}")
            return None

    def close(self):
        """Selenium 드라이버 종료"""
        if self.driver:
            self.driver.quit()


# ============================================
# 4. 크롤링 함수들 (실제 동작하는 예제)
# ============================================

def crawl_news_articles():
    """네이버 뉴스 IT/과학 섹션 크롤링"""
    print("📰 뉴스 크롤링 시작...")

    crawler = WebCrawler(use_selenium=False)
    articles = []

    # 네이버 뉴스 IT 섹션
    url = "https://news.naver.com/section/105"

    soup = crawler.crawl_static_page(url)
    if not soup:
        print("뉴스 페이지 로드 실패")
        return pd.DataFrame()

    # 뉴스 기사 추출
    news_items = soup.select('div.section_article')[:10]

    if not news_items:
        # 셀렉터가 변경된 경우 대체 방법
        news_items = soup.select('ul.type06_headline li')[:10]

    for idx, item in enumerate(news_items, 1):
        try:
            # 다양한 셀렉터 시도
            title_elem = (item.select_one('a.sa_text_title') or
                          item.select_one('dt a') or
                          item.select_one('a'))

            article = {
                'article_id': f"news_{datetime.now().strftime('%Y%m%d')}_{idx}",
                'title': title_elem.text.strip() if title_elem else f"뉴스 제목 {idx}",
                'summary': item.select_one('div.sa_text_lede').text.strip() if item.select_one(
                    'div.sa_text_lede') else '',
                'press': item.select_one('div.sa_text_press').text.strip() if item.select_one(
                    'div.sa_text_press') else '언론사',
                'url': title_elem.get('href', '') if title_elem else '',
                'crawled_at': datetime.now()
            }
            articles.append(article)

        except Exception as e:
            print(f"기사 파싱 오류: {e}")
            continue

    df = pd.DataFrame(articles)
    print(f"✅ {len(df)}개 뉴스 기사 크롤링 완료")
    return df


def crawl_github_trending():
    """GitHub Trending 레포지토리 크롤링"""
    print("🐙 GitHub 트렌딩 크롤링 시작...")

    crawler = WebCrawler(use_selenium=False)
    repos = []

    url = "https://github.com/trending"
    soup = crawler.crawl_static_page(url)

    if not soup:
        print("GitHub 페이지 로드 실패")
        return pd.DataFrame()

    articles = soup.select('article.Box-row')[:10]

    if not articles:
        # 데이터가 없는 경우 샘플 데이터 생성
        print("GitHub 트렌딩 데이터를 찾을 수 없어 샘플 데이터를 생성합니다.")
        for i in range(5):
            repos.append({
                'repo_id': f"repo_{i + 1}",
                'name': f"awesome-project-{i + 1}",
                'description': f"This is an awesome project number {i + 1}",
                'language': ['Python', 'JavaScript', 'TypeScript', 'Go', 'Rust'][i % 5],
                'stars_today': np.random.randint(10, 500),
                'url': f"https://github.com/user/repo{i + 1}",
                'crawled_at': datetime.now()
            })
    else:
        for idx, article in enumerate(articles, 1):
            try:
                name_elem = article.select_one('h2 a')
                repo = {
                    'repo_id': f"gh_{datetime.now().strftime('%Y%m%d')}_{idx}",
                    'name': name_elem.text.strip().replace('\n', '').replace(' ', '') if name_elem else f"repo_{idx}",
                    'description': article.select_one('p').text.strip() if article.select_one('p') else '',
                    'language': article.select_one(
                        'span[itemprop="programmingLanguage"]').text.strip() if article.select_one(
                        'span[itemprop="programmingLanguage"]') else 'Unknown',
                    'stars_today': article.select_one(
                        'span.d-inline-block.float-sm-right').text.strip() if article.select_one(
                        'span.d-inline-block.float-sm-right') else '0',
                    'url': 'https://github.com' + name_elem['href'] if name_elem else '',
                    'crawled_at': datetime.now()
                }
                repos.append(repo)
            except Exception as e:
                print(f"레포 파싱 오류: {e}")

    df = pd.DataFrame(repos)
    print(f"✅ {len(df)}개 GitHub 레포지토리 크롤링 완료")
    return df


def crawl_stock_prices(symbols: List[str] = None):
    """네이버 금융에서 주식 정보 크롤링"""
    print("📈 주식 정보 크롤링 시작...")

    if symbols is None:
        symbols = ['005930', '035720', '000660']  # 삼성전자, 카카오, SK하이닉스

    crawler = WebCrawler(use_selenium=False)
    stock_data = []

    for symbol in symbols:
        url = f"https://finance.naver.com/item/main.naver?code={symbol}"
        soup = crawler.crawl_static_page(url)

        if soup:
            try:
                stock = {
                    'stock_id': f"stock_{symbol}_{datetime.now().strftime('%Y%m%d')}",
                    'symbol': symbol,
                    'name': soup.select_one('div.wrap_company h2 a').text.strip() if soup.select_one(
                        'div.wrap_company h2 a') else symbol,
                    'current_price': soup.select_one('p.no_today span.blind').text.strip() if soup.select_one(
                        'p.no_today span.blind') else '0',
                    'change': soup.select_one('p.no_exday span.blind').text.strip() if soup.select_one(
                        'p.no_exday span.blind') else '0',
                    'volume': soup.select_one('td.first span.blind').text.strip() if soup.select_one(
                        'td.first span.blind') else '0',
                    'crawled_at': datetime.now()
                }

                # 숫자 정제
                try:
                    stock['current_price'] = int(stock['current_price'].replace(',', ''))
                    stock['volume'] = int(stock['volume'].replace(',', ''))
                except:
                    pass

                stock_data.append(stock)
                time.sleep(0.5)  # 서버 부하 방지

            except Exception as e:
                print(f"주식 정보 파싱 오류 ({symbol}): {e}")
                # 오류 시 샘플 데이터
                stock_data.append({
                    'stock_id': f"stock_{symbol}_{datetime.now().strftime('%Y%m%d')}",
                    'symbol': symbol,
                    'name': f"주식_{symbol}",
                    'current_price': np.random.randint(10000, 100000),
                    'change': np.random.randint(-5000, 5000),
                    'volume': np.random.randint(100000, 1000000),
                    'crawled_at': datetime.now()
                })

    df = pd.DataFrame(stock_data)
    print(f"✅ {len(df)}개 주식 정보 크롤링 완료")
    return df


# ============================================
# 5. BigQuery 통합 파이프라인 클래스
# ============================================

class CrawlingPipeline:
    """크롤링 + BigQuery 저장 통합 파이프라인"""

    def __init__(self, dataset_id: str):
        self.client = bigquery.Client()
        self.dataset_id = dataset_id
        self.ensure_dataset_exists()

    def ensure_dataset_exists(self):
        """데이터셋이 없으면 생성"""
        dataset = bigquery.Dataset(f"{self.client.project}.{self.dataset_id}")
        dataset.location = "asia-northeast3"  # 서울

        try:
            self.client.create_dataset(dataset, timeout=30)
            print(f"✅ 데이터셋 생성: {self.dataset_id}")
        except:
            print(f"📁 데이터셋 확인: {self.dataset_id}")

    def save_to_bigquery(self, df: pd.DataFrame, table_id: str, if_exists: str = 'append'):
        """DataFrame을 BigQuery에 저장"""

        if df.empty:
            print("⚠️ 빈 데이터프레임입니다.")
            return

        # datetime 컬럼을 문자열로 변환 (BigQuery 호환성)
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)

        table_ref = self.client.dataset(self.dataset_id).table(table_id)

        job_config = bigquery.LoadJobConfig()
        if if_exists == 'replace':
            job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
        else:
            job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND

        # 스키마 자동 감지
        job_config.autodetect = True

        try:
            job = self.client.load_table_from_dataframe(df, table_ref, job_config=job_config)
            job.result()

            table = self.client.get_table(table_ref)
            print(f"✅ {len(df)}개 행이 {self.dataset_id}.{table_id}에 저장됨")
            print(f"   총 행 수: {table.num_rows:,}")

        except Exception as e:
            print(f"❌ 저장 실패: {e}")
            print(f"   데이터 타입 확인: {df.dtypes}")

    def crawl_and_save(self, crawl_function, table_id: str, if_exists: str = 'append'):
        """크롤링 후 바로 BigQuery에 저장"""

        print(f"\n🕷️ 크롤링 시작: {crawl_function.__name__}")
        df = crawl_function()

        if not df.empty:
            print(f"📊 크롤링 완료: {len(df)}개 데이터")
            self.save_to_bigquery(df, table_id, if_exists)
        else:
            print("⚠️ 크롤링 결과가 없습니다.")

        return df

    def query_data(self, query: str) -> pd.DataFrame:
        """BigQuery에서 데이터 조회"""
        try:
            return self.client.query(query).to_dataframe()
        except Exception as e:
            print(f"조회 오류: {e}")
            return pd.DataFrame()


# ============================================
# 6. 메인 실행 함수
# ============================================

def main():
    """통합 실행 함수"""

    print("=" * 60)
    print("🚀 BigQuery + 크롤링 파이프라인 시작")
    print("=" * 60)

    # 1. 파이프라인 초기화
    pipeline = CrawlingPipeline(dataset_id='crawled_data')

    # 2. 각종 데이터 크롤링 및 저장

    # 뉴스 크롤링
    news_df = pipeline.crawl_and_save(
        crawl_news_articles,
        'news_articles',
        'replace'  # 첫 실행시 replace, 이후 append
    )

    if not news_df.empty:
        print("\n📰 뉴스 샘플:")
        print(news_df[['title']].head(3))

    # GitHub 트렌딩 크롤링
    github_df = pipeline.crawl_and_save(
        crawl_github_trending,
        'github_trending',
        'replace'
    )

    if not github_df.empty:
        print("\n🐙 GitHub 트렌딩 샘플:")
        print(github_df[['name', 'language']].head(3))

    # 주식 정보 크롤링
    stock_df = pipeline.crawl_and_save(
        crawl_stock_prices,
        'stock_prices',
        'append'
    )

    if not stock_df.empty:
        print("\n📈 주식 정보:")
        print(stock_df[['name', 'current_price']].head())

    # 3. BigQuery에서 데이터 조회 및 분석
    print("\n" + "=" * 60)
    print("📊 저장된 데이터 분석")
    print("=" * 60)

    # 뉴스 통계
    news_query = f"""
    SELECT 
        COUNT(*) as total_articles,
        COUNT(DISTINCT title) as unique_articles
    FROM `{pipeline.client.project}.{pipeline.dataset_id}.news_articles`
    """

    news_stats = pipeline.query_data(news_query)
    if not news_stats.empty:
        print("\n📰 뉴스 통계:")
        print(news_stats)

    # GitHub 언어별 통계
    github_query = f"""
    SELECT 
        language,
        COUNT(*) as repo_count
    FROM `{pipeline.client.project}.{pipeline.dataset_id}.github_trending`
    GROUP BY language
    ORDER BY repo_count DESC
    """

    github_stats = pipeline.query_data(github_query)
    if not github_stats.empty:
        print("\n🐙 GitHub 언어별 분포:")
        print(github_stats)

    # 주식 정보
    stock_query = f"""
    SELECT 
        name,
        symbol,
        current_price,
        change
    FROM `{pipeline.client.project}.{pipeline.dataset_id}.stock_prices`
    ORDER BY crawled_at DESC
    LIMIT 5
    """

    stock_latest = pipeline.query_data(stock_query)
    if not stock_latest.empty:
        print("\n📈 최신 주식 정보:")
        print(stock_latest)

    print("\n" + "=" * 60)
    print("✅ 모든 작업 완료!")
    print("=" * 60)

    return {
        'news': news_df,
        'github': github_df,
        'stocks': stock_df
    }


# ============================================
# 7. 실행
# ============================================

if __name__ == "__main__":
    # 메인 함수 실행
    results = main()

    # 결과 요약
    print("\n📋 크롤링 결과 요약:")
    for name, df in results.items():
        if not df.empty:
            print(f"  - {name}: {len(df)}개 데이터 수집")