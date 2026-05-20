import os, json, re, asyncio
from datetime import datetime, timezone, timedelta
import anthropic

API_KEY = os.environ.get('ANTHROPIC_API_KEY')
if not API_KEY:
    print('ANTHROPIC_API_KEY 未設定')
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
    {
        'id': 'MOEA', 'name': '經濟部商業發展署', 'type': 'ext',
        'url': 'https://www.dtts.org.tw/subsidy/Course/Courselist.aspx',
        'crawl_urls': [
            'https://www.dtts.org.tw/subsidy/Course/Courselist.aspx',
            'https://serv.gcis.nat.gov.tw/AOCAI/Course',
        ]
    },
]

CATEGORIES = '02=SD-S、03=DD、04=General、06=DV、07=SD-H、08=DTD'


async def fetch_page_playwright(url):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(locale='zh-TW')).new_page()
            await page.goto(url, timeout=20000, wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)
            text = await page.inner_text('body')
            await browser.close()
            return re.sub(r'\s+', ' ', text).strip()[:3000]
    except Exception as e:
        return '[爬取失敗: ' + str(e) + ']'


def fetch_page_urllib(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'zh-TW,zh;q=0.9',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            for enc in ['utf-8', 'big5', 'gbk']:
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    continue
            else:
                text = raw.decode('utf-8', errors='ignore')
            text = re.sub(r'<[^>]+>', ' ', text)
            return re.sub(r'\s+', ' ', text).strip()[:3000]
    except Exception as e:
        return '[爬取失敗: ' + str(e) + ']'


async def fetch_page(url):
    result = await fetch_page_playwright(url)
    if result.startswith('[爬取失敗'):
        result = fetch_page_urllib(url)
    return result


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
                'generated': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d'),
                'total': len(courses),
                'last_refresh': datetime.now(timezone(timedelta(hours=8))).isoformat(),
            },
            'institutions': [],
            'courses': courses
        }, f, ensure_ascii=False, indent=2)
    with open('data/refresh_log.json', 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print('儲存完成，共 ' + str(len(courses)) + ' 筆')


async def refresh_institution(inst, existing_courses):
    inst_id = inst['id']
    inst_name = inst['name']
    inst_type = inst['type']

    page_contents = []
    for crawl_url in inst.get('crawl_urls', [])[:2]:
        print('   爬取: ' + crawl_url)
        content = await fetch_page(crawl_url)
        if not content.startswith('[爬取失敗'):
            page_contents.append('[來源:' + crawl_url + ']\n' + content[:1500])
        await asyncio.sleep(2)

    if not page_contents:
        return [], '所有頁面爬取失敗'

    existing_names = [c['name'][:25] for c in existing_courses if c.get('inst') == inst_id]
    existing_str = '、'.join(existing_names[:8]) if existing_names else '無'

    page_text = '\n'.join(page_contents)
    prompt = (
        '從以下「' + inst_name + '」網站內容，找出所有AI相關課程。\n'
        '排除已有：' + existing_str + '\n\n'
        '網站內容：\n' + page_text + '\n\n'
        '只回傳JSON陣列，無新課程回傳[]：\n'
        '[{"code":"' + inst_id + '-N01","name":"課程名稱","cat":"02","type":"' + inst_type + '","hours":"","fee":"","target":"","outline":"50字摘要","url":"課程連結"}]\n'
        '類別：' + CATEGORIES
    )

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
            if not any(c.get('inst') == inst_id and c.get('name', '')[:20] == name[:20] for c in existing_courses):
                new_ones.append(s)
        return new_ones, '找到 ' + str(len(new_ones)) + ' 門新課程'
    except Exception as e:
        return [], 'API 錯誤：' + str(e)


async def main():
    print('課程刷新 ' + datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M'))
    courses = load_courses()
    print('現有：' + str(len(courses)) + ' 筆')
    log = {'date': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d'), 'results': {}, 'total_new': 0}
    total_new = 0

    for i, inst in enumerate(INSTITUTIONS):
        print('\n[' + str(i+1) + '/' + str(len(INSTITUTIONS)) + '] ' + inst['id'])
        new_ones, msg = await refresh_institution(inst, courses)
        log['results'][inst['id']] = msg
        print('   -> ' + msg)
        if new_ones:
            courses.extend(new_ones)
            total_new += len(new_ones)
        if i < len(INSTITUTIONS) - 1:
            print('   等待 60 秒...')
            await asyncio.sleep(60)

    log['total_new'] = total_new
    save_courses(courses, log)
    print('完成！新增 ' + str(total_new) + ' 門，共 ' + str(len(courses)) + ' 筆')


if __name__ == '__main__':
    asyncio.run(main())
