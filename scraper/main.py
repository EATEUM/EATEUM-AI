import os
import time
import pandas as pd
import re
from io import StringIO
from selenium import webdriver
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

OUTPUT_FILE = 'data/final_recipe_full_data.csv'

# TODO : 파일 경로 수정 (현재는 예시 데이터 사용)
csv_data = """recipe_video_id,video_title,video_url
1,한국 길거리 음식 NO.1 떡볶이,https://www.youtube.com/watch?v=t4Es8mwdYlE
2,양배추전으로 살 10kg 그냥 뺍니다,https://www.youtube.com/watch?v=cUQzxhmYdGs
3,이연복의 칠리새우,https://youtu.be/HHxrciV2-MU?si=HscScOOJa-OT7NVC"""
df = pd.read_csv(StringIO(csv_data))

# (1) 유튜브 URL에서 비디오 ID만 쏙 뽑아내는 함수 (썸네일용)
def get_video_id(url):
    # 'v=' 뒤에 있는 ID 추출 or 'youtu.be/' 뒤에 있는 ID 추출
    video_id = None
    if 'v=' in url:
        video_id = url.split('v=')[1].split('&')[0]
    elif 'youtu.be' in url:
        video_id = url.split('/')[-1].split('?')[0]
    return video_id

# (2) Selenium으로 화면 긁기 (자막 + 조회수)
def get_info_via_selenium(driver, url):
    info = {"transcript": None, "view_count": "0"}
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 5)
        time.sleep(3)

        # --- [조회수 가져오기] ---
        try:
            # 제목 아래 정보창이나 설명란 근처에서 조회수 찾기
            # (유튜브 UI에 따라 다르지만 보통 아래 셋 중 하나에 걸림)
            view_elem = driver.find_element(By.XPATH, "//*[@id='info-container']//span[contains(text(), '조회수')]")
            info['view_count'] = view_elem.text
        except:
            # 실패하면 설명란 열어서 다시 시도
            pass

        # --- [자막 가져오기] ---
        # 1. 더보기 클릭
        try:
            expand_btn = driver.find_element(By.ID, "expand")
            expand_btn.click()
            time.sleep(1)
        except: pass

        # 2. 조회수 재시도 (더보기 누른 후 설명란 안에서 찾기)
        if info['view_count'] == "0":
            try:
                view_text = driver.find_element(By.CSS_SELECTOR, "#info span.view-count").text
                info['view_count'] = view_text
            except: pass

        # 3. 스크립트 버튼 클릭
        try:
            script_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='스크립트 표시']")))
            script_btn.click()
        except:
            try:
                script_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Show transcript')]")
                script_btn.click()
            except:
                return info # 자막 버튼 없으면 그냥 리턴

        time.sleep(2)

        # 4. 자막 텍스트 긁기
        segments = driver.find_elements(By.CSS_SELECTOR, "ytd-transcript-segment-renderer .segment-text")
        info['transcript'] = " ".join([seg.text for seg in segments])
        
        return info

    except Exception as e:
        print(f"⚠️ 크롤링 에러: {e}")
        return info

# (3) GPT 포맷팅
# TODO : 프롬프트 더 자세히 다듬기
def format_recipe_with_gpt(raw_transcript):
    if not raw_transcript or len(raw_transcript) < 50:
        return "자막 없음"

    llm = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0,
        api_key=api_key,
        base_url=api_base
    )


    template = """
    너는 요리 레시피 정리 앱의 백엔드 AI야.
    아래 [자막]을 읽고 JSON으로 정리해줘. 잡담은 빼고 요리 과정만 남겨.
    
    [출력 예시 JSON]
    [
        {{"step": 1, "step_title": "재료 손질", "step_detail": "양파는 채 썰고 파는 다집니다."}},
        {{"step": 2, "step_title": "볶기", "step_detail": "팬에 기름을 두르고 볶습니다."}}
    ]

    ---
    [자막]
    {transcript}
    """
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm
    
    try:
        response = chain.invoke({"transcript": raw_transcript[:20000]})
        return response.content
    except Exception as e:
        return f"GPT 에러: {e}"

# 3. 메인 실행
chrome_options = Options()
chrome_options.add_argument("--mute-audio")
driver = webdriver.Chrome(options=chrome_options)

if not os.path.exists('data'):
    os.makedirs('data')

print(f"🚀 총 {len(df)}개 영상 크롤링 시작...")

for index, row in df.iterrows():
    print(f"\n[{index+1}/{len(df)}] '{row['video_title']}' 진행 중...")
    
    # 1. 썸네일 (URL에서 ID 추출해서 만들기)
    vid_id = get_video_id(row['video_url'])
    thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg" if vid_id else ""

    # 2. Selenium으로 자막 & 조회수 긁기
    info = get_info_via_selenium(driver, row['video_url'])
    
    gpt_result = ""
    if info['transcript']:
        print("   ✅ 자막 확보! GPT 정리 요청...")
        gpt_result = format_recipe_with_gpt(info['transcript'])
    else:
        print("   ❌ 자막 없음")
        gpt_result = "[]" # 빈 JSON 배열

    # 3. 저장
    data = {
        'id': row['recipe_video_id'],
        'title': row['video_title'],
        'url': row['video_url'],
        'thumbnail': thumbnail_url,      # 썸네일 추가됨
        'view_count': info['view_count'], # 조회수 추가됨
        'recipe_json': gpt_result
    }
    
    df_save = pd.DataFrame([data])
    
    if not os.path.exists(OUTPUT_FILE):
        df_save.to_csv(OUTPUT_FILE, index=False, mode='w', encoding='utf-8-sig')
    else:
        df_save.to_csv(OUTPUT_FILE, index=False, mode='a', header=False, encoding='utf-8-sig')

print("\n🎉 완료! data 폴더를 확인하세요.")
driver.quit()