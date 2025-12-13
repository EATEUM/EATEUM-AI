import os
import time
import pandas as pd
import json
import random
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
api_base = os.getenv("OPENAI_API_BASE")

if not api_key:
    print("⚠️ 경고: .env 파일에서 OPENAI_API_KEY를 찾을 수 없습니다.")

client = OpenAI(
    api_key=api_key,
    base_url=api_base
)

csv_file_path = 'data/recipes_data.csv'


try:
    df = pd.read_csv(csv_file_path)
    print(f"📂 '{csv_file_path}' 파일을 성공적으로 불러왔습니다.")
    print(f"총 {len(df)}개의 레시피 데이터를 처리합니다.")
except FileNotFoundError:
    print(f"❌ '{csv_file_path}' 파일을 찾을 수 없습니다.")
    df = pd.DataFrame()

def get_video_transcript(video_url):
    if not isinstance(video_url, str):
        return None

    try:
        # 유튜브 영상 ID 추출
        video_id = ""
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be" in video_url:
            video_id = video_url.split("/")[-1].split("?")[0]
        
        if not video_id:
            print(f"⚠️ 영상 ID 추출 실패: {video_url}")
            return None

        print(f"   🎬 동영상 {video_id} 의 자막을 가져오는 중...")

        # ✅ [수정됨] 사용자 요청 방식: 인스턴스 생성 -> fetch 호출
        ytt_api = YouTubeTranscriptApi()
        
        # languages=['ko', 'en']: 한국어 우선, 없으면 영어
        transcript_obj = ytt_api.fetch(video_id, languages=['ko', 'en'])
        
        # ✅ 문서 내용 반영: 객체인 경우 .to_raw_data()로 딕셔너리 리스트 변환
        # (만약 일반 리스트가 반환되더라도 안전하게 처리)
        if hasattr(transcript_obj, 'to_raw_data'):
            transcript = transcript_obj.to_raw_data()
        else:
            transcript = transcript_obj

        full_text = ""
        for t in transcript:
            # 딕셔너리 접근 ('text', 'start')
            # 만약 객체라면 t.text, t.start로 접근해야 함 (호환성 확보)
            if isinstance(t, dict):
                text = t.get('text', '')
                start = t.get('start', 0.0)
            else:
                text = getattr(t, 'text', '')
                start = getattr(t, 'start', 0.0)

            minutes = int(start // 60)
            seconds = int(start % 60)
            timestamp = f"{minutes:02d}:{seconds:02d}"
            full_text += f"[{timestamp}] {text} "

        return full_text[:15000]

    except (TranscriptsDisabled, NoTranscriptFound):
        print(f"   ❌ 자막이 없는 영상입니다 (ID: {video_id})")
        return None
    except VideoUnavailable:
        print(f"   ❌ 영상을 볼 수 없습니다 (ID: {video_id})")
        return None
    except Exception as e:
        print(f"   ❌ 오류 발생: {e}")
        return None

def parse_steps_with_ai(transcript):
    if not transcript:
        return []

    prompt = f"""
아래는 요리 유튜브 영상의 자막이야.
이 내용을 바탕으로 '요리 순서(Step)'만 JSON 형식으로 정리해줘.

[규칙]
1. 인사말, 잡담 제거.
2. 각 단계의 시작 시간을 'MM:SS' 형식으로 표기.
3. description은 명확한 요리 행동으로 작성.

[출력 형식]
{{
    "steps": [
        {{"step_number": 1, "description": "...", "time_stamp": "00:30"}}
    ]
}}

[자막 내용]
{transcript}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "너는 요리 레시피 정리 전문가야."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        result = response.choices[0].message.content
        return json.loads(result).get("steps", [])

    except Exception as e:
        print(f"   ❌ AI 변환 실패: {e}")
        return []

all_steps = []

if not df.empty:
    for index, row in df.iterrows():
        video_id_key = row.get('recipe_video_id', f'unknown_{index}')
        video_url = row.get('video_url', None)
        title = row.get('video_title', 'No Title')

        if not video_url or pd.isna(video_url):
            print(f"⚠️ URL 없음 (ID: {video_id_key}) - 스킵")
            continue

        print(f"▶️ Processing [{index+1}/{len(df)}] ID {video_id_key}: {title}")

        transcript = get_video_transcript(video_url)

        if transcript:
            steps = parse_steps_with_ai(transcript)
            if steps:
                print(f"   ✅ {len(steps)}개 단계 추출 성공")
                for step in steps:
                    if isinstance(step, dict):
                        step['recipe_video_id'] = video_id_key
                        all_steps.append(step)
            else:
                print("   ⚠️ AI 응답 없음")
        else:
            print("   Pass (자막 로드 실패)")
        
        time.sleep(random.uniform(2, 5))

    if all_steps:
        os.makedirs('data', exist_ok=True)
        output_path = 'data/recipe_steps.csv'
        steps_df = pd.DataFrame(all_steps)
        
        columns = ['recipe_video_id', 'step_number', 'time_stamp', 'description']
        existing_cols = [c for c in columns if c in steps_df.columns]
        steps_df = steps_df[existing_cols]

        steps_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n🎉 변환 완료! '{output_path}' 저장됨.")
    else:
        print("\n⚠️ 생성된 데이터 없음.")
else:
    print("처리할 데이터가 없습니다.")