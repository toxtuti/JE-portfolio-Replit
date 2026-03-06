import os
import json
import re
from flask import Flask, render_template

app = Flask(__name__)

def slugify(text):
    if not text: return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9가-힣\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    return text.strip('-')

def load_videos():
    """videos.json 파일에서 영상 데이터를 불러옵니다."""
    json_path = os.path.join(os.path.dirname(__file__), 'videos.json')
    with open(json_path, encoding='utf-8') as f:
        return json.load(f)

def get_grouped_videos():
    """장르별로 그룹화된 영상 데이터를 반환합니다."""
    videos = load_videos()
    grouped = {}

    for video in videos:
        genre = video.get('genre', '기타영상')
        sort_order = video.get('sort_order', 9999)

        if genre not in grouped:
            grouped[genre] = {'sort_order': sort_order, 'videos': []}

        grouped[genre]['sort_order'] = min(grouped[genre]['sort_order'], sort_order)
        grouped[genre]['videos'].append(video)

    return grouped


@app.route('/')
def index():
    grouped_data = get_grouped_videos()

    # 메인 노출 영상 모으기
    featured_videos = []
    for group in grouped_data.values():
        for video in group['videos']:
            if video.get('is_featured'):
                featured_videos.append(video)

    featured_videos.sort(key=lambda x: x.get('sort_order', 9999))

    # 메인 노출 영상이 없으면 그냥 앞에서 4개
    if not featured_videos:
        for group in grouped_data.values():
            featured_videos.extend(group['videos'])
            if len(featured_videos) >= 4:
                break

    return render_template('index.html', featured_videos=featured_videos[:4])


@app.route('/projects')
def projects():
    grouped_data = get_grouped_videos()

    sorted_items = sorted(grouped_data.items(), key=lambda x: x[1]['sort_order'])
    ordered_channels = []
    for name, info in sorted_items:
        ordered_channels.append({
            'name': name,
            'slug': slugify(name),
            'videos': info['videos']
        })

    return render_template('projects.html', ordered_channels=ordered_channels)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 81))
    app.run(host='0.0.0.0', port=port)