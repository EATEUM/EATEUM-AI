import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy import create_engine 
from dotenv import load_dotenv  

load_dotenv()

INFO_FILE_PATH = '../data/recipes_data.csv'       
DETAIL_FILE_PATH = '../data/recipes_scraper.csv' 

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DB_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def main():
    print("📂 데이터 파일을 읽는 중...")
    
    if not os.path.exists(INFO_FILE_PATH) or not os.path.exists(DETAIL_FILE_PATH):
        print("❌ 오류: 데이터 파일이 없습니다.")
        return

    try:
        engine = create_engine(DB_URL)
        df_mysql_items = pd.read_sql("SELECT item_id, item_name FROM items", engine)
        item_id_map = dict(zip(df_mysql_items['item_name'], df_mysql_items['item_id']))
        
        df_mysql_cats = pd.read_sql("SELECT category_id, category_name FROM category", engine)
        cat_id_map = dict(zip(df_mysql_cats['category_name'], df_mysql_cats['category_id']))
        
        print(f"✅ DB 연결 성공: 재료 {len(item_id_map)}개, 기존 카테고리 {len(cat_id_map)}개 로드 완료")
    except Exception as e:
        print(f"❌ DB 연결 실패 (데이터 전처리를 계속 진행합니다): {e}")
        cat_id_map = {}
        item_id_map = {}

    df_info = pd.read_csv(INFO_FILE_PATH)
    df_detail_raw = pd.read_csv(DETAIL_FILE_PATH)

    csv_categories = df_info['category_name'].dropna().astype(str).str.strip().unique()
    
    current_max_id = max(cat_id_map.values()) if cat_id_map else 0
    for cat_name in csv_categories:
        if cat_name not in cat_id_map:
            current_max_id += 1
            cat_id_map[cat_name] = current_max_id
    
    df_cat_save = pd.DataFrame([{'category_id': v, 'category_name': k} for k, v in cat_id_map.items()])
    df_cat_save.to_csv('clean_category.csv', index=False, encoding='utf-8-sig')
    print(f"✅ clean_category.csv 생성 완료 (총 {len(df_cat_save)}개)")


    info_rename = {'title': 'video_title', 'url': 'video_url', 'thumbnail': 'thumbnail_url', 'views': 'view_count', 'id': 'recipe_video_id'}
    detail_rename = {'id': 'recipe_video_id', 'title': 'video_title'}
    df_info.rename(columns=info_rename, inplace=True)
    df_detail_raw.rename(columns=detail_rename, inplace=True)

    for df in [df_info, df_detail_raw]:
        df['recipe_video_id'] = pd.to_numeric(df['recipe_video_id'], errors='coerce')
    
    df_info = df_info.dropna(subset=['recipe_video_id'])
    df_detail = df_detail_raw.dropna(subset=['recipe_video_id']).drop_duplicates(subset=['recipe_video_id'])

    merged_df = pd.merge(df_info, df_detail, on='recipe_video_id', how='left')
    
    if 'video_title_x' in merged_df.columns: merged_df['video_title'] = merged_df['video_title_x']
    if 'video_url_x' in merged_df.columns: merged_df['video_url'] = merged_df['video_url_x']


    recipe_item_rows = []
    excluded_items = set()
    for idx, row in merged_df.iterrows():
        if pd.isna(row['item_name']): continue
        items = [x.strip() for x in str(row['item_name']).split(',')]
        for itm in items:
            if itm in item_id_map:
                recipe_item_rows.append({'recipe_video_id': int(row['recipe_video_id']), 'item_id': item_id_map[itm]})
            else:
                excluded_items.add(itm)
    
    pd.DataFrame(recipe_item_rows).to_csv('clean_recipe_items.csv', index=False, encoding='utf-8-sig')
    print(f"✅ clean_recipe_items.csv 생성 완료")

    step_rows = []
    for idx, row in merged_df.iterrows():
        json_str = row.get('steps_json') if 'steps_json' in row else row.get('recipe_json')
        if pd.isna(json_str) or str(json_str).strip() in ['[]', '']: continue
        try:
            clean_json = str(json_str).replace('```json', '').replace('```', '').strip()
            if clean_json.startswith('"') and clean_json.endswith('"'): clean_json = clean_json[1:-1]
            clean_json = clean_json.replace('""', '"')
            steps = json.loads(clean_json)
            for s in steps:
                step_rows.append({
                    'recipe_video_id': int(row['recipe_video_id']),
                    'step_number': s.get('step', 0),
                    'step_title': s.get('step_title', ''),
                    'content': s.get('step_detail', s.get('description', ''))
                })
        except: pass

    pd.DataFrame(step_rows).to_csv('clean_recipe_steps.csv', index=False, encoding='utf-8-sig')
    print(f"✅ clean_recipe_steps.csv 생성 완료")

    video_df = merged_df.copy()
    
    video_df['category_name'] = video_df['category_name'].fillna('기타').astype(str).str.strip()
    video_df['category_id'] = video_df['category_name'].map(cat_id_map)
    
    if 'duration' not in video_df.columns: video_df['duration'] = '00:00'
    video_df['thumbnail_url'] = video_df['thumbnail_url'].fillna('https://via.placeholder.com/150')
    video_df['view_count'] = pd.to_numeric(video_df['view_count'], errors='coerce').fillna(0).astype(int)
    
    final_cols = ['recipe_video_id', 'video_title', 'thumbnail_url', 'view_count', 'duration', 'category_id', 'video_url']
    video_df = video_df[final_cols]
    
    video_df.to_csv('clean_recipe_video.csv', index=False, encoding='utf-8-sig')
    print(f"✅ clean_recipe_video.csv 생성 완료")

if __name__ == "__main__":
    main()