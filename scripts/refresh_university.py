import os, json, re, asyncio
from datetime import datetime, timezone, timedelta
import anthropic

API_KEY = os.environ.get('ANTHROPIC_API_KEY')
if not API_KEY:
    print('ANTHROPIC_API_KEY 未設定')
    exit(1)

client = anthropic.Anthropic(api_key=API_KEY)
TW = timezone(timedelta(hours=8))

UNIVERSITIES = [
    {
        'id': 'NTU', 'name': '國立臺灣大學', 'type': 'ext',
        'url': 'https://course.ntu.edu.tw/',
        'crawl_urls': [
            'https://course.ntu.edu.tw/',
        ],
        'search_hint': '搜尋關鍵字：人工智慧、機器學習、深度學習、生成式AI、自然語言處理'
    },
    {
        'id': 'NTHU', 'name': '國立清華大學', 'type': 'ext',
        'url': 'https://curricul.site.nthu.edu.tw/p/406-1208-290365,r7880.php',
        'crawl_urls': [
            'https://curricul.site.nthu.edu.tw/p/406-1208-290365,r7880.php?Lang=zh-tw',
        ],
        'search_hint': 'AI、Machine Learning、Deep Learning 相關課程'
    },
    {
        'id': 'NYCU', 'name': '國立陽明交通大學', 'type': 'ext',
        'url': 'https://timetable.nycu.edu.tw/',
        'crawl_urls': [
            'https://timetable.nycu.edu.tw/',
        ],
        'search_hint': 'AI、人工智慧、機器學習相關課程'
    },
    {
        'id': 'NCKU', 'name': '國立成功大學', 'type': 'ext',
        'url': 'https://course.ncku.edu.tw/',
        'crawl_urls': [
            'https://course.ncku.edu.tw/index.php?c=qry11215',
        ],
        'search_hint': 'AI、人工智慧、機器學習、深度學習相關課程'
    },
]

CATEGORIES = '02=SD-S(LLM/RAG/Agent)、03=DD(深度學習/影像/數位設計)、04=General(通用/AI概論)、06=DV(AI資安/驗證)、07=SD-H(AIoT/嵌入式)、08=DTD(智慧製造/數位技術)'


async def fetch_page_playwright(url):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context(locale='zh-TW')).new_page()
            await page.goto(url, timeout=30000, wait_until='domcontentloaded')
            await page.wait_for_timeout(4000)
            text = await page.inner_text('body')
            await browser.close()
            return re.sub(r'\s+', ' ', text).strip()[:4000]
    except Exception as e:
        return '[爬取失敗: ' + str(e) + ']'


def fetch_page_urllib(url):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; UniversityCourseBot/1.0)',
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
            return re.sub(r'\s+', ' ', text).strip()[:4000]
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
    existing_insts = []
    if os.path.exists('data/courses.json'):
        try:
            with open('data/courses.json', 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                existing_insts = old_data.get('institutions', [])
        except Exception:
            pass
    with open('data/courses.json', 'w', encoding='utf-8') as f:
        json.dump({
            'meta': {
                'version': '2.0',
                'generated': datetime.now(TW).strftime('%Y-%m-%d'),
                'total': len(courses),
                'last_refresh': datetime.now(TW).isoformat(),
            },
            'institutions': existing_insts,
            'courses': courses
        }, f, ensure_ascii=False, indent=2)
    with open('data/university_refresh_log.json', 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print('儲存完成，共 ' + str(len(courses)) + ' 筆')


async def refresh_university(univ, existing_courses):
    inst_id = univ['id']
    inst_name = univ['name']
    search_hint = univ.get('search_hint', '')

    page_contents = []
    for crawl_url in univ.get('crawl_urls', [])[:2]:
        print('   爬取: ' + crawl_url)
        content = await fetch_page(crawl_url)
        if not content.startswith('[爬取失敗'):
            page_contents.append('[來源:' + crawl_url + ']\n' + content[:2000])
        await asyncio.sleep(3)

    # 即使爬取失敗也用 Claude 根據知識補充
    existing_names = [c['name'][:30] for c in existing_courses if c.get('inst') == inst_id]
    existing_str = '、'.join(existing_names[:10]) if existing_names else '無'

    if page_contents:
        page_text = '\n'.join(page_contents)
        content_section = '網站內容：\n' + page_text
    else:
        content_section = '（網站爬取失敗，請根據你對該校課程的知識回答）'

    prompt = (
        '你是 Realtek 研發創新學院課程顧問。\n'
        '從以下「' + inst_name + '」課程資訊，找出所有與 AI/機器學習/深度學習/自然語言處理/電腦視覺/AIoT 相關的課程。\n'
        '提示：' + search_hint + '\n'
        '排除已有課程：' + existing_str + '\n\n'
        + content_section + '\n\n'
        '篩選標準：必須符合 Realtek 8 大類別之一，且是大學正式開設課程（有課號）。\n'
        '只回傳JSON陣列，無符合課程回傳[]：\n'
        '[{"code":"' + inst_id + '-AI001","name":"課程名稱","cat":"03","type":"ext",'
        '"hours":"3學分","fee":"學費依校規","target":"大學生/研究生",'
        '"outline":"課程重點50字","url":"課程連結或學校課程系統網址"}]\n'
        '類別：' + CATEGORIES
    )

    try:
        response = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
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
            if not any(c.get('inst') == inst_id and c.get('name', '')[:25] == name[:25] for c in existing_courses):
                new_ones.append(s)
        return new_ones, '找到 ' + str(len(new_ones)) + ' 門新課程'
    except Exception as e:
        return [], 'API 錯誤：' + str(e)


async def main():
    now = datetime.now(TW).strftime('%Y-%m-%d %H:%M')
    print('大學課程刷新 ' + now)
    courses = load_courses()
    print('現有：' + str(len(courses)) + ' 筆')

    log = {
        'date': datetime.now(TW).strftime('%Y-%m-%d'),
        'type': 'university',
        'results': {},
        'total_new': 0
    }
    total_new = 0

    for i, univ in enumerate(UNIVERSITIES):
        print('\n[' + str(i+1) + '/' + str(len(UNIVERSITIES)) + '] ' + univ['id'] + ' ' + univ['name'])
        new_ones, msg = await refresh_university(univ, courses)
        log['results'][univ['id']] = msg
        print('   -> ' + msg)
        if new_ones:
            courses.extend(new_ones)
            total_new += len(new_ones)
            print('   新課程：' + str([c['name'][:25] for c in new_ones]))
        if i < len(UNIVERSITIES) - 1:
            print('   等待 90 秒...')
            await asyncio.sleep(90)

    log['total_new'] = total_new
    save_courses(courses, log)
    print('\n完成！新增 ' + str(total_new) + ' 門，共 ' + str(len(courses)) + ' 筆')


if __name__ == '__main__':
    asyncio.run(main())
