"""
每日課程刷新腳本（網頁爬取版）
- 直接爬取各機構課程列表頁取得真實內容
- 讓 Claude 分析分類新課程
- 每個機構間隔 60 秒，避免 rate limit
"""
import os, json, time, re
from datetime import datetime
import urllib.request
import anthropic

API_KEY = os.environ.get('ANTHROPIC_API_KEY')
if not API_KEY:
    print('❌ ANTHROPIC_API_KEY 未設定')
    exit(1)

client = anthropic.Anthropic(api_key=API_KEY)

INSTITUTIONS = [
    {
        'id': 'TCFST', 'name': '自強工業科學基金會', 'type': 'star',
        'url': 'https://edu.tcfst.org.tw',
        'crawl_urls': [
            'https://edu.tcfst.org.tw/web/tw/class/classList.asp?keyword=AI',
            'https://edu.tcfst.org.tw/web/tw/class/classList.asp?keyword=%E4%BA%BA%E5%B7%A5%E6%99%BA%E6%85%A7',
        ]
    },
    {
        'id': 'TAICA', 'name': '臺灣大專院校人工智慧學程聯盟', 'type': 'star',
        'url': 'https://taicatw.net',
        'crawl_urls': ['https://taicatw.net/course/']
    },
    {
        'id': 'UUU', 'name': '恆逸教育訓練', 'type': 'star',
        'url': 'https://uuu.com.tw',
        'crawl_urls': ['https://www.uuu.com.tw/Course/Show?keyword=AI']
    },
    {
        'id': 'PCSchool', 'name': '巨匠電腦', 'type': 'star',
        'url': 'https://business.gjunedu.com',
        'crawl_urls': ['https://business.gjunedu.com/Course/AI%E4%BA%BA%E5%B7%A5%E6%99%BA%E6%85%A7%E9%96%8B%E7%99%BC?c=2']
    },
    {
        'id': 'TibaMe', 'name': '緯育TibaMe', 'type': 'star',
        'url': 'https://business.tibame.com',
        'crawl_urls': ['https://business.tibame.com/']
    },
    {
        'id': 'III', 'name': '資訊工業策進會', 'type': 'star',
        'url': 'https://www.iiiedu.org.tw',
        'crawl_urls': [
            'https://www.iiiedu.org.tw/courses/',
            'https://www.iii.org.tw/zh-TW/news/events-and-classes',
        ]
    },
    {
        'id': 'WDA', 'name': '勞動力發展署', 'type': 'ext',
        'url': 'https://course.taiwanjobs.gov.tw',
        'crawl_urls': ['https://course.taiwanjobs.gov.tw/course/search-training']
    },
    {
        'id': 'AIA', 'name': '台灣人工智慧學校', 'type': 'ext',
        'url': 'https://aiacademy.tw',
        'crawl_urls': [
            'https://aiacademy.tw/genai2026-courses/',
            'https://aiacademy.tw/admission-llmb-tp/',
        ]
    },
]

CATEGORIES = '02=SD-S(LLM/RAG/Agent)、03=DD(深度學習/影像)、04=General(通用/主管)、06=DV(AI資安)、07=SD-H(AIoT/嵌入式)、08=DTD(智慧製造)'

def fetch_page(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; CourseBot/1.0)',
            'Accept-Language': 'zh-TW,zh;q=0.9',
            'Accept': 'text/html,application/xhtml+xml',
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            for enc in ['utf-8', 'big5', 'gbk']:
                try:
                    text = raw.decode(enc); break
                except: continue
            else:
                text = raw.decode('utf-8', errors='ignore')
            text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:3000]
    except Exception as e:
        return f'[爬取失敗: {e}]'

def load_courses():
    path = 'data/courses.json'
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f).get('courses', [])
    return []

def save_courses(courses, log):
    os.makedirs('data', exist_ok=True)
    with open('data/courses.json', 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'version': '2.0',
                'generated': datetime.now().strftime('%Y-%m-%d'),
                'total': len(courses),
                'last_refresh': datetime.now().isoformat(),
            },
            'courses': courses
        }, f, ensure_ascii=False, indent=2)
    with open('data/refresh_log.json', 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f'✅ 儲存完成，共 {len(courses)} 筆')

def refresh_institution(inst, existing_courses):
    inst_id, inst_name, inst_type = inst['id'], inst['name'], inst['type']

    # 爬取頁面
    page_contents = []
    for crawl_url in inst.get('crawl_urls', [])[:2]:
        print(f'   爬取: {crawl_url}')
        content = fetch_page(crawl_url)
        if not content.startswith('[爬取失敗'):
            page_contents.append(f'[來源:{crawl_url}]\n{content[:1500]}')
        time.sleep(2)

    if not page_contents:
        return [], '所有頁面爬取失敗'

    existing_names = [c['name'][:25] for c in existing_courses if c.get('inst') == inst_id]
    existing_str = '、'.join(existing_names[:8]) if existing_names else '無'

    prompt = f"""從以下「{inst_name}」網站內容，找出所有AI相關課程（LLM/生成式AI/機器學習/深度學習/AIoT/AI資安等）。
排除已有：{existing_str}

網站內容：
{chr(10).join(page_contents)}

只回傳JSON陣列：
[{{"code":"{inst_id}-N01","name":"課程名稱","cat":"02","type":"{inst_type}","hours":"","fee":"","target":"","outline":"50字摘要","url":"課程連結"}}]
類別：{CATEGORIES}
無新課程回傳：[]"""

    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1000,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = response.content[0].text.strip()
        match = re.search(r'\[[\s\S]*\]', raw)
        if not match:
            return [], '無 JSON'
        suggestions = json.loads(match.group(0))
        new_ones = []
        for s in suggestions:
            s['inst'] = inst_id
            name = s.get('name', '')
            if len(name) < 3:
                continue
            if not any(c.get('inst') == inst_id and c.get('name','')[:20] == name[:20] for c in existing_courses):
                new_ones.append(s)
        return new_ones, f'找到 {len(new_ones)} 門新課程'
    except Exception as e:
        return [], f'API 錯誤：{e}'

def main():
    print(f'🚀 課程刷新 {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    courses = load_courses()
    print(f'   現有：{len(courses)} 筆')
    log = {'date': datetime.now().strftime('%Y-%m-%d'), 'results': {}, 'total_new': 0}
    total_new = 0

    for i, inst in enumerate(INSTITUTIONS):
        print(f'\n[{i+1}/{len(INSTITUTIONS)}] {inst["id"]}')
        new_ones, msg = refresh_institution(inst, courses)
        log['results'][inst['id']] = msg
        print(f'   → {msg}')
        if new_ones:
            courses.extend(new_ones)
            total_new += len(new_ones)
        if i < len(INSTITUTIONS) - 1:
            print('   ⏳ 等待 60 秒...')
            time.sleep(60)

    log['total_new'] = total_new
    save_courses(courses, log)
    print(f'\n✅ 完成！新增 {total_new} 門，共 {len(courses)} 筆')

if __name__ == '__main__':
    main()
