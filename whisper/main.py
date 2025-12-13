import os
import time
import json
import random
import requests
import pandas as pd
import yt_dlp
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# API 키 확인
api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")
if not api_key:
    print("⚠️ 오류: .env 파일에 OPENAI_API_KEY가 없습니다.")
    exit()
else:
    api_key = api_key.strip()

client = OpenAI(api_key=api_key, base_url=api_base)

# 입력/출력 파일 경로
INPUT_CSV = 'data/recipes_data.csv'
OUTPUT_CSV = 'data/completed_recipes.csv'


def download_json_subtitles(url):
    """유튜브 자막 URL(JSON3 포맷)을 텍스트로 변환"""
    try:
        res = requests.get(url)
        data = res.json()
        full_text = ""
        # JSON 구조 파싱 (events -> segs -> utf8)
        for event in data.get('events', []):
            if 'segs' in event:
                for seg in event['segs']:
                    if 'utf8' in seg:
                        full_text += seg['utf8'] + " "
        return full_text.strip()
    except Exception:
        return None

def transcribe_audio_with_whisper(video_url):
    """[필살기] 자막이 없을 때 오디오를 다운받아 AI(Whisper)가 받아쓰기"""
    print("      🎤 자막 없음! 오디오 다운로드 및 Whisper 변환 시도...")
    
    # 임시 오디오 파일명
    temp_audio = f"temp_{int(time.time())}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_audio, # 확장자는 아래 postprocessor가 붙임 (.mp3)
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        # 1. 오디오 다운로드
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        mp3_filename = temp_audio + ".mp3"

        # 2. OpenAI Whisper API 호출
        with open(mp3_filename, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ko" # 한국어로 인식 유도
            )
        
        # 3. 임시 파일 삭제
        if os.path.exists(mp3_filename):
            os.remove(mp3_filename)
            
        return transcript.text

    except Exception as e:
        print(f"      ❌ Whisper 변환 실패: {e}")
        # 파일이 남아있다면 삭제 시도
        if os.path.exists(temp_audio + ".mp3"):
            os.remove(temp_audio + ".mp3")
        return ""

def process_video(video_url):
    """영상 URL 하나를 받아서 모든 정보를 추출하는 메인 함수"""
    
    # yt-dlp 옵션: 메타데이터와 자막 정보만 가져오기 (다운로드 X)
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True, # 자동 생성 자막도 OK
        'subtitleslangs': ['ko', 'en'],
        'quiet': True,
        'no_warnings': True,
    }

    transcript_text = ""
    video_data = {}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # 1️⃣ 메타데이터 추출 (Java가 할 필요 없음)
            video_data = {
                'video_id': info.get('id'),
                'title': info.get('title'),
                'channel_name': info.get('uploader'),
                'thumbnail_url': info.get('thumbnail'), # 고화질 자동 선택
                'view_count': info.get('view_count'),
                'upload_date': info.get('upload_date'),
                'video_url': video_url,
                'duration': info.get('duration_string')
            }

            # 2️⃣ 자막(Transcript) 추출 시도
            captions = info.get('requested_subtitles')
            if captions:
                # 한국어 -> 영어 순으로 URL 찾기
                sub_url = captions.get('ko', {}).get('url')
                if not sub_url:
                    sub_url = captions.get('en', {}).get('url')
                
                if sub_url:
                    transcript_text = download_json_subtitles(sub_url)

    except Exception as e:
        print(f"   ⚠️ yt-dlp 정보 추출 에러: {e}")
        return None

    # 3️⃣ [Plan B] 자막을 못 구했으면? Whisper 출동!
    if not transcript_text:
        transcript_text = transcribe_audio_with_whisper(video_url)

    # 4️⃣ GPT로 요리 순서 요약
    if transcript_text:
        steps_json = summarize_with_gpt(transcript_text)
        video_data['recipe_steps'] = steps_json # JSON 문자열 형태
        video_data['full_transcript'] = transcript_text[:1000] + "..." # 로그용(생략 가능)
    else:
        video_data['recipe_steps'] = "[]"
        print("      ❌ 내용 추출 실패 (자막도 없고 오디오 변환도 실패)")

    return video_data

def summarize_with_gpt(text):
    """텍스트를 받아 요리 순서 JSON으로 변환"""
    if len(text) < 50: return "[]"
    
    prompt = f"""
    아래 요리 영상 내용을 바탕으로 '요리 순서'만 JSON으로 정리해줘.
    [규칙]
    1. 불필요한 인사말, 잡담 제거.
    2. 단계별로 명확하게 설명.
    3. JSON 포맷 준수: {{ "steps": [ {{ "step": 1, "desc": "설명" }} ] }}
    
    [내용]
    {text[:15000]}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"      ⚠️ GPT 요약 실패: {e}")
        return "[]"


if __name__ == "__main__":
    # CSV 로드
    try:
        df = pd.read_csv(INPUT_CSV)
        print(f"📂 총 {len(df)}개의 레시피 URL을 로드했습니다.")
    except FileNotFoundError:
        print(f"❌ 입력 파일({INPUT_CSV})이 없습니다.")
        exit()

    results = []
    
    for idx, row in df.iterrows():
        url = row.get('video_url')
        
        # URL 없으면 패스
        if not url or pd.isna(url): 
            continue
            
        print(f"\n▶️ [{idx+1}/{len(df)}] 처리 중: {url}")
        
        # --- 핵심 처리 ---
        data = process_video(url)
        # ----------------
        
        if data:
            # 기존 CSV의 ID가 있다면 유지
            if 'recipe_video_id' in row:
                data['recipe_video_id'] = row['recipe_video_id']
            
            results.append(data)
            print("   ✅ 처리 완료!")
        
        # 차단 방지용 랜덤 대기 (3~7초)
        time.sleep(random.uniform(10, 20))

    # 결과 저장
    if results:
        final_df = pd.DataFrame(results)
        
        # 컬럼 순서 예쁘게 정렬
        cols = ['recipe_video_id', 'video_id', 'title', 'channel_name', 'thumbnail_url', 'recipe_steps', 'video_url', 'view_count']
        # 실제 있는 컬럼만 필터링
        existing_cols = [c for c in cols if c in final_df.columns]
        final_df = final_df[existing_cols]
        
        final_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"\n🎉 모든 작업 끝! '{OUTPUT_CSV}' 파일 확인해보세요.")
    else:
        print("\n⚠️ 저장할 데이터가 없습니다.")