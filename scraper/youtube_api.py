# youtube_api.py
import os
import requests
import isodate
from dotenv import load_dotenv

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def get_video_stats(video_id):
    """
    return:
      view_count (int),
      duration (str, mm:ss or hh:mm:ss)
    """
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "statistics,contentDetails",
        "id": video_id,
        "key": YOUTUBE_API_KEY
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if not data.get("items"):
            return 0, "0:00"

        item = data["items"][0]

        # 조회수 (⭐ 숫자)
        view_count = int(item["statistics"].get("viewCount", 0))

        # 재생시간 (ISO → 사람이 보는 포맷)
        duration_iso = item["contentDetails"]["duration"]
        td = isodate.parse_duration(duration_iso)
        total = int(td.total_seconds())

        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        duration = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        return view_count, duration

    except Exception as e:
        print("⚠️ YouTube API 실패:", e)
        return 0, "0:00"