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
    user_ingredients = request.selectedItems 

    if not user_ingredients:
        return {"recipe_ids": []} 

    query = ", ".join(user_ingredients)
    candidates = vectorstore.similarity_search(query, k=20)

    scored_recipes = []

    # Re-ranking
    for doc in candidates:
        db_ingredients_str = doc.metadata.get("ingredients", "") # DB에 있는 재료 문자열
        
        match_count = 0
        
        for user_item in user_ingredients:
            if user_item in db_ingredients_str:
                match_count += 1
        
        scored_recipes.append((match_count, doc))

    scored_recipes.sort(key=lambda x: x[0], reverse=True)

    final_ids = []
    print(f"사용자 입력: {user_ingredients}")
    print("재료 일치 순위 결과:")

    for count, doc in scored_recipes[:9]: # 상위 9개만 이 부분 수정해야 함!
        rec_id = doc.metadata.get("recipe_video_id")
        title = doc.metadata.get("video_title")
        ingredients = doc.metadata.get("ingredients")
        
        print(f"[일치 {count}개] {title} (재료: {ingredients})")

        if rec_id is not None:
            try:
                if int(rec_id) not in final_ids:
                    final_ids.append(int(rec_id))
            except ValueError:
                pass

    return {"recipe_ids": final_ids}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"[에러 상세 내용] : {exc}") 
    print(f"받은 데이터 본문]: {await request.body()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

