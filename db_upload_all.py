import pandas as pd
from sqlalchemy import create_engine
import os

DB_USER = 'eateum'
DB_PASSWORD = 'scca14' 
DB_HOST = 'localhost'
DB_PORT = '3306'
DB_NAME = 'EATEUM-BE'

# DB 연결
try:
    db_connection_str = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    db_connection = create_engine(db_connection_str)
    print(f"✅ DB 연결 성공: {DB_NAME}")
except Exception as e:
    print(f"❌ DB 연결 실패: {e}")
    exit()

def upload_csv(file_name, table_name, mapping=None):
    """CSV 파일을 읽어서 DB 테이블에 넣는 함수"""
    # etl 폴더 안에 파일이 생성되었을 경우 경로 수정
    file_path = f'etl/{file_name}' 
    
    # 만약 etl 폴더가 아니라 현재 폴더에 있다면 아래 줄 주석 해제
    # file_path = file_name 

    if not os.path.exists(file_path):
        # 현재 폴더에서도 한 번 찾아봄
        if os.path.exists(file_name):
            file_path = file_name
        else:
            print(f"⚠️ 파일 없음: {file_path} (건너뜀)")
            return

    print(f"\n📂 '{file_path}' 읽는 중...")
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"❌ CSV 읽기 실패: {e}")
        return

    # 컬럼 이름 매핑 (CSV 헤더 -> DB 컬럼명)
    if mapping:
        df = df.rename(columns=mapping)

    # DB 테이블에 없는 불필요한 컬럼 제거 (오류 방지)
    # (실제로는 to_sql이 남는 컬럼을 무시하지 않고 에러를 낼 수 있어서, 
    #  매핑된 컬럼만 남기는 것이 안전하지만, 여기선 일단 진행)
    
    print(f"🚀 '{table_name}' 테이블에 {len(df)}개 데이터 업로드 시작...")
    
    try:
        # if_exists='append': 데이터 추가 모드
        # index=False: 판다스 인덱스 제외
        df.to_sql(name=table_name, con=db_connection, if_exists='append', index=False)
        print(f"✅ 성공! ({table_name})")
    except Exception as e:
        print(f"❌ 실패 ({table_name}): {e}")

def main():

    # (1) 카테고리 (Category) - 가장 먼저!
    upload_csv('clean_categories.csv', 'category', mapping={
        'category_id': 'category_id', 
        'category_name': 'category_name'
    })

    # (2) 레시피 기본 정보 (Recipe_Video)
    upload_csv('clean_recipe_video.csv', 'recipe_video', mapping={
        'recipe_video_id': 'recipe_video_id',
        'video_title': 'video_title',
        'thumbnail_url': 'thumbnail_url',
        'video_url': 'video_url',
        'view_count': 'view_count',
        'duration': 'duration',       # 추가됨
        'category_id': 'category_id'
    })

    # (3) 재료 사전 (Item)
    upload_csv('clean_items.csv', 'items', mapping={
        'item_id': 'item_id',
        'item_name': 'item_name',
        'item_img': 'item_img'
    })

    # (4) 레시피-재료 연결 (Recipe_Item)
    upload_csv('clean_recipe_items.csv', 'recipe_items', mapping={
        'recipe_video_id': 'recipe_video_id',
        'item_id': 'item_id'
    })

    # (5) 요리 순서 (Recipe_Step)
    upload_csv('clean_recipe_steps.csv', 'recipe_steps', mapping={
        'recipe_video_id': 'recipe_video_id',
        'step_number': 'step_number',
        'step_title': 'step_title',   # 추가됨
        'content': 'content'
    })

    print("\n🎉 모든 데이터 업로드 완료!")

if __name__ == "__main__":
    main()