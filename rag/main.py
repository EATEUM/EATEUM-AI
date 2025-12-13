import os
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field


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
    selectedItems: List[str]

class RecipeResponse(BaseModel):
    recipe_ids: List[int]   # 예: [10, 5, 2]

@app.post("/recipes/recommend/ai", response_model=RecipeResponse)
async def recommend_recipes(request: RecipeRequest):
    # ✅ 이미 파싱된 데이터
    ingredients = request.selectedItems

    if not ingredients:
        return {"recipe_ids": []}

    # 검색 쿼리 생성
    user_ingredients = ", ".join(request.selectedItems)
    query = f"{user_ingredients}을(를) 사용한 맛있는 요리 레시피를 추천해줘."

    print(f"📩 요청 검색어: {query}")

    results = vectorstore.similarity_search(query, k=3)

    ids = []
    for doc in results:
        rec_id = doc.metadata.get("recipe_video_id")
        if rec_id is not None:
            try:
                ids.append(int(rec_id))
            except ValueError:
                pass

    unique_ids = list(dict.fromkeys(ids))
    print(f"📤 추천 결과(ID): {unique_ids}")

    return {"recipe_ids": unique_ids}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 👇 터미널에 정확히 뭐가 문제인지 빨간 글씨로 띄워줍니다.
    print(f"❌ [에러 상세 내용] : {exc}") 
    print(f"📩 [받은 데이터 본문]: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

