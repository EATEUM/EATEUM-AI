import os
import time
import pandas as pd
from io import StringIO
from selenium import webdriver
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from youtube_api import get_video_stats

# 1. 환경변수 로드
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

# 2. 파일 경로 및 데이터 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(DATA_DIR, 'recipes_scraper.csv')

# 테스트용 데이터
csv_data = """recipe_video_id,video_title,video_url
1,한국 길거리 음식 NO.1 떡볶이,https://www.youtube.com/watch?v=t4Es8mwdYlE
2,양배추전으로 살 10kg 그냥 뺍니다,https://www.youtube.com/watch?v=cUQzxhmYdGs
3,이연복의 칠리새우,https://youtu.be/HHxrciV2-MU?si=HscScOOJa-OT7NVC"""
df = pd.read_csv(StringIO(csv_data))

def get_video_id(url):
    video_id = None
    if 'v=' in url:
        video_id = url.split('v=')[1].split('&')[0]
    elif 'youtu.be' in url:
        video_id = url.split('/')[-1].split('?')[0]
    return video_id

# [함수 2] Selenium 크롤링 (재시도 로직 포함)
def get_info_via_selenium(driver, url):
    info = {
        "transcript": None,
        "view_count": 0,
        "duration": "0:00"
    }

    video_id = get_video_id(url)

    # ⭐ 조회수 / 재생시간은 API ONLY
    if video_id:
        info["view_count"], info["duration"] = get_video_stats(video_id)

    # ⭐ Selenium은 자막만 담당
    for attempt in range(1, 3):
        try:
            if attempt > 1:
                print(f"   🔄 재시도 {attempt}/2")
                driver.refresh()
                time.sleep(5)
            else:
                driver.get(url)
                time.sleep(4)

            wait = WebDriverWait(driver, 10)

            # 더보기
            try:
                expand_btn = driver.find_element(By.ID, "expand")
                driver.execute_script("arguments[0].click();", expand_btn)
                time.sleep(2)
            except:
                pass

            # 스크립트 버튼
            script_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "ytd-video-description-transcript-section-renderer button")
                )
            )

            driver.execute_script("arguments[0].click();", script_btn)

            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "ytd-transcript-segment-renderer")
                )
            )

            segments = driver.find_elements(
                By.CSS_SELECTOR,
                "ytd-transcript-segment-renderer .segment-text"
            )

            text = " ".join(seg.text for seg in segments)

            if len(text) > 20:
                info["transcript"] = text
                return info

        except Exception as e:
            if attempt == 1:
                print("   ⚠️ 자막 로딩 실패, 재시도")
            else:
                print("   ❌ 자막 최종 실패")

    return info
# ------------------------------------------------------------------
# [함수 3] GPT 포맷팅
# ------------------------------------------------------------------
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
        response = chain.invoke({"transcript": raw_transcript[:15000]})
        return response.content
    except Exception as e:
        return f"GPT 에러: {e}"

# ------------------------------------------------------------------
# [메인 실행]
# ------------------------------------------------------------------
if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)

    print(f"🚀 총 {len(df)}개 영상 크롤링 시작...")

    for index, row in df.iterrows():
        print(f"\n[{index+1}/{len(df)}] '{row['video_title']}' 진행 중...")
        
        info = get_info_via_selenium(driver, row['video_url'])
        
        gpt_result = ""
        if info['transcript']:
            print(f"   ✅ 자막 확보 성공! GPT 정리 요청...")
            gpt_result = format_recipe_with_gpt(info['transcript'])
        else:
            print("   ❌ 자막 없음")
            gpt_result = "[]"

        vid_id = get_video_id(row['video_url'])
        thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg" if vid_id else ""

        data = {
            'id': row['recipe_video_id'],
            'title': row['video_title'],
            'url': row['video_url'],
            'thumbnail': thumbnail_url,
            'view_count': info['view_count'],
            'duration': info['duration'],
            'recipe_json': gpt_result
        }
        
        df_save = pd.DataFrame([data])
        
        if not os.path.exists(OUTPUT_FILE):
            df_save.to_csv(OUTPUT_FILE, index=False, mode='w', encoding='utf-8-sig')
        else:
            df_save.to_csv(OUTPUT_FILE, index=False, mode='a', header=False, encoding='utf-8-sig')

    print("\n🎉 완료! data 폴더를 확인하세요.")
    driver.quit()