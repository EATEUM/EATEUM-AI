import pandas as pd
import json
import uuid
from datetime import datetime
from io import StringIO

# ==========================================
# 1. 원본 데이터 로드 (파일 경로 수정 필요)
# ==========================================
# 실제 파일 경로를 넣어주세요. 예: 'data/recipe_detail.csv'
# 여기서는 예시 데이터를 코드로 넣었습니다. 실제로는 pd.read_csv('파일명.csv')를 쓰세요.

csv_detail = """id,title,url,thumbnail,view_count,recipe_json
1,떡볶이,http://url1,http://img1,조회수 1444만회,"[{""step"":1,""description"":""파를 썬다""}]"
2,김치찌개,http://url2,http://img2,조회수 100만회,"[{""step"":1,""description"":""김치를 볶는다""}]"
"""

csv_info = """recipe_video_id,video_title,category_name,item_name,video_url
1,떡볶이,분식,"떡, 파, 양배추",http://url1
2,김치찌개,한식,"김치, 돼지고기, 두부",http://url2
"""

# 실제 사용 시:
# df_detail = pd.read_csv('recipe_detail.csv')
# df_info = pd.read_csv('recipe_data.csv')

df_detail = pd.read_csv(StringIO(csv_detail))
df_info = pd.read_csv(StringIO(csv_info))

print("📂 원본 데이터 로드 완료")

# ==========================================
# 2. 데이터 병합 (ID 기준)
# ==========================================
merged_df = pd.merge(df_info, df_detail, left_on='recipe_video_id', right_on='id', how='inner')

# ==========================================
# 3. [Categories] 테이블 생성
# ==========================================
categories = merged_df['category_name'].unique()
category_df = pd.DataFrame({'category_name': categories})
category_df['category_id'] = range(1, len(category_df) + 1)

# 메인 데이터에 ID 매핑
merged_df = pd.merge(merged_df, category_df, on='category_name', how='left')
category_df.to_csv('clean_categories.csv', index=False, encoding='utf-8-sig')
print("✅ clean_categories.csv 생성")

# ==========================================
# 4. [Items] & [Recipe_Items] 테이블 생성
# ==========================================
all_items = set()
recipe_item_rows = []

# (1) 모든 재료 수집
for idx, row in merged_df.iterrows():
    if pd.isna(row['item_name']): continue
    items = [x.strip() for x in row['item_name'].split(',')]
    for item in items:
        all_items.add(item)

# (2) Items 테이블 만들기
items_df = pd.DataFrame({'item_name': list(all_items)})
items_df['item_id'] = range(1, len(items_df) + 1)
items_df['item_img'] = 'default.jpg'
items_df['created_at'] = datetime.now()
items_df['updated_at'] = datetime.now()

items_df.to_csv('clean_items.csv', index=False, encoding='utf-8-sig')
print("✅ clean_items.csv 생성")

# (3) Recipe_Items (연결) 만들기
item_map = dict(zip(items_df['item_name'], items_df['item_id']))
ri_id = 1

for idx, row in merged_df.iterrows():
    if pd.isna(row['item_name']): continue
    items = [x.strip() for x in row['item_name'].split(',')]
    for item in items:
        if item in item_map:
            recipe_item_rows.append({
                'recipe_item_id': ri_id,
                'recipe_video_id': row['recipe_video_id'],
                'item_id': item_map[item],
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
            ri_id += 1

pd.DataFrame(recipe_item_rows).to_csv('clean_recipe_items.csv', index=False, encoding='utf-8-sig')
print("✅ clean_recipe_items.csv 생성")

# ==========================================
# 5. [Recipe_Steps] 테이블 생성
# ==========================================
step_rows = []
step_id = 1

for idx, row in merged_df.iterrows():
    try:
        json_str = row['recipe_json']
        if isinstance(json_str, str):
            # CSV 이스케이프 문자 처리
            if json_str.startswith('"') and json_str.endswith('"'):
                json_str = json_str[1:-1].replace('""', '"')
            
            steps = json.loads(json_str)
            for step in steps:
                step_rows.append({
                    'step_id': step_id,
                    'recipe_video_id': row['recipe_video_id'],
                    'step_number': step.get('step', 0),
                    'description': step.get('description', step.get('step_detail', '')),
                    'time_stamp': step.get('time_stamp', '00:00')
                })
                step_id += 1
    except Exception as e:
        print(f"⚠️ JSON 파싱 오류 (ID {row['recipe_video_id']}): {e}")

pd.DataFrame(step_rows).to_csv('clean_recipe_steps.csv', index=False, encoding='utf-8-sig')
print("✅ clean_recipe_steps.csv 생성")

# ==========================================
# 6. [Recipe_Video] 메인 테이블 생성
# ==========================================
video_df = merged_df[[
    'recipe_video_id', 'video_title', 'url', 'thumbnail', 'view_count', 'category_id'
]].copy()

video_df = video_df.rename(columns={'url': 'video_url', 'thumbnail': 'thumbnail_url'})
video_df['dish_name'] = video_df['video_title']
video_df['youtube_video_id'] = video_df['video_url'].apply(lambda x: x.split('v=')[-1] if 'v=' in x else '')
video_df['last_search_at'] = datetime.now()
video_df['created_at'] = datetime.now()
video_df['updated_at'] = datetime.now()

video_df.to_csv('clean_recipe_video.csv', index=False, encoding='utf-8-sig')
print("✅ clean_recipe_video.csv 생성")
print("\n🎉 전처리 끝! 5개 CSV 파일을 DB에 Import 하세요.")