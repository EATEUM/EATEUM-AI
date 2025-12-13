import os
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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

# 임베딩 모델 설정 (ingest.py와 동일해야 함)
embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small"
)

# DB 연결 (안전장치 추가)
if not os.path.exists(db_path):
    # DB가 없으면 서버 실행을 막음 (실수 방지)
    raise RuntimeError("❌ 'chroma_db' 폴더가 없습니다. ingest.py를 먼저 실행해서 DB를 구축해주세요!")

vectorstore = Chroma(
    persist_directory=db_path,
    embedding_function=embedding_model
)
print("✅ RAG 서버 준비 완료! ChromaDB가 로드되었습니다.")

# --- 데이터 모델 정의 ---
class RecipeRequest(BaseModel):
    ingredients: List[str]  # 예: ["김치", "돼지고기"]

class RecipeResponse(BaseModel):
    recipe_ids: List[int]   # 예: [10, 5, 2]

@app.post("/recommend/ai", response_model=RecipeResponse)
async def recommend_recipes(request: RecipeRequest):
    # 1. 검색 쿼리 최적화 (자연어 문장으로 변환)
    # 팁: 단순히 재료만 나열하는 것보다, "추천해줘" 같은 뉘앙스를 넣으면 더 잘 찾음
    user_ingredients = ", ".join(request.ingredients)
    query = f"{user_ingredients}을(를) 사용한 맛있는 요리 레시피를 추천해줘."
    
    print(f"📩 요청 검색어: {query}") 

    # 2. 벡터 검색 수행 (상위 5개)
    # k=5: 가장 유사한 5개 추출
    results = vectorstore.similarity_search(query, k=5)
    
    # 3. 결과에서 ID 추출 및 정제
    ids = []
    for doc in results:
        rec_id = doc.metadata.get("recipe_video_id")
        
        # 메타데이터에 ID가 있는지 확인하고 추가
        if rec_id is not None:
            try:
                ids.append(int(rec_id))
            except ValueError:
                continue # 혹시 숫자가 아닌 게 들어있으면 스킵
    
    # 중복 제거 (순서 유지하면서) - 중요! 같은 요리가 여러 번 나올 수 있음
    unique_ids = list(dict.fromkeys(ids))
    
    print(f"📤 추천 결과(ID): {unique_ids}")
    
    # 검색 결과가 없으면 빈 리스트 반환
    return {"recipe_ids": unique_ids}

# 실행 방법 (터미널):
# uvicorn main:app --reload