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

# ======== [속도 개선] 캐시 설정 ========
CACHE = {"data": None, "timestamp": 0}
CACHE_DURATION = 300 # 300초(5분) 동안 데이터를 기억합니다.

def get_youtube_links_from_notion():
    current_time = time.time()
    
    # 캐시된 데이터가 있고, 5분이 지나지 않았다면 저장된 데이터를 바로 반환 (초고속!)
    if CACHE["data"] is not None and (current_time - CACHE["timestamp"] < CACHE_DURATION):
        print("⚡ 캐시된 데이터 사용 (빠름)")
        return CACHE["data"]

    print("⏳ 노션에서 데이터 새로 가져오는 중...")
    all_notion_pages = []
    next_cursor = None

    # 1. 노션 데이터 가져오기
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

    # 2. 데이터 가공
    for page in all_notion_pages:
        properties = page['properties']

        # 공개 여부 체크
        is_public = False
        if '공개 여부' in properties and properties['공개 여부']['checkbox']:
            is_public = True

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

        # 분류 기준: '장르' 우선
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
            grouped_videos[group_name]['videos'].append({
                'title': final_title, 'url': final_url, 'thumbnail': final_thumbnail, 'tags': final_tags
            })

    # ======== [속도 개선] 새로 가져온 데이터를 캐시에 저장 ========
    CACHE["data"] = grouped_videos
    CACHE["timestamp"] = current_time

    return grouped_videos

@app.route('/')
def index():
    grouped_data = get_youtube_links_from_notion()

    # 카테고리 코멘트
    comments = {
        "공공기관": "정부 부처 및 공공기관과 협업하여 정책을 알기 쉽게 전달하고, 기관의 신뢰도를 높이는 공식 영상을 제작했습니다.",
        "숏폼": "유튜브 쇼츠, 릴스 등 트렌드를 반영한 빠른 호흡과 임팩트 있는 세로형 숏폼 콘텐츠입니다.",
        "병원": "병원의 전문성과 환자 중심의 서비스를 강조하여, 신뢰감을 줄 수 있는 병원 홍보 영상을 제작했습니다.",
        "타이틀그래픽": "영상의 첫인상을 결정짓는 오프닝 및 타이틀 모션 그래픽 작업물입니다.",
        "인포그래픽": "복잡한 데이터나 정보를 그래픽 요소를 활용하여 이해하기 쉽게 표현한 모션그래픽 영상입니다.",
        "교육": "학습 목표를 효과적으로 달성할 수 있도록 기획된 교육용 콘텐츠입니다.",
        "브이로그": "자연스러운 일상의 순간들을 감성적인 시선으로 담아낸 브이로그 영상입니다.",
        "행사스케치": "현장의 생생한 분위기와 주요 순간들을 포착한 스케치 영상입니다.",
        "홍보영상": "기업이나 제품의 핵심 가치를 매력적으로 전달하는 프로모션 영상입니다.",
        "인터뷰": "출연자의 진솔한 이야기를 깊이 있게 담아낸 인터뷰 콘텐츠입니다.",
        "기타영상": "다양한 시도와 주제를 담은 영상 프로젝트 모음입니다."
    }

    sorted_items = sorted(grouped_data.items(), key=lambda x: x[1]['sort_order'])
    ordered_channels = []
    for name, info in sorted_items:
        ordered_channels.append({
            'name': name, 'slug': slugify(name), 'videos': info['videos'], 'comment': comments.get(name, "")
        })

    return render_template('index.html', ordered_channels=ordered_channels, comments=comments)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81))
    app.run(host='0.0.0.0', port=port)