import os
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# 1. 환경 설정 (.env 로드)
load_dotenv()

app = FastAPI()

# 2. 벡터 DB 로드 (서버 켜질 때 한 번만 실행)
db_path = "./chroma_db"
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 임베딩 모델 설정 (ingest.py와 똑같이!)
embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small" # 모델명 주의 (에러나면 ada-002)
)

# DB 연결
if not os.path.exists(db_path):
    print("❌ 에러: 'chroma_db' 폴더가 없습니다. ingest.py를 먼저 실행해주세요!")
    # 실제 배포시는 여기서 예외처리를 하지만, 개발중엔 그냥 둡니다.
else:
    vectorstore = Chroma(
        persist_directory=db_path,
        embedding_function=embedding_model
    )
    print("✅ RAG 서버 준비 완료! ChromaDB가 로드되었습니다.")

# --- 데이터 모델 정의 (Spring Boot가 보낼 데이터) ---
class RecipeRequest(BaseModel):
    ingredients: List[str]  # 예: ["계란", "스팸"]

class RecipeResponse(BaseModel):
    recipe_ids: List[int]   # 예: [10, 5, 2]

@app.post("/recommend/ai", response_model=RecipeResponse)
async def recommend_recipes(request: RecipeRequest):
    # 1. 입력받은 재료 리스트를 검색 문장으로 변환
    user_ingredients = ", ".join(request.ingredients)
    query = f"주재료: {user_ingredients}"
    
    print(f"📩 요청 도착: {query}") # 로그 확인용

    # 2. 벡터 검색 수행 (상위 5개)
    results = vectorstore.similarity_search(query, k=5)
    
# 3. 결과에서 ID만 쏙쏙 뽑아내기
    ids = []
    for doc in results:
        rec_id = doc.metadata.get("recipe_video_id") 
        
        if rec_id is not None:
            # CSV/DB ID가 BIGINT(Long)이므로 int로 변환
            ids.append(int(rec_id))
    
    # 중복 제거
    unique_ids = list(dict.fromkeys(ids))
    
    print(f"📤 추천 결과(ID): {unique_ids}")
    
    return {"recipe_ids": unique_ids}