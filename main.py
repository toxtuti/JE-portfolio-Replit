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

# 유튜브 영상 ID 추출 함수 (썸네일 생성에 사용)
def get_youtube_video_id(url):
    """다양한 유튜브 URL 형식에서 11자리 영상 ID를 추출합니다."""
    if not url:
        return None
    match = re.search(r'(?:v=|youtu\.be/|embed/|shorts/)([a-zA-Z0-9_-]{11})', url)
    if match:
        return match.group(1)
    return None # 영상 ID를 찾지 못한 경우

# 채널 이름을 HTML ID로 사용할 수 있는 'slug' 형태로 변환하는 함수
def slugify(text):
    import re
    if not text:
        return ""
    text = text.lower() # 소문자로 변환
    text = re.sub(r'[^a-z0-9가-힣\s-]', '', text) # 한글, 알파벳, 숫자, 공백, 하이픈 외 제거
    text = re.sub(r'[\s]+', '-', text) # 공백을 하이픈으로 대체
    text = text.strip('-') # 양 끝 하이픈 제거
    return text

def get_youtube_links_from_notion():
    """
    Notion 데이터베이스에서 모든 영상을 가져와 공개 여부에 따라 링크를 다르게 처리합니다.
    '영상구분' 채널별로 그룹화합니다. (페이지네이션 및 정렬 적용)
    """
    all_notion_pages = [] 
    next_cursor = None     

    while True: 
        try:
            response = notion.databases.query(
                database_id=NOTION_DATABASE_ID,
                start_cursor=next_cursor,
                sorts=[
                    {
                        "property": "정렬 순서", 
                        "direction": "ascending"
                    }
                ]
            )

            print("Notion API 응답:", response) # <-- 이 줄이 로그에 데이터를 출력합니다.

            all_notion_pages.extend(response['results']) 

            if not response['has_more']: 
                break

            next_cursor = response['next_cursor'] 

        except Exception as e:
            print(f"Error fetching Notion data during pagination: {e}")
            import traceback
            traceback.print_exc() 
            break 

    grouped_videos_with_sort_key = {} 

    def extract_url_from_property(prop_value):
        if prop_value and prop_value['type'] == 'url' and prop_value['url']:
            return prop_value['url']
        return ""

    for page in all_notion_pages:
        properties = page['properties']

        is_public = False
        if '공개 여부' in properties and properties['공개 여부']['type'] == 'checkbox': 
            is_public = properties['공개 여부']['checkbox']

        final_title = ""
        final_url = ""
        final_thumbnail = ""
        final_tags = []

        if '제목' in properties and properties['제목']['type'] == 'title' and properties['제목']['title']:
            final_title = properties['제목']['title'][0]['plain_text']
        elif 'Name' in properties and properties['Name']['type'] == 'title' and properties['Name']['title']:
            final_title = properties['Name']['title'][0]['plain_text']
        else:
            final_title = "제목 없음"

        if '태그' in properties and properties['태그']['type'] == 'multi_select':
            final_tags = [tag['name'] for tag in properties['태그']['multi_select']]

        original_youtube_url = ""
        if '유튜브 링크' in properties and properties['유튜브 링크']['type'] == 'url' and properties['유튜브 링크']['url']: 
            original_youtube_url = properties['유튜브 링크']['url']
        elif 'YouTube URL' in properties and properties['YouTube URL']['type'] == 'url' and properties['YouTube URL']['url']: 
            original_youtube_url = properties['YouTube URL']['url']

        youtube_id = get_youtube_video_id(original_youtube_url)

        if youtube_id:
            final_thumbnail = f"https://img.youtube.com/vi/{youtube_id}/hqdefault.jpg" 

        manual_thumbnail_prop_name = '썸네일 URL' 
        if not final_thumbnail and manual_thumbnail_prop_name in properties:
            final_thumbnail = extract_url_from_property(properties[manual_thumbnail_prop_name])

        DEFAULT_PLACEHOLDER_THUMBNAIL = "https://via.placeholder.com/300x180?text=No+Image+Available"
        if not final_thumbnail:
            final_thumbnail = DEFAULT_PLACEHOLDER_THUMBNAIL

        if is_public:
            final_url = original_youtube_url
            if not final_url:
                final_url = "#" 
        else:
            final_url = "#" 
            final_title = "🚫 " + final_title 

        channel_name = "미분류" 
        if '영상구분' in properties and properties['영상구분']['type'] == 'select': 
            if properties['영상구분']['select']:
                channel_name = properties['영상구분']['select']['name']

        sort_order = 9999 
        if '정렬 순서' in properties and properties['정렬 순서']['type'] == 'number' and properties['정렬 순서']['number'] is not None:
            sort_order = properties['정렬 순서']['number']

        if final_title and final_url and final_thumbnail: 
            if channel_name not in grouped_videos_with_sort_key:
                grouped_videos_with_sort_key[channel_name] = {'sort_order': sort_order, 'videos': []}

            grouped_videos_with_sort_key[channel_name]['sort_order'] = min(grouped_videos_with_sort_key[channel_name]['sort_order'], sort_order)
            grouped_videos_with_sort_key[channel_name]['videos'].append({
                'title': final_title,
                'url': final_url,
                'thumbnail': final_thumbnail,
                'tags': final_tags
            })

    return grouped_videos_with_sort_key

@app.route('/')
def index():
    grouped_youtube_data_with_sort = get_youtube_links_from_notion()

    channel_comments = {
        "웅이지니": "웅진씽크빅 유튜브 채널 '웅이지니'에서 제작한 교육 콘텐츠 영상들입니다. 아이들의 학습 흥미를 유발하는 다양한 기획과 편집으로 참여했습니다.",
        "총리실TV": "총리실 공식 유튜브 채널의 주요 영상들입니다. 사회 현안을 쉽고 재미있게 전달하기 위한 기획과 촬영, 편집을 담당했습니다.", 
        "팀브릭스": "팀브릭스에서 대리 및 PD로서 영상 제작 전반을 관리하고 제작한 프로젝트들입니다.", 
        "북클럽": "북클럽 관련 영상 프로젝트들입니다.", 
        "농업기술원": "농업기술원과 협력하여 제작한 홍보 및 교육 영상들입니다.", 
        "Jieun Kim's Pick": "김지은 영상 제작자가 직접 선정한 추천 작업물입니다.", 
        "기타 채널": "다양한 주제와 클라이언트의 요구에 맞춰 제작한 영상 프로젝트들입니다.",
        "미분류": "채널 정보가 없거나 분류되지 않은 영상들입니다." 
    }

    sorted_channel_items = sorted(
        grouped_youtube_data_with_sort.items(),
        key=lambda item: item[1]['sort_order'] 
    )

    ordered_channels_for_template = []
    for channel_name, channel_info in sorted_channel_items:
        ordered_channels_for_template.append({
            'name': channel_name,
            'slug': slugify(channel_name), 
            'videos': channel_info['videos'],
            'comment': channel_comments.get(channel_name, "")
        })

    return render_template('index.html', ordered_channels=ordered_channels_for_template, comments=channel_comments)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81)) 
    app.run(host='0.0.0.0', port=port)