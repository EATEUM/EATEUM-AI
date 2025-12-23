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

INPUT_FILE = os.path.join(DATA_DIR, 'recipes_data.csv')  # 읽어올 파일
OUTPUT_FILE = os.path.join(DATA_DIR, 'recipes_scraper.csv') # 저장할 파일

# --- [수정된 부분] 실제 데이터 로드 ---
if os.path.exists(INPUT_FILE):
    df = pd.read_csv(INPUT_FILE)
    print(f"📂 원본 데이터({INPUT_FILE}) 로드 완료: 총 {len(df)}개")
else:
    print(f"❌ 오류: '{INPUT_FILE}' 파일이 없습니다.")
    exit()
# -----------------------------------

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
        model="gpt-4o", 
        temperature=0,
        api_key=api_key,
        base_url=api_base
    )

    template = """
    너는 요리 레시피를 정리하는 전문 에디터 AI야.
    제공된 [자막]을 분석해서 불필요한 사담(인사, 맛 평가, 광고 등)은 모두 제거하고, 핵심 '요리 과정'만 추출해줘.

    [작성 규칙]
    1. 반드시 아래의 순수 JSON 리스트 포맷만 출력할 것. (Markdown 코드 블록 사용 금지)
    2. 전체 구조는 객체들의 리스트(`[...]`)여야 한다.
    3. 'step_title'은 해당 단계의 핵심 행동을 10글자 내외로 요약.
    4. 'step_detail'은 구체적인 행동과 재료 손질법, 조리 시간을 포함하여 명확한 문장으로 서술.
    5. 재료 손질 과정이 있다면 1번 스텝에 모아서 정리할 것.

    [출력 예시]
    [
        {{"step": 1, "step_title": "재료 손질", "step_detail": "양파는 채 썰고 대파는 송송 썰어 준비합니다."}},
        {{"step": 2, "step_title": "재료 볶기", "step_detail": "달궈진 팬에 식용유를 두르고 손질한 야채를 중불에서 볶습니다."}},
        {{"step": 3, "step_title": "양념 하기", "step_detail": "간장 2스푼과 설탕 1스푼을 넣고 골고루 섞어줍니다."}}
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
            'recipe_video_id': row.get('recipe_video_id'),  # id -> recipe_video_id
            'video_title': row.get('video_title'),          # title -> video_title
            'video_url': row.get('video_url'),                          # url -> video_url
            'thumbnail_url': thumbnail_url,                 # thumbnail -> thumbnail_url
            'view_count': info['view_count'],
            'duration': info['duration'],
            'steps_json': gpt_result                        # recipe_json -> steps_json
        }
        
        df_save = pd.DataFrame([data])
        
        if not os.path.exists(OUTPUT_FILE):
            df_save.to_csv(OUTPUT_FILE, index=False, mode='w', encoding='utf-8-sig')
        else:
            df_save.to_csv(OUTPUT_FILE, index=False, mode='a', header=False, encoding='utf-8-sig')

    print("\n🎉 완료! data 폴더를 확인하세요.")
    driver.quit()