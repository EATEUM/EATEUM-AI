import os
import pandas as pd
from dotenv import load_dotenv
from langchain_community.document_loaders import DataFrameLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

# 1. .env 파일 로드
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 주소 확인 
print(f"🔑 Key Loaded: {api_key[:5]}*****")
print(f"🌐 Base URL: {api_base}")

# 2. 데이터 로드 및 문서 변환
csv_path = "data/recipes_data.csv" 
df = pd.read_csv(csv_path)

# CSV 컬럼 헤더가 정확한지 확인 (혹시 모를 공백 제거)
df.columns = df.columns.str.strip()

print(f"✅ CSV 파일 로드 완료. 총 {len(df)}개 레시피.")

docs = []
for index, row in df.iterrows():
    # TODO : 수정할 부분 1. 검색할 텍스트 ('video_title'과 'item_name' 합치기)
    content = f"요리명: {row['video_title']} / 재료: {row['item_name']}"
    
    # 2. 메타데이터 (recipe_video_id를 ID로 저장)
    metadata = {
        "recipe_video_id": row['recipe_video_id'], 
        "video_url": row.get('video_url', ''), 
    }
    
    # LangChain 문서 객체 생성
    doc = Document(page_content=content, metadata=metadata)
    docs.append(doc)

print(f"✅ 총 {len(docs)}개의 문서가 준비되었습니다. 벡터 변환 시작...")

# 3. 임베딩 모델 설정 (SSAFY GMS 맞춤 설정)
# 주의: gpt-4.1은 채팅용 모델입니다. 임베딩에는 보통 'text-embedding-3-small'을 씁니다.
# 만약 에러가 나면 'text-embedding-ada-002'로 바꿔보세요.
embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base, # GMS 주소 연결
    model="text-embedding-3-small" # 임베딩 전용 모델
)

# 4. 벡터 DB 생성 및 저장
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    persist_directory="./chroma_db"
)

print("🎉 벡터 DB 구축 완료! (GMS 연동 성공)")