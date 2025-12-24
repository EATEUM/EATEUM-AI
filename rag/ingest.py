import os
import pandas as pd
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

# 환경 변수 로드 (.env 파일에 OPENAI_API_KEY가 있어야 합니다)
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

print(f"🔑 OpenAI API 연동 준비 중...")

# 파일 경로 설정 (데이터 파일이 같은 폴더에 있어야 합니다)
data_path = "recipes_data.csv"
scraper_path = "recipes_scraper.csv"

try:
    # 1. 두 가지 데이터 소스 로드
    df_data = pd.read_csv(data_path)
    df_scraper = pd.read_csv(scraper_path)
    
    # 2. 데이터 병합 (recipe_video_id 기준)
    # scraper 데이터에서 조리과정(steps_json)과 썸네일을 가져와 합칩니다.
    df = pd.merge(df_data, df_scraper[['recipe_video_id', 'steps_json', 'thumbnail_url']], 
                  on='recipe_video_id', how='left')
    
    df.columns = df.columns.str.strip()
    print(f"✅ CSV 파일 병합 완료. 총 {len(df)}개 레시피 데이터를 로드했습니다.")
except Exception as e:
    print(f"❌ 파일 로드 실패: {e}")
    print("recipes_data.csv와 recipes_scraper.csv 파일이 현재 폴더에 있는지 확인해주세요.")
    exit()

docs = []
for index, row in df.iterrows():
    category = str(row['category_name']) if pd.notna(row['category_name']) else "기타"
    title = str(row['video_title']) if pd.notna(row['video_title']) else "제목 없음"
    items = str(row['item_name']) if pd.notna(row['item_name']) else ""
    steps = str(row['steps_json']) if pd.notna(row['steps_json']) else ""

    # RAG 성능 향상을 위해 조리법(steps)까지 검색 대상인 content에 포함합니다.
    # 사용자가 '볶음'이나 특정 조리법을 검색해도 대응할 수 있습니다.
    content = f"요리명: {title} / 재료: {items} / 분류: {category} / 조리과정: {steps}"
    
    # 메타데이터에 필요한 정보를 저장합니다.
    metadata = {
        "recipe_video_id": int(row['recipe_video_id']), 
        "ingredients": items,  
        "video_title": title,
        "thumbnail_url": str(row.get('thumbnail_url', ''))
    }
    
    doc = Document(page_content=content, metadata=metadata)
    docs.append(doc)

print(f"🚀 총 {len(docs)}개의 문서 벡터화 시작 (text-embedding-3-small)...")

embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small" 
)

persist_directory = "./chroma_db"

# 기존 DB가 있다면 덮어쓰거나 새로 생성합니다.
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    persist_directory=persist_directory
)

print(f"✨ 벡터 DB 구축 완료! '{persist_directory}' 폴더에 저장되었습니다.")