import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

try:
    db_connection_str = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    db_connection = create_engine(db_connection_str)
    print(f"✅ DB 연결 성공: {DB_NAME}")
except Exception as e:
    print(f"❌ DB 연결 실패: {e}")
    exit()

def upload_csv(file_name, table_name, mapping=None):
    """CSV 파일을 읽어서 DB 테이블에 넣는 함수"""
    file_path = f'etl/{file_name}' 
    


    if not os.path.exists(file_path):
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

    if mapping:
        df = df.rename(columns=mapping)


    
    print(f"🚀 '{table_name}' 테이블에 {len(df)}개 데이터 업로드 시작...")
    
    try:
        
        df.to_sql(name=table_name, con=db_connection, if_exists='append', index=False)
        print(f"✅ 성공! ({table_name})")
    except Exception as e:
        print(f"❌ 실패 ({table_name}): {e}")

def main():

    upload_csv('clean_category.csv', 'category', mapping={
        'category_id': 'category_id', 
        'category_name': 'category_name'
    })

    upload_csv('clean_recipe_video.csv', 'recipe_video', mapping={
        'recipe_video_id': 'recipe_video_id',
        'video_title': 'video_title',
        'thumbnail_url': 'thumbnail_url',
        'video_url': 'video_url',
        'view_count': 'view_count',
        'duration': 'duration',       
        'category_id': 'category_id'
    })

    upload_csv('clean_items.csv', 'items', mapping={
        'item_id': 'item_id',
        'item_name': 'item_name',
        'item_img': 'item_img'
    })

    upload_csv('clean_recipe_items.csv', 'recipe_items', mapping={
        'recipe_video_id': 'recipe_video_id',
        'item_id': 'item_id'
    })

    upload_csv('clean_recipe_steps.csv', 'recipe_steps', mapping={
        'recipe_video_id': 'recipe_video_id',
        'step_number': 'step_number',
        'step_title': 'step_title',   
        'content': 'content'
    })

    print("\n🎉 모든 데이터 업로드 완료!")

if __name__ == "__main__":
    main()