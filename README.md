# 🚀 SK네트웍스 Family AI 과정 14기 1팀 - Final Project

## **❇️ 프로젝트명 : CodeNova**  
LLM 활용 내부 고객 업무 효율성 향상을 위한 API 전문 사내 개발자 지원 AI 기반 문서 검색 시스템  

---


## 🙌 팀원
- 김준기 · 김재우 · 안윤지 · 이나경 · 이원지희 · 정민영

---

## 📌 프로젝트 개요
API 문서는 방대한 문서와 복잡한 구조로 인해 개발자가 필요한 정보를 신속하게 찾기 어렵습니다.  

본 프로젝트는 **RAG + LLM 기반 문서 검색 시스템**을 구축하여 내부 개발자의 **검색 효율성**과 **업무 생산성**을 높이는 것을 목표로 합니다.  

이 시스템은 아래와 같이 크게 **API 전문 어시스턴트**과 **사내 내부 문서 전문 SLLM 챗봇**으로 구성됩니다.  

- **API 전문 어시스턴트**:  
  - **OpenAI GPT-4o 기반 챗봇**
  > API Q&A, 예제 코드, 오류 해결 등 **API 문서에 대한 전반적인 질의응답**을 지원하는 챗봇. 사용자가 질문을 입력하면 관련 문서를 벡터 DB에서 검색하여 최적의 답변을 제공합니다.  

  - **API 문서 원문 검색**:  
  > 사용자가 입력한 검색어에 대한 **의미 기반 검색**을 통해 API 문서 원문 링크를 빠르게 찾을 수 있는 기능. 
  > 
  > 사용자가 특정 키워드나 의미를 입력하면 관련 원문 링크를 제공하여 구체적인 정보에 쉽게 접근할 수 있게 합니다.  

- **사내 내부 문서 전문 sLLM 챗봇**:  
  > 사내 정책·규정·기술 자료를 검색할 수 있으며, **권한 기반 보안 필터**를 적용해 사용자의 직급과 부서에 맞는 문서만 열람 가능하도록 합니다.
  >
  > 또한, **사내 전용 말투·용어·보고체계**를 반영하여 내부 직원들이 친숙하고 실질적인 도움을 받을 수 있도록 최적화된 대화 경험 제공합니다.
  > 
  > 그리고 사용자가 공손/친구 말투 중 선택할 수 있도록 하여, 원하는 형태의 챗봇 응답을 받을 수 있도록 하는 사용자 경험을 제공합니다. 


---

## 📊 시장 조사 및 BM
### 시장 규모
- **글로벌 AI 소프트웨어 시장**: 2028년 6,788억 달러 전망  
- **국내 AI 산업**: 2024년 6조 3,000억 원 (응용 소프트웨어 2조 6,700억 원, 최대 비중)

### 타겟 고객
- API(구글 등)를 활용하는 **사내 개발자 / 엔지니어**
- API 연관 서비스 및 연동 솔루션 관련 부서

### 비즈니스 모델 (BM)
- **구독형 라이선스**: 월/연 단위 과금, 기능별·사용자 수 차등 요금제
- **엔터프라이즈 계약**: 맞춤형 데이터 연동, 기술 지원 포함  

---

## ⚙️ 기술 스택

