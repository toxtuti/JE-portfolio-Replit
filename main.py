import os
import time
from flask import Flask, render_template
from notion_client import Client
import re

app = Flask(__name__)

# 환경 변수 가져오기
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_API_KEY)

# 유튜브 ID 추출
def get_youtube_video_id(url):
    if not url: return None
    match = re.search(r'(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None

# 슬러그 변환
def slugify(text):
    import re
    if not text: return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9가-힣\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    return text.strip('-')

# 캐시 설정
CACHE = {"data": None, "timestamp": 0}
CACHE_DURATION = 300 

def get_youtube_links_from_notion():
    current_time = time.time()
    
    # 5분 이내면 캐시 사용
    if CACHE["data"] is not None and (current_time - CACHE["timestamp"] < CACHE_DURATION):
        return CACHE["data"]

    all_notion_pages = []
    next_cursor = None

    while True:
        try:
            response = notion.databases.query(
                database_id=NOTION_DATABASE_ID,
                start_cursor=next_cursor,
                sorts=[{"property": "정렬 순서", "direction": "ascending"}]
            )
            all_notion_pages.extend(response['results'])
            if not response['has_more']: break
            next_cursor = response['next_cursor']
        except Exception as e:
            print(f"Notion API 에러: {e}")
            break

    grouped_videos = {}

    for page in all_notion_pages:
        properties = page['properties']

        # 공개 여부 체크
        is_public = False
        if '공개 여부' in properties and properties['공개 여부']['checkbox']:
            is_public = True

        # [NEW] 메인 노출 여부 체크
        is_featured = False
        if '메인 노출' in properties and properties['메인 노출']['checkbox']:
            is_featured = True

        # 제목
        final_title = "제목 없음"
        if '제목' in properties and properties['제목']['title']:
            final_title = properties['제목']['title'][0]['plain_text']
        elif 'Name' in properties and properties['Name']['title']:
            final_title = properties['Name']['title'][0]['plain_text']

        # 태그
        final_tags = []
        if '태그' in properties and properties['태그']['multi_select']:
            final_tags = [tag['name'] for tag in properties['태그']['multi_select']]

        # 링크 및 썸네일
        original_url = ""
        if '유튜브 링크' in properties and properties['유튜브 링크']['url']:
            original_url = properties['유튜브 링크']['url']
        elif 'YouTube URL' in properties and properties['YouTube URL']['url']:
            original_url = properties['YouTube URL']['url']

        youtube_id = get_youtube_video_id(original_url)
        final_thumbnail = f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg" if youtube_id else "https://via.placeholder.com/300x180?text=No+Image"
        
        if '썸네일 URL' in properties and properties['썸네일 URL']['url']:
             final_thumbnail = properties['썸네일 URL']['url']

        final_url = original_url if is_public else "#"
        if not is_public: final_title = "🚫 " + final_title

        # 분류 기준
        group_name = "기타영상"
        if '장르' in properties and properties['장르']['select']:
            group_name = properties['장르']['select']['name']
        
        # 정렬 순서
        sort_order = 9999
        if '정렬 순서' in properties and properties['정렬 순서']['number'] is not None:
            sort_order = properties['정렬 순서']['number']

        # 데이터 저장
        if final_title and final_url:
            if group_name not in grouped_videos:
                grouped_videos[group_name] = {'sort_order': sort_order, 'videos': []}
            
            grouped_videos[group_name]['sort_order'] = min(grouped_videos[group_name]['sort_order'], sort_order)
            
            # 딕셔너리에 is_featured 정보도 함께 저장
            grouped_videos[group_name]['videos'].append({
                'title': final_title, 
                'url': final_url, 
                'thumbnail': final_thumbnail, 
                'tags': final_tags,
                'is_featured': is_featured
            })

    CACHE["data"] = grouped_videos
    CACHE["timestamp"] = current_time

    return grouped_videos

# 1. 홈 화면 (메인 페이지)
@app.route('/')
def index():
    grouped_data = get_youtube_links_from_notion()
    
    # [NEW] 노션에서 '메인 노출' 체크된 영상만 골라내기
    featured_videos = []
    for group in grouped_data.values():
        for video in group['videos']:
            if video.get('is_featured'):
                featured_videos.append(video)
    
    # 만약 체크를 깜빡하고 안 했다면, 예비로 아무거나 4개 가져오기 (빈 화면 방지)
    if not featured_videos:
        for group in grouped_data.values():
            featured_videos.extend(group['videos'])
            if len(featured_videos) >= 4: break

    # 메인에는 딱 4개까지만 넘겨줍니다 (그리드 디자인 유지를 위해)
    return render_template('index.html', featured_videos=featured_videos[:4])


# 2. 전체 프로젝트 화면 (All Videos)
@app.route('/projects')
def projects():
    grouped_data = get_youtube_links_from_notion()
    
    sorted_items = sorted(grouped_data.items(), key=lambda x: x[1]['sort_order'])
    ordered_channels = []
    for name, info in sorted_items:
        ordered_channels.append({
            'name': name, 'slug': slugify(name), 'videos': info['videos']
        })

    return render_template('projects.html', ordered_channels=ordered_channels)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81))
    app.run(host='0.0.0.0', port=port)