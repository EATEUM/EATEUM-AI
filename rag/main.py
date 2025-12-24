import os
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

load_dotenv()

app = FastAPI()

db_path = "./chroma_db"
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 임베딩 모델 설정
embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base,
    model="text-embedding-3-small"
)

# DB 존재 여부 확인
if not os.path.exists(db_path):
    print("⚠️ 경고: 'chroma_db' 폴더가 없습니다. ingest.py를 먼저 실행해주세요!")

# 로드된 벡터스토어
vectorstore = Chroma(
    persist_directory=db_path,
    embedding_function=embedding_model
)
print("✅ RAG 서버 준비 완료! ChromaDB가 성공적으로 로드되었습니다.")

class RecipeRequest(BaseModel):
    selectedItems: List[str]

class RecipeResponse(BaseModel):
    recipe_ids: List[int] 

@app.post("/recipes/recommend/ai", response_model=RecipeResponse)
async def recommend_recipes(request: RecipeRequest):
    user_ingredients = request.selectedItems 

    if not user_ingredients:
        return {"recipe_ids": []} 

    # 1. RAG를 이용한 1차 유사 후보군 검색 (20개)
    query = ", ".join(user_ingredients)
    candidates = vectorstore.similarity_search(query, k=20)

    scored_recipes = []

    # 2. Re-ranking 로직: 재료 매칭 정확도 정밀 검사
    for doc in candidates:
        db_ingredients_str = doc.metadata.get("ingredients", "")
        
        # 해결책: 문자열을 쉼표로 잘라 리스트화한 후 정확히 일치하는지 비교
        # 이렇게 하면 "파"가 "양파"의 일부로 인식되지 않습니다.
        db_ingredients_list = [i.strip() for i in db_ingredients_str.split(',') if i.strip()]
        
        match_count = 0
        for user_item in user_ingredients:
            # 리스트 내에 정확한 재료명이 있는지 확인
            if user_item in db_ingredients_list:
                match_count += 1
        
        scored_recipes.append((match_count, doc))

    # 3. 일치하는 재료 개수가 많은 순으로 정렬
    scored_recipes.sort(key=lambda x: x[0], reverse=True)

    final_ids = []
    print(f"\n[AI 요청] 사용자 재료: {user_ingredients}")
    print("--- 재료 매칭 순위 결과 ---")

    # 4. 상위 9개 결과의 ID 추출 (중복 제거)
    for count, doc in scored_recipes[:9]:
        rec_id = doc.metadata.get("recipe_video_id")
        title = doc.metadata.get("video_title")
        ingredients = doc.metadata.get("ingredients")
        
        print(f"[일치 {count}개] {title} (DB재료: {ingredients})")

        if rec_id is not None:
            try:
                rid = int(rec_id)
                if rid not in final_ids:
                    final_ids.append(rid)
            except (ValueError, TypeError):
                pass

    return {"recipe_ids": final_ids}

# 에러 핸들러
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"❌ 요청 데이터 에러: {exc}") 
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)