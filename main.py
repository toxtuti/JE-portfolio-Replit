import os
from flask import Flask, render_template
from notion_client import Client
import re

app = Flask(__name__)

# Notion API 키와 데이터베이스 ID를 환경 변수에서 가져옵니다.
# Vercel에 환경 변수(Environment Variables)를 설정하는 것을 잊지 마세요.
notion = Client(auth=os.environ["NOTION_API_KEY"])
database_id = os.environ["NOTION_DATABASE_ID"]

@app.route("/")
def index():
    try:
        results = fetch_all_videos()

        # '정렬 순서' 속성이 있는지 확인
        if any(item.get('properties', {}).get('정렬 순서') for item in results):
            sorted_videos = sorted(
                results,
                key=lambda x: x['properties']['정렬 순서']['number'],
                reverse=False
            )
        else:
            sorted_videos = results

        all_videos = parse_video_data(sorted_videos)

        return render_template('index.html', video_channels=all_videos)

    except Exception as e:
        print(f"An error occurred: {e}")
        return "An internal server error occurred.", 500

def fetch_all_videos():
    """노션 데이터베이스에서 모든 비디오를 가져옵니다."""
    all_results = []
    has_more = True
    start_cursor = None

    while has_more:
        query_params = {
            "database_id": database_id,
            "filter": {
                "property": "공개 여부",
                "checkbox": {
                    "equals": True
                }
            }
        }
        if start_cursor:
            query_params["start_cursor"] = start_cursor

        response = notion.databases.query(**query_params)
        all_results.extend(response['results'])

        has_more = response.get("has_more")
        start_cursor = response.get("next_cursor")

    return all_results

def parse_video_data(videos):
    """노션 비디오 데이터를 파싱하여 템플릿에 전달할 형식으로 변환합니다."""
    video_channels = {}
    for video in videos:
        properties = video['properties']

        # '제목' 속성이 없을 경우 처리
        title_property = properties.get('제목', {}).get('title')
        if title_property and title_property[0]['plain_text']:
            title = title_property[0]['plain_text']
        else:
            title = '제목 없음'

        # '유튜브 링크' 속성이 없을 경우 처리
        youtube_link = properties.get('유튜브 링크', {}).get('url', '')

        # '태그' 속성 값 가져오기
        tags_property = properties.get('태그', {}).get('multi_select', [])
        tags = [tag['name'] for tag in tags_property]

        # '영상구분' 속성이 없을 경우 처리
        channel_name = properties.get('영상구분', {}).get('select', {}).get('name', '기타')

        # '유튜브 링크'가 유효한지 확인하고 썸네일 추출
        if youtube_link and re.match(r'^https://www\.youtube\.com/watch\?v=[\w-]+$', youtube_link):
            video_id = re.search(r'v=([\w-]+)', youtube_link).group(1)
            thumbnail_url = f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg'
        else:
            # '썸네일' 속성이 없을 경우 처리
            thumbnail_property = properties.get('썸네일', {}).get('files', [])
            if thumbnail_property and 'external' in thumbnail_property[0]:
                thumbnail_url = thumbnail_property[0]['external']['url']
            else:
                thumbnail_url = 'https://via.placeholder.com/640x360.png?text=No+Image'

        video_data = {
            'title': title,
            'youtube_link': youtube_link,
            'thumbnail_url': thumbnail_url,
            'tags': tags  # tags 속성 추가
        }

        if channel_name not in video_channels:
            video_channels[channel_name] = []
        video_channels[channel_name].append(video_data)

    return video_channels

if __name__ == "__main__":
    app.run(debug=True)