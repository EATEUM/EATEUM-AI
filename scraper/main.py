import os
import time
import random
import pandas as pd
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

INPUT_FILE = os.path.join(DATA_DIR, 'recipes_data.csv')
OUTPUT_FILE = os.path.join(DATA_DIR, 'recipes_scraper.csv')

if os.path.exists(INPUT_FILE):
    df = pd.read_csv(INPUT_FILE)
    print(f"📂 원본 데이터({INPUT_FILE}) 로드 완료: 총 {len(df)}개")
else:
    print(f"❌ 오류: '{INPUT_FILE}' 파일이 없습니다.")
    exit()

def get_video_id(url):
    video_id = None
    if isinstance(url, str):
        if 'v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
        elif 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]
    return video_id

# [핵심] Selenium 봇 탐지 우회 및 강력한 자막 추출
def get_info_via_selenium(driver, url):
    info = { "transcript": None, "view_count": 0, "duration": "0:00" }
    
    if not isinstance(url, str): return info

    video_id = get_video_id(url)
    
    # API로 조회수 가져오기 (실패해도 크롤링은 계속)
    if video_id:
        try:
            info["view_count"], info["duration"] = get_video_stats(video_id)
        except:
            pass

    # 크롤링 재시도 (최대 2번)
    for attempt in range(1, 3):
        try:
            driver.get(url)
            
            # 1. 페이지 로딩 대기 (랜덤 딜레이로 사람인 척)
            time.sleep(random.uniform(3, 5))
            
            wait = WebDriverWait(driver, 10)

            # 2. '더보기' 버튼 찾아서 누르기 (설명창 확장)
            try:
                expand_btn = wait.until(EC.element_to_be_clickable((By.ID, "expand")))
                expand_btn.click()
                time.sleep(1)
            except:
                pass # 이미 펼쳐져 있거나 없으면 패스

            # 3. '스크립트 표시' 버튼 찾기 (여러 방법 시도)
            script_btn = None
            try:
                # 방법 A: 최신 유튜브 UI (설명창 내부 버튼)
                script_btn = driver.find_element(By.CSS_SELECTOR, "ytd-video-description-transcript-section-renderer button")
            except:
                try:
                    # 방법 B: 텍스트로 찾기 (XPath) - 가장 강력함
                    script_btn = driver.find_element(By.XPATH, "//button[contains(@aria-label, '스크립트') or .//*[contains(text(), '스크립트')]]")
                except:
                    pass

            if script_btn:
                # 자바스크립트로 강제 클릭 (가려져 있어도 클릭됨)
                driver.execute_script("arguments[0].click();", script_btn)
                time.sleep(2)
                
                # 4. 자막 텍스트 긁어오기
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-transcript-segment-renderer")))
                segments = driver.find_elements(By.CSS_SELECTOR, "ytd-transcript-segment-renderer .segment-text")
                
                # 텍스트 합치기
                text = " ".join([seg.text for seg in segments]).replace("\n", " ")
                
                if len(text) > 50:
                    info["transcript"] = text
                    return info # 성공하면 즉시 리턴
            
            print(f"   ⚠️ 시도 {attempt}: 자막 버튼을 못 찾았습니다.")

        except Exception as e:
            print(f"   ⚠️ 시도 {attempt} 에러: {e}")
            time.sleep(3) # 에러 나면 잠시 대기

    return info

def format_recipe_with_gpt(raw_transcript):
    if not raw_transcript or len(raw_transcript) < 50:
        return "[]"

    llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=api_key, base_url=api_base)

    template = """
    너는 요리 레시피를 정리하는 전문 에디터 AI야.
    제공된 [자막]을 분석해서 불필요한 사담(인사, 맛 평가, 광고 등)은 모두 제거하고, 핵심 '요리 과정'만 추출해줘.

    [작성 규칙]
    1. 반드시 아래 예시와 같은 **순수 JSON 리스트 포맷**만 출력할 것. (Markdown 코드 블록 사용 금지)
    2. 전체 구조는 객체들의 리스트(`[...]`)여야 한다.
    3. 'step_title'은 해당 단계의 핵심 행동을 10글자 내외로 요약.
    4. 'step_detail'은 구체적인 행동과 재료 손질법, 조리 시간을 포함하여 명확한 문장으로 서술.
    5. 재료 손질 과정이 있다면 **반드시 1번 스텝**에 모아서 정리할 것.

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
        response = chain.invoke({"transcript": raw_transcript[:20000]})
        clean_content = response.content.strip()
        if clean_content.startswith("```"):
            clean_content = clean_content.split("\n", 1)[1]
            if clean_content.endswith("```"):
                clean_content = clean_content.rsplit("\n", 1)[0]
        return clean_content
    except Exception as e:
        print(f"GPT 에러: {e}")
        return "[]"

# [메인 실행]
if __name__ == "__main__":
    # 봇 탐지 우회 옵션 설정
    chrome_options = Options()
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    # ⭐ 봇 탐지 방지 핵심 옵션
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User-Agent 설정 (일반 브라우저처럼 보이게)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    
    # navigator.webdriver 속성 숨기기 (봇 탐지 우회)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    print(f"🚀 총 {len(df)}개 영상 크롤링 시작...")

    for index, row in df.iterrows():
        url = row.get('video_url')
        print(f"\n[{index+1}/{len(df)}] '{row.get('video_title', '제목없음')}' 진행 중...")
        
        if not url: continue

        info = get_info_via_selenium(driver, url)
        
        gpt_result = "[]"
        if info['transcript']:
            print(f"   ✅ 자막 확보 성공! ({len(info['transcript'])}자) GPT 정리 요청...")
            gpt_result = format_recipe_with_gpt(info['transcript'])
        else:
            print("   ❌ 자막 없음")

        vid_id = get_video_id(url)
        thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg" if vid_id else ""

        data = {
            'recipe_video_id': row.get('recipe_video_id'),
            'video_title': row.get('video_title'),
            'video_url': url,
            'thumbnail_url': thumbnail_url,
            'view_count': info['view_count'],
            'duration': info['duration'],
            'steps_json': gpt_result
        }
        
        df_save = pd.DataFrame([data])
        
        if not os.path.exists(OUTPUT_FILE):
            df_save.to_csv(OUTPUT_FILE, index=False, mode='w', encoding='utf-8-sig')
        else:
            df_save.to_csv(OUTPUT_FILE, index=False, mode='a', header=False, encoding='utf-8-sig')

    print("\n🎉 완료! data 폴더를 확인하세요.")
    driver.quit()