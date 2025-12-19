import os
import pandas as pd
from dotenv import load_dotenv
from langchain_community.document_loaders import DataFrameLoader
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

print(f"🔑 Key Loaded: {api_key[:5]}*****")
print(f"🌐 Base URL: {api_base}")

csv_path = "../data/recipes_data.csv" 
try:
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    print(f"CSV 파일 로드 완료. 총 {len(df)}개 레시피.")
except FileNotFoundError:
    print("CSV 파일이 없습니다. 경로를 확인해주세요.")
    exit()


docs = []
for index, row in df.iterrows():
    category = str(row['category_name']) if pd.notna(row['category_name']) else "기타"
    title = str(row['video_title']) if pd.notna(row['video_title']) else "제목 없음"
    items = str(row['item_name']) if pd.notna(row['item_name']) else ""

    content = f"요리명: {title} / 재료: {items} / 분류: {category}"
    

    metadata = {
        "recipe_video_id": row['recipe_video_id'], 
        "ingredients": items,  
        "video_title": title
    }
    
    doc = Document(page_content=content, metadata=metadata)
    docs.append(doc)


print(f"총 {len(docs)}개의 문서가 준비되었습니다. 벡터 변환 시작...")

embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small" 
)

persist_directory = "./chroma_db"

vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=embedding_model,
    persist_directory=persist_directory
)

print(f"벡터 DB 구축 '{persist_directory}' 폴더에 저장되었습니다.")