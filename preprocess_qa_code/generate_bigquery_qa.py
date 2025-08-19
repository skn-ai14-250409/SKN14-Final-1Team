import os
import re
import json
from openai import OpenAI
from dotenv import load_dotenv
import time
from datetime import datetime

load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 파일이 저장된 디렉토리 경로
files_dir = "./bigquery_docs_crawled"
jsonl_filename = "generate_bigquery_qa.jsonl"

# API 호출 간 지연 시간 (초)
API_DELAY = 1


# 질문-답변 및 출처 생성 함수
def generate_qa_and_sources(text, filename):
    """BigQuery 문서를 바탕으로 QA 생성"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """주어진 BigQuery REST API 문서를 바탕으로 유용한 질문-답변과 해당 답변의 출처 URL을 찾아주세요.

**중요한 제약사항:**
- 문서에 명시된 내용만을 기반으로 질문과 답변을 작성하세요
- 문서에 없는 내용이나 추측, 일반적인 지식을 추가하지 마세요
- 답변은 반드시 문서 내용을 직접 참조해야 합니다
- 확실하지 않은 내용은 포함하지 마세요

**우선적으로 다룰 주제 (BigQuery 특화):**
1. BigQuery API 엔드포인트와 HTTP 메서드 사용법
2. 요청/응답 파라미터와 스키마 설명
3. 쿼리 작성 방법과 SQL 문법
4. 데이터셋, 테이블, 작업(job) 관리 방법
5. 인증, 권한, 할당량 관련 정보
6. 코드 예시와 구현 패턴
7. 오류 코드와 해결 방법
8. 성능 최적화와 비용 관리

**생성 규칙:**
- 문서에서 위 주제에 해당하는 내용이 충분히 있을 때만 질문-답변을 생성하세요
- API 레퍼런스 문서의 특성을 고려하여 기술적이고 구체적인 질문을 생성하세요
- 내용이 부족하거나 추상적인 설명만 있다면 "생성할 수 없음"이라고 응답하세요
- 최대 10개의 질문-답변을 생성하세요
- 각 질문-답변은 실용적이고 구체적이어야 합니다

