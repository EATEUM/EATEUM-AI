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


load_dotenv()

app = FastAPI()

db_path = "./chroma_db"
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small"
)

if not os.path.exists(db_path):
    raise RuntimeError("❌ 'chroma_db' 폴더가 없습니다. ingest.py를 먼저 실행해서 DB를 구축해주세요!")

vectorstore = Chroma(
    persist_directory=db_path,
    embedding_function=embedding_model
)
print("✅ RAG 서버 준비 완료! ChromaDB가 로드되었습니다.")

class RecipeRequest(BaseModel):
    selectedItems: List[str]

class RecipeResponse(BaseModel):
    recipe_ids: List[int] 

@app.post("/recipes/recommend/ai", response_model=RecipeResponse)
async def recommend_recipes(request: RecipeRequest):
    ingredients = request.selectedItems

    # if not ingredients:
    #     return {"recipe_ids": []}
    
    # 재료가 아예 없는 경우 방어
    if not ingredients or len(ingredients) == 0:
    # 우선 인기 레시피 3개 제공  여기서 조회수 조회애서 3개 주기
        return {"recipe_ids": [1, 2, 3]}

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
    print(f"❌ [에러 상세 내용] : {exc}") 
    print(f"📩 [받은 데이터 본문]: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

