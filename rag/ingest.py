import os
import pandas as pd
from dotenv import load_dotenv
from langchain_community.document_loaders import DataFrameLoader
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

# 1. .env 파일 로드
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 주소 확인 
print(f"🔑 Key Loaded: {api_key[:5]}*****")
print(f"🌐 Base URL: {api_base}")

# 2. 데이터 로드
csv_path = "../data/recipes_test.csv" 
try:
    df = pd.read_csv(csv_path)
    # 컬럼 공백 제거 (안전장치)
    df.columns = df.columns.str.strip()
    print(f"✅ CSV 파일 로드 완료. 총 {len(df)}개 레시피.")
except FileNotFoundError:
    print("❌ CSV 파일이 없습니다. 경로를 확인해주세요.")
    exit()

docs = []
for index, row in df.iterrows():
    # ---------------------------------------------------------
    # ✏️ 수정된 부분 1: 검색 내용(Content) 강화
    # 카테고리 정보도 텍스트에 포함시켜서 "일식 추천해줘" 같은 질문에 잘 걸리게 함
    # ---------------------------------------------------------
    content = f"분류: {row['category_name']} / 요리명: {row['video_title']} / 재료: {row['item_name']}"
    
    # ---------------------------------------------------------
    # ✏️ 수정된 부분 2: 메타데이터(Metadata) 추가
    # 나중에 프론트엔드에서 보여주거나 필터링할 때 필요한 정보들
    # ---------------------------------------------------------
    metadata = {
        "recipe_video_id": row['recipe_video_id'], 
        "category_name": row['category_name'], # ✅ 카테고리 추가됨
        "video_url": row.get('video_url', ''), 
        "video_title": row['video_title']      # 제목도 메타데이터에 있으면 나중에 꺼내 쓰기 편함
    }
    
    # LangChain 문서 객체 생성
    doc = Document(page_content=content, metadata=metadata)
    docs.append(doc)

print(f"✅ 총 {len(docs)}개의 문서가 준비되었습니다. 벡터 변환 시작...")

# 3. 임베딩 모델 설정
embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small" # 임베딩 전용 모델 권장
)

# 4. 벡터 DB 생성 및 저장 (기존 DB가 있다면 덮어쓰거나 추가됨)
persist_directory = "./chroma_db"

vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    persist_directory=persist_directory
)

print(f"🎉 벡터 DB 구축 완료! '{persist_directory}' 폴더에 저장되었습니다.")