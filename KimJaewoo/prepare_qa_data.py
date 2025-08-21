#!/usr/bin/env python3
"""
크롤링한 텍스트 데이터를 QA 형식으로 변환하는 스크립트
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Tuple


class QADataPreparer:
    """크롤링 데이터를 QA 형식으로 변환"""

    def __init__(self, input_dir: str = "./crawler_code", output_dir: str = "./GOOGLE_API_DATA/GOOGLE_API_DATA_QA"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_qa_from_text(self, text: str) -> List[Dict[str, str]]:
        """텍스트에서 QA 쌍 추출"""
        qa_pairs = []

        # 방법 1: 섹션 기반 추출 (## 제목 형식)
        sections = re.split(r'\n##\s+', text)
        for section in sections:
            lines = section.strip().split('\n')
            if len(lines) >= 2:
                question = lines[0].replace('#', '').strip()
                answer = '\n'.join(lines[1:]).strip()
                if question and answer:
                    qa_pairs.append({
                        'question': question,
                        'answer': answer
                    })

        # 방법 2: 메서드 설명 패턴
        method_pattern = r'(\w+\.\w+\(\))[:\s]+(.*?)(?=\n\w+\.\w+\(\)|$)'
        matches = re.findall(method_pattern, text, re.DOTALL)
        for method, description in matches:
            qa_pairs.append({
                'question': f"{method} 메서드는 어떻게 사용하나요?",
                'answer': description.strip()
            })

        # 방법 3: 파라미터 설명 추출
        param_pattern = r'Parameters?:?\s*\n(.*?)(?=\n[A-Z]|\n\n|$)'
        param_matches = re.findall(param_pattern, text, re.DOTALL)
        for params in param_matches:
            qa_pairs.append({
                'question': "필요한 파라미터는 무엇인가요?",
                'answer': f"필요한 파라미터:\n{params.strip()}"
            })

        return qa_pairs

    def create_api_specific_qa(self, api_name: str, content: str) -> List[Dict[str, str]]:
        """API별 특화 QA 생성"""
        qa_list = []

        # Gmail API 관련
        if 'gmail' in api_name.lower():
            qa_list.extend([
                {
                    'question': "Gmail API로 이메일을 보내는 방법은?",
                    'answer': self._extract_method_info(content, 'messages.send')
                },
                {
                    'question': "Gmail API에서 라벨을 관리하는 방법은?",
                    'answer': self._extract_method_info(content, 'labels')
                }
            ])

        # Drive API 관련
        elif 'drive' in api_name.lower():
            qa_list.extend([
                {
                    'question': "Google Drive에서 파일을 검색하는 방법은?",
                    'answer': self._extract_method_info(content, 'files.list')
                },
                {
                    'question': "Drive API로 파일을 업로드하는 방법은?",
                    'answer': self._extract_method_info(content, 'files.create')
                }
            ])

        # Calendar API 관련
        elif 'calendar' in api_name.lower():
            qa_list.extend([
                {
                    'question': "Calendar API로 이벤트를 생성하는 방법은?",
                    'answer': self._extract_method_info(content, 'events.insert')
                },
                {
                    'question': "반복 이벤트를 설정하는 방법은?",
                    'answer': self._extract_recurrence_info(content)
                }
            ])

        # Sheets API 관련
        elif 'sheets' in api_name.lower():
            qa_list.extend([
                {
                    'question': "Sheets API로 데이터를 읽는 방법은?",
                    'answer': self._extract_method_info(content, 'values.get')
                },
                {
                    'question': "스프레드시트에 데이터를 쓰는 방법은?",
                    'answer': self._extract_method_info(content, 'values.update')
                }
            ])

        # 답변이 비어있는 항목 제거
        qa_list = [qa for qa in qa_list if qa['answer'] and qa['answer'] != "정보를 찾을 수 없습니다."]

        return qa_list

    def _extract_method_info(self, content: str, method_name: str) -> str:
        """특정 메서드 정보 추출"""
        # 메서드명 주변 텍스트 추출
        pattern = rf'{re.escape(method_name)}.*?(?:\n\n|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

        if match:
            extracted = match.group(0).strip()
            # 코드 예제 찾기
            code_pattern = r'```.*?```'
            code_match = re.search(code_pattern, content[match.start():match.end() + 500], re.DOTALL)
            if code_match:
                extracted += f"\n\n예제 코드:\n{code_match.group(0)}"
            return extracted

        return "정보를 찾을 수 없습니다."

    def _extract_recurrence_info(self, content: str) -> str:
        """반복 이벤트 정보 추출"""
        keywords = ['recurrence', 'RRULE', '반복', 'recurring']
        for keyword in keywords:
            if keyword in content:
                start = content.find(keyword)
                end = min(start + 500, len(content))
                return content[start:end].strip()
        return "반복 이벤트 설정 정보를 찾을 수 없습니다."

    def process_crawled_files(self):
        """크롤링된 파일들을 처리"""

        # 입력 디렉토리의 모든 텍스트 파일 처리
        for file_path in self.input_dir.glob("*.txt"):
            print(f"📄 처리 중: {file_path.name}")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 파일명에서 API 이름 추출
            api_name = file_path.stem

            # QA 추출
            qa_pairs = []

            # 1. 일반적인 QA 추출
            qa_pairs.extend(self.extract_qa_from_text(content))

            # 2. API 특화 QA 생성
            qa_pairs.extend(self.create_api_specific_qa(api_name, content))

            # 중복 제거
            unique_qa = []
            seen_questions = set()
            for qa in qa_pairs:
                if qa['question'] not in seen_questions:
                    unique_qa.append(qa)
                    seen_questions.add(qa['question'])

            # JSON 파일로 저장
            if unique_qa:
                output_file = self.output_dir / f"{api_name}_qa.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(unique_qa, f, ensure_ascii=False, indent=2)
                print(f"   ✅ {len(unique_qa)}개의 QA 쌍 저장: {output_file.name}")

    def create_sample_qa_data(self):
        """샘플 QA 데이터 생성"""
        sample_data = {
            "gmail_api_qa.json": [
                {
                    "question": "Gmail API 인증은 어떻게 설정하나요?",
                    "answer": """Gmail API 인증 설정 단계:

1. Google Cloud Console에서 프로젝트 생성
2. Gmail API 활성화
3. OAuth 2.0 클라이언트 ID 생성
4. 필요한 스코프 설정:
   - gmail.readonly: 읽기 전용
   - gmail.send: 이메일 전송
   - gmail.modify: 이메일 수정

예제 코드:
```python
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

creds = None
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

if not creds or not creds.valid:
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
```"""
                },
                {
                    "question": "첨부파일이 있는 이메일을 보내려면?",
                    "answer": """첨부파일 포함 이메일 전송:

```python
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

message = MIMEMultipart()
message['to'] = 'recipient@example.com'
message['subject'] = '첨부파일 테스트'

# 본문 추가
message.attach(MIMEText('첨부파일을 확인해주세요.', 'plain'))

# 파일 첨부
with open('document.pdf', 'rb') as file:
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(file.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="document.pdf"')
    message.attach(part)

# base64 인코딩 후 전송
raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
service.users().messages().send(userId='me', body={'raw': raw}).execute()
```"""
                }
            ],
            "drive_api_qa.json": [
                {
                    "question": "특정 폴더의 파일 목록을 가져오려면?",
                    "answer": """폴더 내 파일 목록 조회:

```python
def list_files_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed = false"

    results = service.files().list(
        q=query,
        pageSize=100,
        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)"
    ).execute()

    files = results.get('files', [])

    for file in files:
        print(f"Name: {file['name']}, ID: {file['id']}")

    return files
```

쿼리 옵션:
- mimeType='application/vnd.google-apps.folder': 폴더만
- name contains 'report': 이름에 'report' 포함
- modifiedTime > '2024-01-01': 특정 날짜 이후 수정"""
                },
                {
                    "question": "파일 공유 권한을 설정하는 방법은?",
                    "answer": """파일 공유 권한 설정:

```python
def share_file(service, file_id, email, role='reader'):
    '''
    role: 'reader', 'writer', 'commenter', 'owner'
    '''
    permission = {
        'type': 'user',
        'role': role,
        'emailAddress': email
    }

    try:
        service.permissions().create(
            fileId=file_id,
            body=permission,
            sendNotificationEmail=True
        ).execute()
        print(f"파일 공유 완료: {email}")
    except Exception as e:
        print(f"공유 실패: {e}")

# 링크로 공유
public_permission = {
    'type': 'anyone',
    'role': 'reader'
}
service.permissions().create(fileId=file_id, body=public_permission).execute()
```"""
                }
            ]
        }

        # 샘플 데이터 저장
        for filename, qa_list in sample_data.items():
            output_path = self.output_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(qa_list, f, ensure_ascii=False, indent=2)
            print(f"✅ 샘플 QA 데이터 생성: {output_path}")


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📚 Google API QA 데이터 준비 스크립트")
    print("=" * 60 + "\n")

    preparer = QADataPreparer()

    # 옵션 선택
    print("작업을 선택하세요:")
    print("1. 크롤링 데이터 처리 (crawler_code 폴더)")
    print("2. 샘플 QA 데이터 생성")
    print("3. 모두 실행")

    choice = input("\n선택 (1/2/3): ").strip()

    if choice == '1':
        if preparer.input_dir.exists():
            preparer.process_crawled_files()
        else:
            print(f"⚠️ {preparer.input_dir} 폴더가 없습니다.")

    elif choice == '2':
        preparer.create_sample_qa_data()

    elif choice == '3':
        if preparer.input_dir.exists():
            preparer.process_crawled_files()
        preparer.create_sample_qa_data()

    else:
        print("잘못된 선택입니다.")

    print("\n✅ 작업 완료!")


if __name__ == "__main__":
    main()