**출처 URL 찾기 규칙:**
1. 문서 맨 위에 있는 Source URL (보통 https://cloud.google.com으로 시작)을 기본으로 포함
2. 답변 내용과 직접 관련된 특정 API 메서드나 리소스의 URL이 문서 내에 별도로 명시되어 있다면 추가로 포함
3. 내부 링크나 참조 링크가 답변과 관련이 있다면 포함
4. 문서에 실제로 존재하는 URL만 사용하세요

**응답 형식:**
질문1: [BigQuery API 사용에 대한 구체적인 질문]
답변1: [문서에 명시된 내용만으로 작성한 답변]
출처1: [문서 내에 실제로 존재하는 URL1, URL2, ...]

질문2: [두 번째 질문]
답변2: [두 번째 답변]
출처2: [URL1, URL2, ...]

(최대 10개까지)

만약 적절한 API 사용법, 파라미터 설명, 코드 예시가 문서에 충분히 없다면 "생성할 수 없음"이라고만 응답하세요.""",
                },
                {
                    "role": "user",
                    "content": f"다음 BigQuery REST API 문서를 정확히 분석해서, API 사용법, 파라미터, 코드 예시 등 실용적인 내용을 기반으로 최대 10개의 질문-답변과 해당 출처 URL들을 찾아주세요. 적절한 내용이 없다면 '생성할 수 없음'이라고 응답하세요:\n\n파일명: {filename}\n\n{text}",
                },
            ],
            max_tokens=2000,
            temperature=0,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  ❌ 질문-답변 생성 중 오류 발생: {e}")
        return None


def extract_urls_from_text(text):
    """텍스트에서 URL 추출"""
    # HTTP/HTTPS URL 패턴
    url_pattern = r'https?://[^\s\],;)\'"]+[^\s\],;)\'".]'
    urls = re.findall(url_pattern, text)

    # URL 정리 (끝에 붙은 특수문자 제거)
    cleaned_urls = []
    for url in urls:
        # 끝에 있는 구두점 제거
        url = re.sub(r"[.,;:)]+$", "", url)
        # 중복 제거
        if url not in cleaned_urls:
            cleaned_urls.append(url)

    return cleaned_urls


def parse_single_qa_block(block):
    """단일 질문-답변-출처 블록 파싱"""
    try:
        qa_dict = {}
        lines = block.strip().split("\n")

        current_section = None
        question_lines = []
        answer_lines = []
        source_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 질문 시작 패턴
            if re.match(r"^질문\d*:", line):
                current_section = "question"
                question_content = re.sub(r"^질문\d*:", "", line).strip()
                if question_content:
                    question_lines.append(question_content)

            # 답변 시작 패턴
            elif re.match(r"^답변\d*:", line):
                current_section = "answer"
                answer_content = re.sub(r"^답변\d*:", "", line).strip()
                if answer_content:
                    answer_lines.append(answer_content)

            # 출처 시작 패턴
            elif re.match(r"^출처\d*:", line):
                current_section = "sources"
                source_content = re.sub(r"^출처\d*:", "", line).strip()
                if source_content:
                    source_lines.append(source_content)

            # 연속되는 내용 라인
            else:
                if current_section == "question":
                    question_lines.append(line)
                elif current_section == "answer":
                    answer_lines.append(line)
                elif current_section == "sources":
                    source_lines.append(line)

        # 각 섹션 조합
        if question_lines:
            qa_dict["question"] = " ".join(question_lines).strip()

        if answer_lines:
            qa_dict["answer"] = " ".join(answer_lines).strip()

        # URL 추출
        if source_lines:
            all_source_text = " ".join(source_lines)
            urls = extract_urls_from_text(all_source_text)
            # BigQuery 관련 URL만 필터링
            bigquery_urls = [url for url in urls if 'bigquery' in url.lower() or 'cloud.google.com' in url]
            qa_dict["sources"] = bigquery_urls if bigquery_urls else urls if urls else ["출처를 찾을 수 없음"]
        else:
            qa_dict["sources"] = ["출처를 찾을 수 없음"]

        return qa_dict

    except Exception as e:
        print(f"  ⚠️ 단일 QA 블록 파싱 중 오류: {e}")
        return {}


def parse_qa_and_sources(ai_response):
    """개선된 질문-답변-출처 파싱 함수"""
    try:
        # "생성할 수 없음" 응답 체크
        if "생성할 수 없음" in ai_response:
            print("  → 적절한 내용이 없어서 질문-답변을 생성하지 않음")
            return []

        qa_pairs = []

        # 전체 텍스트를 질문 단위로 분할
        # 질문1:, 질문2: 등의 패턴으로 분할
        question_blocks = re.split(r"\n(?=질문\d*:)", ai_response.strip())

        for block in question_blocks:
            if not block.strip():
                continue

            # 각 블록에서 질문, 답변, 출처 추출
            qa_dict = parse_single_qa_block(block)
            if qa_dict and qa_dict.get("question") and qa_dict.get("answer"):
                # 데이터 정리
                cleaned_qa = {
                    "question": qa_dict["question"].strip(),
                    "answer": qa_dict["answer"].strip(),
                    "sources": qa_dict.get("sources", ["출처를 찾을 수 없음"]),
                }
                qa_pairs.append(cleaned_qa)

        return qa_pairs

    except Exception as e:
        print(f"  ⚠️ 응답 파싱 중 오류: {e}")
        return []


def categorize_content(filename, question):
    """파일명과 질문 내용을 기반으로 카테고리 분류"""
    categories = []

    filename_lower = filename.lower()
    question_lower = question.lower()

    # 파일명 기반 카테고리
    if 'datasets' in filename_lower:
        categories.append('datasets')
    if 'tables' in filename_lower:
        categories.append('tables')
    if 'jobs' in filename_lower:
        categories.append('jobs')
    if 'queries' in filename_lower:
        categories.append('queries')
    if 'models' in filename_lower:
        categories.append('models')
    if 'routines' in filename_lower:
        categories.append('routines')
    if 'projects' in filename_lower:
        categories.append('projects')

    # 질문 내용 기반 카테고리
    if 'dataset' in question_lower or '데이터셋' in question_lower:
        categories.append('datasets')
    if 'table' in question_lower or '테이블' in question_lower:
        categories.append('tables')
    if 'query' in question_lower or '쿼리' in question_lower or 'sql' in question_lower:
        categories.append('queries')
    if 'job' in question_lower or '작업' in question_lower:
        categories.append('jobs')
    if 'permission' in question_lower or 'iam' in question_lower or '권한' in question_lower:
        categories.append('permissions')
    if 'error' in question_lower or 'exception' in question_lower or '오류' in question_lower:
        categories.append('troubleshooting')

    # 중복 제거
    categories = list(set(categories))

    # 카테고리가 없으면 general 추가
    if not categories:
        categories = ['general']

    return categories


def validate_qa_pair(qa):
    """QA 쌍의 유효성 검증"""
    # 질문과 답변의 최소 길이 확인
    if len(qa['question']) < 10 or len(qa['answer']) < 20:
        return False

    # 답변이 단순히 "문서를 참조하세요" 같은 내용인지 확인
    unhelpful_patterns = [
        "문서를 참조",
        "자세한 내용은",
        "더 알아보려면",
        "참고하세요"
    ]

    answer_lower = qa['answer'].lower()
    if any(pattern in answer_lower for pattern in unhelpful_patterns) and len(qa['answer']) < 50:
        return False

    return True


# 메인 처리 함수
def main():
    jsonl_data = []
    total_files = 0
    processed_files = 0
    skipped_files = 0

    # 시작 시간 기록
    start_time = time.time()
    current_date = datetime.now().strftime("%Y-%m-%d")

    print("=" * 60)
    print("🚀 BigQuery API 문서 QA 생성 시작")
    print("=" * 60)

    # 파일 목록 가져오기
    txt_files = [f for f in os.listdir(files_dir) if f.endswith(".txt")]
    total_files = len(txt_files)

    print(f"📁 총 {total_files}개의 문서 파일 발견\n")

    for idx, filename in enumerate(txt_files, 1):
        file_path = os.path.join(files_dir, filename)
        print(f"[{idx}/{total_files}] 처리 중: {filename}")

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()

            # 파일 크기 확인
            file_size = len(text)
            if file_size < 500:
                print(f"  ⚠️ 파일이 너무 작음 ({file_size} 문자) - 건너뛰기")
                skipped_files += 1
                continue

            # 텍스트가 너무 길면 잘라내기 (토큰 제한 고려)
            if file_size > 15000:
                text = text[:15000]
                print(f"  📝 텍스트 길이 조정: {file_size} → 15000 문자")

            # AI가 질문-답변과 출처를 한 번에 생성
            ai_response = generate_qa_and_sources(text, filename)

            if ai_response:
                # AI 응답 파싱 (여러 개의 질문-답변 쌍)
                qa_pairs = parse_qa_and_sources(ai_response)

                if qa_pairs:
                    valid_qa_count = 0

                    for i, qa in enumerate(qa_pairs, 1):
                        # QA 유효성 검증
                        if not validate_qa_pair(qa):
                            print(f"    ⚠️ QA{i} 유효성 검증 실패 - 건너뛰기")
                            continue

                        # 카테고리 분류
                        categories = categorize_content(filename, qa["question"])

                        # 메타데이터 설정
                        metadata = {
                            "question": qa["question"],
                            "answer": qa["answer"],
                            "sources": qa["sources"],
                            "tags": "bigquery,rest-api",
                            "categories": categories,
                            "api_version": "v2",
                            "last_verified": current_date,
                            "source_file": filename,
                            "doc_type": "api_reference",
                            "language": "ko"
                        }

                        jsonl_data.append(metadata)
                        valid_qa_count += 1

                        # 진행 상황 출력 (첫 50자만)
                        print(f"    ✅ QA{i}: {qa['question'][:50]}...")
                        if len(qa['sources']) > 0 and qa['sources'][0] != "출처를 찾을 수 없음":
                            print(f"       출처: {qa['sources'][0][:60]}...")

                    if valid_qa_count > 0:
                        print(f"  → {valid_qa_count}개의 유효한 질문-답변 쌍 생성됨")
                        processed_files += 1
                    else:
                        print(f"  → 유효한 QA가 없어서 건너뛰기")
                        skipped_files += 1
                else:
                    print(f"  → 적절한 내용이 없어서 건너뛰기")
                    skipped_files += 1
            else:
                print(f"  ❌ AI 응답 실패")
                skipped_files += 1

        except Exception as e:
            print(f"  ❌ 파일 처리 중 오류: {e}")
            skipped_files += 1

        # API 호출 제한을 위한 지연
        if idx < total_files:
            time.sleep(API_DELAY)

    # JSONL 파일로 저장
    if jsonl_data:
        with open(jsonl_filename, "w", encoding="utf-8") as jsonl_file:
            for item in jsonl_data:
                jsonl_file.write(json.dumps(item, ensure_ascii=False) + "\n")

        # 처리 시간 계산
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)

        # 최종 통계 출력
        print("\n" + "=" * 60)
        print("📊 QA 생성 완료 통계")
        print("=" * 60)
        print(f"✅ 성공적으로 처리된 파일: {processed_files}개")
        print(f"⚠️ 건너뛴 파일: {skipped_files}개")
        print(f"📝 생성된 QA 쌍: {len(jsonl_data)}개")
        print(f"💾 저장된 파일: {jsonl_filename}")
        print(f"⏱️ 소요 시간: {minutes}분 {seconds}초")
        print("=" * 60)

        # 카테고리별 통계
        category_stats = {}
        for item in jsonl_data:
            for cat in item.get('categories', ['general']):
                category_stats[cat] = category_stats.get(cat, 0) + 1

        print("\n📊 카테고리별 QA 분포:")
        for cat, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {cat}: {count}개")

    else:
        print("\n⚠️ 생성된 QA가 없습니다. 문서 내용을 확인해주세요.")

    print("\n✨ 작업이 완료되었습니다!")


if __name__ == "__main__":
    # 환경 변수 확인
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ 오류: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("👉 .env 파일을 생성하고 다음과 같이 API 키를 추가하세요:")
        print("   OPENAI_API_KEY=your-api-key-here")
    elif not os.path.exists(files_dir):
        print(f"❌ 오류: '{files_dir}' 디렉토리가 존재하지 않습니다.")
        print("👉 먼저 BigQuery 문서 크롤링을 실행하세요.")
    else:
        main()