import os
from flask import Flask, render_template
from notion_client import Client
import re

app = Flask(__name__)

# 환경 변수에서 Notion API 키와 데이터베이스 ID 불러오기
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")

# Notion 클라이언트 초기화
notion = Client(auth=NOTION_API_KEY)

# 유튜브 영상 ID 추출 함수
def get_youtube_video_id(url):
    if not url:
        return None
    match = re.search(r'(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    return None

# 슬러그 변환 함수
def slugify(text):
    import re
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9가-힣\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    text = text.strip('-')
    return text

def get_youtube_links_from_notion():
    all_notion_pages = []
    next_cursor = None

    while True:
        try:
            response = notion.databases.query(
                database_id=NOTION_DATABASE_ID,
                start_cursor=next_cursor,
                sorts=[{"property": "정렬 순서", "direction": "ascending"}]
            )
            print("Notion API 응답 수신 완료") # 로그 출력
            all_notion_pages.extend(response['results'])
            if not response['has_more']:
                break
            next_cursor = response['next_cursor']
        except Exception as e:
            print(f"Notion API 에러: {e}")
            break

    grouped_videos = {}

    for page in all_notion_pages:
        properties = page['properties']

        # 1. 공개 여부 확인
        is_public = False
        if '공개 여부' in properties and properties['공개 여부']['type'] == 'checkbox':
            is_public = properties['공개 여부']['checkbox']

        # 2. 제목 가져오기
        final_title = "제목 없음"
        if '제목' in properties and properties['제목']['title']:
            final_title = properties['제목']['title'][0]['plain_text']
        elif 'Name' in properties and properties['Name']['title']:
            final_title = properties['Name']['title'][0]['plain_text']

        # 3. 태그 가져오기
        final_tags = []
        if '태그' in properties and properties['태그']['multi_select']:
            final_tags = [tag['name'] for tag in properties['태그']['multi_select']]

        # 4. 유튜브 링크 및 썸네일 처리
        original_url = ""
        if '유튜브 링크' in properties and properties['유튜브 링크']['url']:
            original_url = properties['유튜브 링크']['url']
        elif 'YouTube URL' in properties and properties['YouTube URL']['url']:
            original_url = properties['YouTube URL']['url']

        youtube_id = get_youtube_video_id(original_url)
        final_thumbnail = f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg" if youtube_id else "https://via.placeholder.com/300x180?text=No+Image"

        # 썸네일 수동 설정 확인
        if '썸네일 URL' in properties and properties['썸네일 URL']['url']:
             final_thumbnail = properties['썸네일 URL']['url']

        final_url = original_url if is_public else "#"
        if not is_public:
            final_title = "🚫 " + final_title

        # 5. [핵심] 분류 기준: '장르' 속성 우선
        group_name = "기타영상" # 기본값

        if '장르' in properties and properties['장르']['select']:
            group_name = properties['장르']['select']['name']

        # '장르'가 비어있으면 콘솔에 경고 출력 (디버깅용)
        elif '장르' not in properties:
            print(f"경고: 노션에 '장르' 속성이 없습니다. 영상: {final_title}")

        # 6. 정렬 순서
        sort_order = 9999
        if '정렬 순서' in properties and properties['정렬 순서']['number'] is not None:
            sort_order = properties['정렬 순서']['number']

        # 7. 데이터 저장
        if final_title and final_url:
            if group_name not in grouped_videos:
                grouped_videos[group_name] = {'sort_order': sort_order, 'videos': []}

            # 해당 그룹의 정렬 순서를 가장 낮은 번호(우선순위 높음)로 갱신
            grouped_videos[group_name]['sort_order'] = min(grouped_videos[group_name]['sort_order'], sort_order)

            grouped_videos[group_name]['videos'].append({
                'title': final_title,
                'url': final_url,
                'thumbnail': final_thumbnail,
                'tags': final_tags
            })

    return grouped_videos

@app.route('/')
def index():
    grouped_data = get_youtube_links_from_notion()

    # 카테고리 설명 (노션 '장르' 옵션 이름과 정확히 일치해야 함)
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

    # 정렬
    sorted_items = sorted(grouped_data.items(), key=lambda x: x[1]['sort_order'])

    ordered_channels = []
    for name, info in sorted_items:
        ordered_channels.append({
            'name': name,
            'slug': slugify(name),
            'videos': info['videos'],
            'comment': comments.get(name, "")
        })

    return render_template('index.html', ordered_channels=ordered_channels, comments=comments)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81))
    app.run(host='0.0.0.0', port=port)