| 항목                  | 내용                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|:--------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Frontend**        | ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white) ![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white) ![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white) ![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black) |
| **Backend**         | ![Django](https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![Gunicorn](https://img.shields.io/badge/Gunicorn-6DA55F?style=for-the-badge&logo=gunicorn&logoColor=white) ![Uvicorn](https://img.shields.io/badge/Uvicorn-FFA500?style=for-the-badge&logo=uvicorn&logoColor=white) |
| **DB**              | ![MySQL](https://img.shields.io/badge/MySQL-4479A1?style=for-the-badge&logo=mysql&logoColor=white) ![Chroma](https://img.shields.io/badge/Chroma-4B8BEA?style=for-the-badge&logo=python&logoColor=white)                                                                                                                                                                                                                            |
| **Infra**           | ![AWS](https://img.shields.io/badge/Amazon%20AWS-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white) ![S3](https://img.shields.io/badge/Amazon%20S3-569A31?style=for-the-badge&logo=amazons3&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![Nginx](https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white) ![RunPod](https://img.shields.io/badge/RunPod-FF4500?style=for-the-badge&logo=cloudflare&logoColor=white) ![vLLM](https://img.shields.io/badge/vLLM-000000?style=for-the-badge&logo=lightning&logoColor=white) |
| **CI/CD**           | ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white) ![AWS Elastic Beanstalk](https://img.shields.io/badge/AWS%20Elastic%20Beanstalk-232F3E?style=for-the-badge&logo=amazon-aws&logoColor=white)                                                                                                                                                         |
| **Embedding Model** | ![BGE-M3](https://img.shields.io/badge/BGE--M3-000000?style=for-the-badge&logo=huggingface&logoColor=white)                                                                                                                                                                                                                                                                                                                         |
| **LLM Model**       | ![GPT-4](https://img.shields.io/badge/GPT--4-4B91FF?style=for-the-badge&logo=openai&logoColor=white) ![Qwen3-8B](https://img.shields.io/badge/Qwen3--8B%20(on%20RunPod%20+%20vLLM)-FF6F00?style=for-the-badge&logo=alibabacloud&logoColor=white) |
| **Orchestration**   | ![LangGraph](https://img.shields.io/badge/LangGraph-1E90FF?style=for-the-badge&logo=graphviz&logoColor=white) ![LangChain](https://img.shields.io/badge/LangChain-2E8B57?style=for-the-badge&logo=chainlink&logoColor=white) |
| **Collaboration**   | ![Git](https://img.shields.io/badge/Git-F05032?style=for-the-badge&logo=git&logoColor=white) ![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white) ![Notion](https://img.shields.io/badge/Notion-000000?style=for-the-badge&logo=notion&logoColor=white) ![Discord](https://img.shields.io/badge/Discord-7289DA?style=for-the-badge&logo=discord&logoColor=white) |
| **Development**     | ![VS Code](https://img.shields.io/badge/VS%20Code-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white) ![PyCharm](https://img.shields.io/badge/PyCharm-000000?style=for-the-badge&logo=pycharm&logoColor=white) |

---

## ⚙️ 시스템 아키텍처

> 본 시스템은 Django 기반 웹 애플리케이션, FastAPI 서비스, LLM(OpenAI GPT-4), sLLM(Qwen3-8B 파인튜닝 모델)로 구성됩니다.  
> 
> 대부분의 애플리케이션은 **AWS Elastic Beanstalk** 환경에서 **Docker 컨테이너** 형태로 배포됩니다.  
> 
> 다만, **MySQL DB는 별도의 AWS EC2 인스턴스** 위에서 Docker 컨테이너로 운영됩니다.  

---

### 🔹 주요 구성 요소

1. **웹 애플리케이션 계층**
   - **Django (Gunicorn/Uvicorn)**: 메인 백엔드 프레임워크, OpenAI GPT-4 API 연동
   - **Nginx Proxy + Application Load Balancer (ALB)**: 외부 요청을 HTTPS/HTTP로 수신 후 Django 컨테이너로 전달
   - **AWS Route53**: 도메인 관리 및 HTTPS 라우팅 (`https://code-nova.dev`, `http://sllm.code-nova.site`)

2. **데이터베이스 계층**
   - **MySQL (별도 AWS EC2 인스턴스 내 Docker 컨테이너)**: 사용자 계정 정보, 채팅 내역, 커뮤니티 내용 등 저장
   - **Chroma Vector DB**: 챗봇 RAG 검색용 벡터 데이터베이스

3. **스토리지 계층**
   - **AWS S3**: 채팅 이미지, 프로필 이미지 파일 저장소

4. **AI 모델 계층**
   - **LLM (OpenAI GPT-4)**: 주 대화 모델로서 범용적인 질의응답 처리
   - **sLLM (Qwen3-8B Fine-tuned, RunPod + vLLM)**: 파인튜닝된 도메인 특화 모델, RunPod GPU 환경에서 vLLM을 통해 서빙  
   - **FastAPI 서비스**: sLLM inference API 제공 (Nginx Proxy와 연동)

5. **CI/CD 파이프라인**
   - **GitHub → DockerHub → AWS EB**
   - 로컬 개발(예: PyCharm) 후 GitHub에 Push
   - `main` 브랜치 Merge 시 **GitHub Actions**가 Docker Image를 빌드 및 DockerHub에 업로드
   - Elastic Beanstalk이 최신 이미지를 Pull 받아 자동 배포
---

### [**아키텍처 다이어그램**]

<img width="1100" alt="시스템 아키텍처" src="https://github.com/user-attachments/assets/05f357ed-9120-4b1b-a99c-e1e7af3b46a6" />

---

## ✔️ 주요 기능

### **🌎 구글 API 전문 어시스턴트**

- **OpenAI GPT-4 기반 멀티모달 챗봇**:  
  > 구글 API Q&A, 예제 코드, 오류 해결 등 **구글 API 문서 전반에 대한 질의응답**을 지원합니다.  
  > 텍스트 입력뿐 아니라 **오류 코드 스니펫**이나 **API 관련 캡처 이미지**도 인식하여,  
  > **API 사용법 / 오류 해결법 / 예시 코드**를 함께 제공합니다.  
  > 또한 **이전 대화 맥락**을 반영하여 연속적인 대화에서도 정확한 답변을 유지합니다.  

- **API 질문 분기 처리**:  
  > 입력된 질문 유형에 따라 효율적으로 분기 처리합니다.  
  > - **API 관련 질문** → 문서 검색 + GPT-4 기반 응답  
  > - **일상 대화** → 일반 대화 모드로 응답  
  > - **지원하지 않는 질문(예: GitFlow, 사내 업무 질문 등)** → "지원 범위 외 질문"으로 안내  

- **음성 입력 지원 (Whisper 연동)**:  
  > OpenAI **Whisper 모델**을 연동하여, 사용자의 **음성 입력을 실시간으로 텍스트 변환**하고  
  > 변환된 내용을 기반으로 질의응답을 수행합니다.  

- **구글 API 문서 검색 기능**:  
  > **의미 기반 검색**을 통해 관련된 문서 원문을 빠르게 찾아 답변에 반영합니다.  
  > 검색된 문서 중 **가장 유사도가 높은 Top N개 문서**를 사용자에게 제공하며,  
  > **N 값은 사용자가 직접 조절 가능**합니다.  
  > 또한 관련 원문 링크를 함께 제공하여, 세부 정보를 쉽게 확인할 수 있도록 지원합니다.

### **🧑‍💼 사내 문서 sLLM 챗봇**

- **모델 및 학습 특성**:  
  > **Qwen3-8B 모델**을 **LoRA 방식으로 파인튜닝**하여 구축된 챗봇입니다.  
  > 학습 과정에서 **일상 대화**, **문서 검색 질의응답(RAG)**, **말투(공손/반말)**뿐만 아니라  
  > **멀티턴 TOOL CALL 패턴**까지 반영하여, 대화 맥락을 고려한 자연스러운 응답이 가능합니다.  
  > 사용자가 원하는 말투를 선택할 수 있도록 지원합니다.  

- **내부 문서 검색 및 응답**:  
  > **사내 문서 검색**과 관련된 질문은 **RAG 기반 검색**을 통해 정확한 답변을 제공합니다.  
  > 이 과정에서 **직급 및 권한에 따른 문서 접근 제어**를 적용해 보안이 강화된 검색 환경을 보장합니다.  

- **일상 대화 응답**:  
  > 사내 문서 검색 이외의 **일상 질문**에 대해서는, 파인튜닝된 **Qwen3-8B 모델 자체**의 대화 능력을 활용하여 응답합니다.  

- **커뮤니케이션 톤**:  
  > **사내 말투와 용어**를 반영해 조직 내부 커뮤니케이션에 맞는 톤과 스타일로 응답하며,  
  > 사용자 선택에 따라 **공손한 말투**와 **반말 톤** 모두 자연스럽게 지원합니다.


---

### **⚙️ 부가기능**

- **대화 카드 저장**:  
  > 팀 내에서 중요한 **코드 자산**이나 **API 사용 예시** 등을 **대화 카드**로 저장할 수 있습니다.  
  > 저장된 카드는 **마이페이지에서 확인 가능**하며, **채팅 보러가기** 기능을 통해 해당 카드가 속한 대화 세션으로 바로 이동할 수 있습니다.  
  > 이를 통해 팀 내 지식 관리와 코드 자산 공유가 촉진되어 업무 효율성을 높입니다.  

- **API 키 관리**:  
  > API 키를 **저장, 수정, 삭제, 복사**할 수 있는 기능입니다.  
  > 사용자는 자신의 API 키를 손쉽게 관리할 수 있습니다.

- **커뮤니티**:  
  > 사용자들이 **코드 예제, API 사용법, 문제 해결**뿐 아니라 **일상적인 주제**에 대해서도 자유롭게 의견을 나눌 수 있는 커뮤니티 기능을 제공합니다.  
  > 이를 통해 개발자 간의 정보 공유는 물론, 친목 도모와 소통의 장으로도 활용할 수 있습니다.  
  > 커뮤니티 내 **베스트 게시글**은 별도로 선별되어 게시판 상단에 노출됩니다.


---

## ♒ 프로젝트 User-Flow

![img_2.png](image/userflow.png)

### 🧭 유저 플로우 정리

1. **회원가입 및 승인**
   - 신규 유저는 회원가입 후 `status: pending` 상태로 등록
   - 관리자가 승인해야 로그인 가능

2. **메인 내비게이션: 로그인 후 유저는 네 가지 주요 기능을 이용할 수 있음**
   - **API 챗봇 (API Q&A)**
   - **사내 문서 검색 sLLM**
   - **마이페이지 (키 관리 / 카드 관리 / 내 정보 수정)**
   - **커뮤니티 Q&A**

3. **API 챗봇 (API Q&A)**
   - 입력: 이미지 / 음성 / 텍스트
   - 관련 문서 검색 (RAG) 및 응답 생성
   - 답변 생성 후 대화 내용 표시
   - 유저가 원하는 경우 **대화 카드 저장** 가능
   - 저장된 카드는 마이페이지에서 확인 및 재접속 가능

4. **사내 문서 검색 sLLM**
   - 직급 및 권한 확인 후 문서 검색 가능
   - RAG 기반 문서 답변 및 대화 내용 표시
   - 필요 시 **대화 카드 자동 저장** 기능 지원

5. **마이페이지**
   - **API 키 관리** (등록 / 수정 / 삭제 / 복사)
   - **대화 카드 관리** (목록 확인, 선택 시 해당 세션으로 이동)
   - **내 정보 수정** 가능

6. **커뮤니티 Q&A**
   - 질문, 답변, 댓글, 좋아요 기능 제공
   - **베스트 게시글**은 커뮤니티 상단에 노출
   - 개발/코드뿐 아니라 **일상 관련 주제**도 지원 → 친목 도모 가능


## 🧠 모델링 계획

### 1. **메인 챗봇 & RAG 시스템**
- **메인 챗봇**: **OpenAI GPT-4o** 모델을 기반으로 구글 API Q&A, 코드 예시, 오류 해결 등을 지원합니다.
- **벡터 DB**: **Chroma Vector DB**를 사용하여 구글 API 문서와 관련된 데이터를 벡터화하여 저장
- **RAG 시스템**: **벡터화된 데이터**를 기반으로 메인 챗봇이 더 정확한 답변을 제공합니다.

####  <**QA셋 전처리 방식**>
- **기존 방식**: 한 문서 내 최대 10개 QA셋 생성.
- **청킹 및 페어 방식**: 문서 내 청킹(단락, 문장) 및 페어(청크 쌍) 방식으로 QA셋을 구성. 각 페어당 최대 5개 QA 생성하며 이전 페어에서 나온 질문과 내용이 동일한 질문은 생성하지 않도록 함.
- **전처리 방식별 QA셋 평가**: 핵심 포인트가 각 QA셋에 얼마나 반영되었는지 **GPT 모델**로 평가.
  - **반영됨**: 1점, **부분반영**: 0.5점, **누락됨**: 0점
  - **결과**: **95% 커버율** vs (기존 방식 75%)

#### <**성능 비교: QA셋 방식 vs 원문 데이터 방식**> (이후 비교 예정)
- **QA셋 방식**: 코드와 중요한 내용은 잘 보존할 수 있지만, 문서 전체 내용을 **커버하기 어려울 수 있습니다**. 청킹 및 페어 방식으로 **누락을 최소화**할 수 있지만, **문서의 전체 맥락**을 포괄하는 데 한계가 있을 수 있습니다.
- **원문 데이터 방식**: **문서 전체 내용**을 포함할 수 있어 맥락이 잘 유지되지만, **청킹 과정**에서 코드나 중요한 부분이 잘릴 수 있으며, 검색 성능이 떨어질 가능성도 있습니다.
- **향후 계획**: 두 가지 방식의 벡터 DB를 **개별적으로** 테스트하고, **두 방식 결합**을 통한 성능 비교 및 최적화도 진행할 예정입니다.


### <**지속적 개선 예정 사항**>
- **최신 api문서 크롤링을 주기적으로 진행하는 자동화 파이프라인 구축**을 통해서, api문서가 수정된 경우에도 rag 챗봇이 최신 문서 내용을 반영하여 답변할 수 있도록 개선
- **커뮤니티 고품질 답변**을 벡터 DB에 주기적으로 반영하여 챗봇 성능 지속 개선


---
### 2. **사내 문서 sLLM (권한 기반 검색 + 파인튜닝 + Chroma Vector DB)**

<**모델**>: **QWEN 8B** 모델을 기반으로 사내 문서에 대한 질의응답 시스템을 구축할 예정입니다.
  - **파인튜닝**: 사내 문서에 특화된 **멀티턴 데이터셋**을 생성하여 모델을 최적화하며, 사내의 고유한 문서 말투까지 모델이 학습하도록 합니다.

#### <**사내 문서 말투 학습 데이터 생성 프로세스**> (예상 프로세스로 설계 필요)
1. **문서 임베딩 및 벡터화**: 
   - 사내 문서를 임베딩하여 **벡터 DB**에 저장.  
   - 검색 기반 **RAG 환경** 구축을 위한 데이터 준비.

2. **질문 후보 생성**:  
   - **GPT-4**를 활용하여, 사내 문서를 순회하며 **실제 발생할 만한 질문**을 생성.

3. **1차 RAG 응답 생성**:  
   - 생성된 질문을 바탕으로 **벡터 DB**에서 **관련 컨텍스트**를 검색하고, **GPT-4**로 **첫 번째 답변**을 생성.

4. **멀티턴 질문 확장**:  
   - 첫 번째 질문/답변을 바탕으로 **연결 질문**을 **GPT-4**로 생성.
   - 이전 질문/답변/컨텍스트와 새 질문을 묶어 **2차 RAG 검색** 후 멀티턴 답변을 생성.

5. **대화형 데이터셋 구성**:  
   - **질문1 / CONTEXT1 / 답변1 / 질문2 / CONTEXT2 / 답변2** 형태로 **멀티턴 데이터셋** 구성.

6. **말투 적용**:  
   - **사내 문서의 말투**를 **프롬프트**에 반영하여 학습 데이터를 **실제 서비스 말투**로 변환.

#### <**RAG 기반 성능 최적화 예정**>
- **청킹된 사내 문서 벡터화 및 RAG 적용**: 원문을 **청킹하여 벡터 DB에 저장**하고, **RAG**로 컨텍스트를 제공하여 검색 성능을 최적화합니다.

---

## 📂 사용 데이터

- **외부 데이터**  
  - **Google API 공식 문서** (Drive, Sheets, Gmail, Maps, YouTube, Firebase, BigQuery 등 총 11개 API)  
    - **수집 방식**: 웹 크롤링 → 텍스트 추출 → 텍스트 파일 저장  
    - **내용**: 구글의 각종 API 공식 문서에서 필요한 데이터를 크롤링하여 수집. 각 문서의 구조와 내용에 맞춰 텍스트를 추출하고, 각 API 문서가 담고 있는 사용법, 예제 코드, 오류 해결법 등을 포함.  
    - **수집 데이터 양**: 약 2000개 문서 (txt 형식)

  - **Google API QA 문서**  
    - **수집 방식**: 구글 API 문서를 기반으로 Q&A 데이터셋 생성 (질문과 답변을 추출하여 JSONL 형식으로 저장)  
    - **내용**: 각 API 문서에서 중요한 정보나 사용자들이 자주 묻는 질문을 기반으로 **QA셋**을 생성. 이 데이터셋은 API 사용법, 오류 해결 방안 등을 중심으로 구성.  
    - **수집 데이터 양**: 아직 전체 문서에 대한 Q&A 데이터셋 생성 전 단계 (약 15000 ~ 20000개 정도의 QA셋이 생성될 것으로 예상)

- **내부 데이터**  
  - **사내 정책/규정 문서**  
    - **수집 방식**: OpenAI API 프롬프트 합성 → 텍스트 파일 저장  
    - **내용**: 사내 정책, 규정, 기술 매뉴얼 등 사내 문서들을 프롬프트 합성을 통해 생성하여 수집. 각 직급별(사원, 대리, 과장, 부장, 사장)로 문서 구조와 내용이 달라지며, 이를 바탕으로 텍스트 파일을 생성.  
    - **수집 데이터 양**: 직급별로 10개씩 총 50개 문서 (txt 형식)


---

## 🔀 ERD
> 아래 **ERD (Entity-Relationship Diagram)**는 **사용자 관리**, **채팅 세션**, **카드 관리**, **메시지 기록** 등을 포함한 주요 테이블 구조를 보여줍니다. 각 테이블은 다음과 같이 연결됩니다:

![img.png](image/erd.png)


- **User**: 시스템의 사용자 정보를 관리하며, **API Key**, **Card**, **Chat Session**, **Approval Log**와 연결됩니다.
  - **user_id**를 기준으로 여러 엔티티와 관계를 형성합니다.
  
- **API Key**: 사용자의 **API 키** 정보를 저장합니다.
  - **user_id**를 통해 **User**와 연결됩니다.

- **Card**: 사용자 카드 정보를 저장하며, **Card Message**와 연결되어 카드 내 메시지를 관리합니다.
  - **user_id**와 **session_id**를 통해 사용자 및 세션과 연결됩니다.

- **Chat Session**: 각 사용자별로 생성되는 **채팅 세션**을 저장하며, **Chat Message**와 연결됩니다.
  - **user_id**와 **session_id**로 **User**와 **Card** 테이블과 연관됩니다.

- **Chat Message**: **채팅 메시지**를 저장하며, **Chat Session**과 연결됩니다.

- **Card Message**: 각 카드 내에서 발생하는 메시지 정보를 관리하며, **Card** 및 **Chat_message**와 연결됩니다.

- **Approval Log**: 시스템 내 **승인 로그**를 기록하며, **User**와 연결됩니다.


---

## ⚠️ 현재 발생한 문제점

### 문제 1. SLLM에 사용할 QWEN 모델 선택 및 학습 방법 불확실
- 원래는 QWEN3 8B 모델을 사용 계획이었으나, 아래 문제들이 발생함
> 확보된 파인튜닝 코드는 Qwen2-7B 기준이며, Qwen3는 COT/Thinking 모드 적용으로 학습 파이프라인이 달라진 것으로 보임

> 목표는 멀티턴 학습이나, 현재 알고 있는 학습 데이터셋 관련 내용은 싱글턴 기준이므로 멀티턴 데이터 생성에 대한 설계가 필요함

### 🔍 문제 1에 대한 해결방안
- 아래 내용에 대해 고민·결정이 필요함 (멘토님께 자문 병행)
> 적용 가능성 확인: Qwen3의 COT/Thinking 모드 기준 멀티턴 학습셋 생성 가능 여부.

> 필요성 검토: 우리 도메인에서 COT/Thinking 모드가 꼭 필요한지 판단.

> 트레이드오프 평가: 파인튜닝 데이터 준비·진행 시간/비용 vs 기대 성능 향상.

> 정책 결정: 위 평가를 바탕으로 SLLM 모델 선정(Qwen2 vs Qwen3) 및 학습 데이터 생성(가능하면 멀티턴으로).


### 문제 2. SLLM RAG 구축용 사내 문서의 직급/팀/권한 현실성 부족
- 기존에 생성한 사내 내부 문서에 아래 문제점들이 존재함
> 직급별로 문서를 나눴지만 실제 내용은 하위 직급도 열람 가능해 보이는 수준으로 생성됨

> 직급만으로 권한을 구분했을 뿐, **팀/부서/업무 맥락**이 고려되지 않아 실제 사용성과 맞지 않음


### 🔍 문제 2에 대한 해결방안
- 아래 내용에 대해 고민·결정이 필요함 (멘토님께 자문 병행)
> 권한 스키마 정의: 단순 직급 기준이 아닌, 문서 내용의 실제 중요도나 업무 상 필요성을 반영한 권한 기준 재설계

> 문서 생성 기준: 실제 내부 직원(개발팀)이 자주 묻는 질문이나 업무 흐름 기반으로 문서 작성 방향 재정립

> 문서 검수 기준: 각 직급별 문서 내용이 과도하거나 부족하지 않도록, 현실 업무에서 열람 필요성과 수준을 기준으로 피드백/보완


## 👥 역할 분담 (R&R)

| 구분 | 담당자 | 역할 |
|------|--------|------|
| **총괄** | 김준기 | 프로젝트 리드, 서비스 배포 |
| **데이터 수집** | 김준기, 이원지희, 이나경, 안윤지, 정민영, 김재우 | API별 문서 수집 및 정제 |
| **AI 백엔드** | 이나경, 안윤지, 정민영 | API문서 RAG 기반 LLM 개발 |
|  | 김준기, 이원지희, 김재우 | 사내 문서 sLLM 개발 |
| **웹 개발(Django)** | (페이지별 추후 배정) | 인증/회원가입/챗봇 UI |
| **서비스 배포** | 김준기, 정민영 | AWS, Docker, Nginx, CI/CD |


---

## 🚧 향후 계획

### **✔️ 기술 검증 및 기반 구축**
- **RAG + sLLM을 위한 FastAPI 설계**: RAG와 sLLM을 효과적으로 통합하여 API 서버를 구축합니다.
- **Qwen Finetuning 방법 조사**: **Qwen 8B 모델**에 대해 최적화 및 파인튜닝 방법을 조사하고 적용합니다.
- **벡터 DB 성능 평가**: **QA data**와 **원문 data**를 비교 분석하여 벡터 DB의 검색 성능을 평가하고 최적화합니다.
- **RAG 평가 방법 구축**: RAG 성능 평가를 위한 정확한 기준과 방법을 설계합니다.

### **✔️ 모델 최적화 및 기능 개발**
- **SLLM 파인튜닝** : 선택한 Qwen 모델에 대한 파인튜닝을 진행합니다.
- **RAG 연동 및 프롬프트 최적화**: LLM/SLLM 모델에 RAG 기능을 적용하고, 프롬프트를 최적화하여 모델 성능을 극대화합니다.
- **RAG 성능 평가 진행**: RAG 성능 평가를 진행하고, 개선 방안에 대해 조사하여 적용합니다.
- **DJANGO 웹 구현(프론트/백엔드)**: Django 프레임워크를 사용하여 웹 UI(프론트)와 백엔드를 구현합니다.

### **✔️ 서비스 고도화 및 배포**
- **사용자 기능 최적화 및 개선**: 사용자 피드백을 바탕으로 기능을 최적화 및 개선하고, 사용자 맞춤형 서비스를 제공할 수 있도록 합니다.
- **AWS + Docker 기반 배포**: AWS와 Docker 환경에서 안정적이고 확장 가능한 서비스를 배포합니다.
- **운영 환경에서의 안정화 및 성능 개선**: 배포된 시스템의 안정성과 성능을 지속적으로 모니터링하고 최적화합니다.

### **✔️ CI/CD 구축**
- GitHub Actions를 사용하여 **CI/CD 파이프라인을 자동화**하고, 코드를 **AWS Elastic Beanstalk**에 배포합니다.
- GitHub Actions는 코드를 푸시할 때마다 자동으로 빌드하고 테스트한 후, **AWS Elastic Beanstalk**에 자동 배포를 실행하여 **빠르고 안전한 배포**를 보장합니다.



---
