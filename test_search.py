import os
from dotenv import load_dotenv # <--- [필수] .env 로드
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# 1. 환경변수(.env) 불러오기
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 2. 임베딩 모델 설정 (ingest.py와 100% 똑같아야 함!)
# 중요: 아까 ingest.py에서 'text-embedding-ada-002'를 썼다면 여기서도 그걸 써야 합니다.
embedding_model = OpenAIEmbeddings(
    openai_api_key=api_key,
    openai_api_base=api_base, # GMS 주소 연결
    model="text-embedding-3-small" # ingest.py와 동일한 모델명 입력
)

# 3. 저장된 DB 불러오기
db_path = "./chroma_db"

if not os.path.exists(db_path):
    print("❌ 에러: 'chroma_db' 폴더가 없습니다. ingest.py를 먼저 실행하세요!")
    exit()

vectorstore = Chroma(
    persist_directory=db_path, 
    embedding_function=embedding_model # GMS 설정이 담긴 모델 주입
)

# 4. 검색 테스트
query = "자취생인데 스팸이랑 계란으로 할 수 있는 요리 있어?"
print(f"🔍 질문: {query}\n")

print("--- 검색 결과 ---")
# 유사도 기반 검색 (상위 3개)
results = vectorstore.similarity_search(query, k=3)

for i, doc in enumerate(results):
    print(f"[{i+1}위] {doc.page_content}")
    # CSV 만들 때 'id' 컬럼을 넣었다면 여기서 나옵니다.
    recipe_id = doc.metadata.get('id')
    print(f"   ㄴ ID: {recipe_id}") 
    print("-" * 30)

if not results:
    print("검색 결과가 없습니다. (데이터가 너무 적거나 임베딩 모델이 안 맞을 수 있습니다)")