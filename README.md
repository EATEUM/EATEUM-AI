# EATEUM-AI

EATEUM 프로젝트의 AI서버입니다. 레시피 데이터 수집, 전처리 및 RAG(Retrieval-Augmented Generation) 기반 레시피 추천 시스템을 제공합니다.

## 📋 목차

- [시작하기](#시작하기)
- [환경 설정](#환경-설정)
- [데이터 수집 및 전처리](#데이터-수집-및-전처리)
- [RAG 서버 실행](#rag-서버-실행)
- [프로젝트 구조](#프로젝트-구조)

---

## 🚀 시작하기

### 1. 환경세팅

코드를 다운로드합니다.

### 2. 환경 변수 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 입력합니다:

```env
# GMS에서 발급받은 키
OPENAI_API_KEY=""

# GMS 전용 주소 (여기가 핵심!)
OPENAI_API_BASE=""

# YouTube API 키 (각자 발급받은 키 입력)
YOUTUBE_API_KEY=""

# 데이터베이스 접속 정보
DB_USER={DB 유저 네임}
DB_PASSWORD={DB 비밀번호}
DB_HOST=localhost
DB_PORT=3306
DB_NAME=EATEUM-BE
```

### 3. 가상환경 생성 및 실행 (필수 ⭐)

**Mac / Linux:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Windows:**

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
```

> 💡 터미널 앞에 `(.venv)`가 뜨면 성공입니다!

### 4. 라이브러리 설치

```bash
pip install -r requirements.txt
```

---

## 📊 데이터 수집 및 전처리

### Step 1: Selenium으로 레시피 데이터 크롤링

```bash
cd scraper
python main.py
```

이 과정에서 YouTube 레시피 영상 데이터를 수집합니다.

### Step 2: 데이터 전처리 (ETL)

```bash
cd ../etl
python main.py
```

수집된 데이터를 정제하고 구조화합니다.

### Step 3: 데이터베이스에 업로드

```bash
cd ..
python db_upload_all.py
```

> ⚠️ **주의**: `db_upload_all.py` 실행 시 루트 디렉토리(`EATEUM-AI/`)에 있어야 합니다.

---

## 🤖 RAG 서버 실행

### 가상환경 활성화 확인

**Mac / Linux:**

```bash
source .venv/bin/activate
```

**Windows:**

```bash
source .venv/Scripts/activate
```

### RAG 디렉토리로 이동

```bash
cd rag
```

### 벡터 데이터베이스 초기화 (최초 1회만)

`chroma_db` 폴더가 없는 경우에만 실행합니다:

```bash
python ingest.py
```

이 과정에서 레시피 데이터를 벡터화하여 ChromaDB에 저장합니다.

### RAG 서버 실행

```bash
uvicorn main:app --reload
```

서버가 정상적으로 실행되면 `http://localhost:8000`에서 API를 사용할 수 있습니다.

> 📌 **전체 시스템 실행 순서**:
>
> 1. RAG 서버 실행 (이 프로젝트)
> 2. 백엔드 서버 실행 (EATEUM-BE)
> 3. 프론트엔드 실행 (EATEUM-FE)

---

## 📁 프로젝트 구조

```
EATEUM-AI/
├── scraper/           # 웹 크롤링 (Selenium + YouTube API)
│   ├── main.py        # 레시피 영상 크롤러
│   └── youtube_api.py # YouTube API 헬퍼
├── etl/               # 데이터 전처리
│   └── main.py        # ETL 파이프라인
├── rag/               # RAG 서버
│   ├── ingest.py      # 벡터 DB 생성
│   └── main.py        # FastAPI 서버
├── data/              # 수집된 원본 데이터
├── chroma_db/         # 벡터 데이터베이스
├── db_upload_all.py   # DB 업로드 스크립트
├── requirements.txt   # Python 패키지 목록
└── .env               # 환경 변수 (직접 생성)
```

---

## 🛠 기술 스택

- **Python 3.11**
- **LangChain**: RAG 파이프라인 구축
- **OpenAI API**: 임베딩 및 LLM
- **ChromaDB**: 벡터 데이터베이스
- **FastAPI**: RESTful API 서버
- **Selenium**: 웹 크롤링
- **SQLAlchemy**: 데이터베이스 ORM

---

## 📝 API 문서

RAG 서버 실행 후 다음 주소에서 API 문서를 확인할 수 있습니다:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
