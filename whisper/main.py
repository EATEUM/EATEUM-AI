import os
import time
import json
import random
import requests
import pandas as pd
import yt_dlp
from dotenv import load_dotenv
from openai import OpenAI

# 1. 현재 파일(main.py)의 위치를 기준으로 경로 설정 (가장 안전함)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) # whisper 폴더
BASE_DIR = os.path.dirname(CURRENT_DIR)                # EATEUM-AI (상위) 폴더
DATA_DIR = os.path.join(BASE_DIR, 'data')              # data 폴더
ENV_PATH = os.path.join(BASE_DIR, '.env')              # .env 파일

# .env 로드
load_dotenv(dotenv_path=ENV_PATH)

# API 키 확인
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

if not api_key:
    print("⚠️ 오류: .env 파일에 OPENAI_API_KEY가 없습니다.")
    exit()

client = OpenAI(api_key=api_key.strip(), base_url=api_base)

# 입력/출력 파일 경로 (절대 경로 사용)
INPUT_CSV = os.path.join(DATA_DIR, 'recipes_data.csv')
OUTPUT_CSV = os.path.join(DATA_DIR, 'recipes_scraper.csv')

def download_json_subtitles(url):
    """유튜브 자막 URL(JSON3 포맷)을 텍스트로 변환"""
    try:
        res = requests.get(url)
        data = res.json()
        full_text = ""
        for event in data.get('events', []):
            if 'segs' in event:
                for seg in event['segs']:
                    if 'utf8' in seg:
                        full_text += seg['utf8'] + " "
        return full_text.strip()
    except Exception:
        return None

def transcribe_audio_with_whisper(video_url):
    """자막 없을 때 Whisper로 변환"""
    print("      🎤 자막 없음! Whisper 변환 시도...")
    # 임시 파일도 data 폴더에 저장 (권한 문제 방지)
    temp_audio = os.path.join(DATA_DIR, f"temp_{int(time.time())}")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_audio,
        'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '128'}],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        mp3_filename = temp_audio + ".mp3"
        
        with open(mp3_filename, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, language="ko"
            )
        
        if os.path.exists(mp3_filename): os.remove(mp3_filename)
        return transcript.text
    except Exception as e:
        print(f"      ❌ Whisper 실패: {e}")
        # 실패 시 잔여 파일 삭제
        if os.path.exists(temp_audio + ".mp3"): os.remove(temp_audio + ".mp3")
        return ""

def summarize_with_gpt(text):
    """텍스트를 받아 요리 순서 JSON List로 변환"""
    if not text or len(text) < 50: return "[]"
    
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
    
    formatted_prompt = template.format(transcript=text[:25000])

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": formatted_prompt}],
            temperature=0
        )
        
        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("\n", 1)[0]
        
        return content.strip()
        
    except Exception as e:
        print(f"      ⚠️ GPT 요약 실패: {e}")
        return "[]"

def process_video(video_url, recipe_video_id):
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['ko', 'en'],
        'quiet': True,
        'no_warnings': True,
    }

    transcript_text = ""
    video_data = {
        'recipe_video_id': recipe_video_id,
        'video_title': None,
        'video_url': video_url,
        'thumbnail_url': None,
        'view_count': 0,
        'duration': "0:00",
        'steps_json': "[]"
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            video_data['video_title'] = info.get('title')
            video_data['thumbnail_url'] = info.get('thumbnail')
            video_data['view_count'] = info.get('view_count')
            video_data['duration'] = info.get('duration_string')

            captions = info.get('requested_subtitles')
            if captions:
                sub_url = captions.get('ko', {}).get('url')
                if not sub_url: sub_url = captions.get('en', {}).get('url')
                if sub_url: transcript_text = download_json_subtitles(sub_url)

    except Exception as e:
        print(f"   ⚠️ yt-dlp 에러: {e}")
        return None

    if not transcript_text:
        transcript_text = transcribe_audio_with_whisper(video_url)

    if transcript_text:
        print(f"      ✅ 자막 확보! ({len(transcript_text)}자) GPT 요약 중...")
        steps_json = summarize_with_gpt(transcript_text)
        video_data['steps_json'] = steps_json
    else:
        print("      ❌ 자막/오디오 추출 실패")

    return video_data

if __name__ == "__main__":
    if os.path.exists(INPUT_CSV):
        df = pd.read_csv(INPUT_CSV)
        print(f"📂 총 {len(df)}개의 레시피 URL 로드")
    else:
        print(f"❌ '{INPUT_CSV}' 파일 없음")
        print("💡 data 폴더에 recipes_data.csv 파일을 넣어주세요.")
        exit()

    for idx, row in df.iterrows():
        url = row.get('video_url')
        rec_id = row.get('recipe_video_id')
        
        if not url or pd.isna(url): continue
            
        print(f"\n▶️ [{idx+1}/{len(df)}] 처리 중: {row.get('video_title', '제목없음')}")
        
        data = process_video(url, rec_id)
        
        if data:
            df_save = pd.DataFrame([data])
            if not os.path.exists(OUTPUT_CSV):
                df_save.to_csv(OUTPUT_CSV, index=False, mode='w', encoding='utf-8-sig')
            else:
                df_save.to_csv(OUTPUT_CSV, index=False, mode='a', header=False, encoding='utf-8-sig')
            
            print("   ✅ 저장 완료!")
        
        time.sleep(random.uniform(5, 10))

    print(f"\n🎉 작업 완료! '{OUTPUT_CSV}' 확인.")