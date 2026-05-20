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
        'id': 'NTU', 'name': '國立臺灣大學', 'type': 'star',
        'url': 'https://course.ntu.edu.tw/',
        'crawl_urls': [
            'https://course.ntu.edu.tw/zh-TW/search/quick?q=%E4%BA%BA%E5%B7%A5%E6%99%BA%E6%85%A7',
            'https://course.ntu.edu.tw/zh-TW/search/quick?q=%E6%A9%9F%E5%99%A8%E5%AD%B8%E7%BF%92',
            'https://course.ntu.edu.tw/zh-TW/search/quick?q=%E6%B7%B1%E5%BA%A6%E5%AD%B8%E7%BF%92',
        ]
    },
    {
        'id': 'NTHU', 'name': '國立清華大學', 'type': 'star',
        'url': 'https://curricul.site.nthu.edu.tw/',
        'crawl_urls': [
            'https://curricul.site.nthu.edu.tw/p/406-1208-290365,r7880.php?Lang=zh-tw',
            'https://www.ccxp.nthu.edu.tw/ccxp/INQUIRE/JH/6/6.2/6.2.9/JH629001.php',
        ]
    },
    {
        'id': 'NYCU', 'name': '國立陽明交通大學', 'type': 'star',
        'url': 'https://timetable.nycu.edu.tw/',
        'crawl_urls': [
            'https://timetable.nycu.edu.tw/',
        ]
    },
    {
        'id': 'NCKU', 'name': '國立成功大學', 'type': 'star',
        'url': 'https://course.ncku.edu.tw/',
        'crawl_urls': [
            'https://course.ncku.edu.tw/index.php?c=qry11215',
        ]
    },
]

CATEGORIES = '02=SD-S(LLM/RAG/NLP/Agent)、03=DD(深度學習/影像/電腦視覺)、04=General(AI概論/通用)、06=DV(AI資安/驗證)、07=SD-H(AIoT/嵌入式/邊緣AI)、08=DTD(智慧製造/工業AI)'

# 已確認的教授課程（含教授姓名、系所、研究領域）
KNOWN_COURSES = {
    'NTU': [
        {
            'code': 'NTU-ML01',
            'name': '機器學習 Machine Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：李宏毅（電機工程學系）｜專長：語音辨識、機器學習、深度學習',
            'outline': '機器學習理論與實作：線性/邏輯回歸、SVM、降維、半監督學習、強化學習、深度學習，含GenAI最新內容。李宏毅教授為台灣ML領域頂尖師資，有豐富企業培訓經驗。',
            'url': 'https://speech.ee.ntu.edu.tw/~hylee/ml/2025-spring.php'
        },
        {
            'code': 'NTU-GenAI01',
            'name': '生成式AI導論 Introduction to Generative AI',
            'cat': '02',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：李宏毅（電機工程學系）｜專長：生成式AI、LLM、語音辨識',
            'outline': 'LLM原理、Prompt Engineering、RAG、AI Agent、文字/影像生成，涵蓋ChatGPT/GPT-4/Claude等主流模型。適合企業AI轉型培訓。',
            'url': 'https://speech.ee.ntu.edu.tw/~hylee/genai/2025-spring.php'
        },
        {
            'code': 'NTU-DL01',
            'name': '深度學習 Deep Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：陳縕儂（資訊工程學系）｜專長：深度學習、NLP、多模態學習',
            'outline': 'CNN/RNN/Transformer架構、注意力機制、遷移學習、模型壓縮，PyTorch實作。適合ML/AI工程師深化技術。',
            'url': 'https://www.csie.ntu.edu.tw/~yvchen/'
        },
        {
            'code': 'NTU-NLP01',
            'name': '自然語言處理 Natural Language Processing',
            'cat': '02',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：陳縕儂（資訊工程學系）｜專長：NLP、對話系統、多語言模型',
            'outline': '語言模型、BERT/GPT預訓練模型、文字分類、機器翻譯、問答系統、對話AI，兼顧理論與企業應用。',
            'url': 'https://www.csie.ntu.edu.tw/~yvchen/'
        },
        {
            'code': 'NTU-CV01',
            'name': '電腦視覺 Computer Vision',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：徐宏民（資訊工程學系）｜專長：電腦視覺、影像辨識、視覺問答',
            'outline': '影像分類、物件偵測（YOLO/DETR）、語義分割、視覺Transformer（ViT），工業視覺品檢應用。',
            'url': 'https://www.csie.ntu.edu.tw/~htsung/'
        },
        {
            'code': 'NTU-RL01',
            'name': '強化學習 Reinforcement Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：李宏毅（電機工程學系）｜專長：強化學習、AI策略優化',
            'outline': 'Q-Learning、Policy Gradient、PPO、Actor-Critic、RLHF（人類反饋強化學習），AI自主系統設計。',
            'url': 'https://speech.ee.ntu.edu.tw/~hylee/'
        },
        {
            'code': 'NTU-AIoT01',
            'name': '物聯網與人工智慧 IoT and AI',
            'cat': '07',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：AIoT、邊緣運算、嵌入式AI',
            'outline': 'IoT架構與AI整合、邊緣計算、TinyML、Raspberry Pi/Jetson部署，智慧感測器應用。',
            'url': 'https://course.ntu.edu.tw/'
        },
    ],
    'NTHU': [
        {
            'code': 'NTHU-ML01',
            'name': '機器學習 Machine Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：林軒田（資訊工程學系）｜專長：機器學習理論、統計學習',
            'outline': 'ML理論基礎：VC維度、正則化、SVM、AdaBoost、神經網路，數學嚴謹，適合深度理解ML原理的工程師。',
            'url': 'https://www.csie.ntu.edu.tw/~htlin/'
        },
        {
            'code': 'NTHU-DL01',
            'name': '深度學習 Deep Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：李濬屹（資訊工程學系）｜專長：深度學習、影像生成',
            'outline': 'CNN/RNN/GAN/Transformer/Diffusion Model，PyTorch實作，影像辨識與生成應用。',
            'url': 'https://curricul.site.nthu.edu.tw/'
        },
        {
            'code': 'NTHU-NLP01',
            'name': '自然語言處理 NLP',
            'cat': '02',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：NLP、語言模型、文字分析',
            'outline': '詞向量、語言模型、BERT/GPT、機器翻譯、情感分析，LLM微調與應用。',
            'url': 'https://curricul.site.nthu.edu.tw/'
        },
        {
            'code': 'NTHU-CV01',
            'name': '電腦視覺 Computer Vision',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：電腦視覺、影像處理',
            'outline': '影像處理基礎、特徵提取、深度學習視覺模型（ResNet/YOLO/ViT），工業瑕疵檢測應用。',
            'url': 'https://curricul.site.nthu.edu.tw/'
        },
        {
            'code': 'NTHU-AIoT01',
            'name': '智慧物聯網 AIoT',
            'cat': '07',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：IoT、嵌入式系統、邊緣AI',
            'outline': 'IoT平台與AI整合、邊緣運算、FPGA/ASIC加速、Jetson Nano部署，智慧製造應用。',
            'url': 'https://curricul.site.nthu.edu.tw/'
        },
        {
            'code': 'NTHU-SM01',
            'name': '智慧製造與工業AI',
            'cat': '08',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：工業工程與工程管理學系｜專長：智慧製造、預測維護',
            'outline': '工業4.0、製程最佳化、預測性維護、品質AI檢測，半導體/電子製造業應用案例。',
            'url': 'https://curricul.site.nthu.edu.tw/'
        },
    ],
    'NYCU': [
        {
            'code': 'NYCU-ML01',
            'name': '機器學習 Machine Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系/資訊工程學系｜專長：機器學習、資料科學',
            'outline': '監督/非監督/強化學習，SVM、決策樹、深度學習，Python實作，適合工程師系統性建立ML知識。',
            'url': 'https://timetable.nycu.edu.tw/'
        },
        {
            'code': 'NYCU-DL01',
            'name': '深度學習 Deep Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：深度神經網路、電腦視覺',
            'outline': 'CNN/RNN/GAN/Transformer，TensorFlow/PyTorch，影像辨識、自然語言處理應用，含硬體加速。',
            'url': 'https://timetable.nycu.edu.tw/'
        },
        {
            'code': 'NYCU-NLP01',
            'name': '自然語言處理 NLP',
            'cat': '02',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：NLP、對話系統、知識圖譜',
            'outline': '語言模型基礎、預訓練模型（BERT/GPT/LLaMA）、問答系統、對話AI，LLM企業應用。',
            'url': 'https://timetable.nycu.edu.tw/'
        },
        {
            'code': 'NYCU-CV01',
            'name': '電腦視覺 Computer Vision',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：電腦視覺、影像辨識、自駕車',
            'outline': '物件偵測（YOLO/Faster RCNN）、語義分割、3D視覺、視覺Transformer，工業視覺與自駕應用。',
            'url': 'https://timetable.nycu.edu.tw/'
        },
        {
            'code': 'NYCU-AIoT01',
            'name': 'AIoT智慧物聯網',
            'cat': '07',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：AIoT、嵌入式AI、FPGA',
            'outline': 'IoT感測網路、邊緣AI推論、FPGA加速設計、Jetson部署，智慧工廠與智慧城市應用。',
            'url': 'https://timetable.nycu.edu.tw/'
        },
        {
            'code': 'NYCU-HW01',
            'name': 'AI硬體加速器設計',
            'cat': '07',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：AI晶片設計、硬體加速、VLSI',
            'outline': 'DNN加速器架構、資料流設計、SRAM/DRAM優化、量化與剪枝，適合硬體工程師了解AI加速設計。',
            'url': 'https://timetable.nycu.edu.tw/'
        },
    ],
    'NCKU': [
        {
            'code': 'NCKU-ML01',
            'name': '機器學習 Machine Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：機器學習、資料探勘',
            'outline': '監督/非監督學習、特徵工程、SVM、集成學習、深度學習基礎，Python/Scikit-learn實作。',
            'url': 'https://course.ncku.edu.tw/'
        },
        {
            'code': 'NCKU-DL01',
            'name': '深度學習 Deep Learning',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：深度學習、影像辨識',
            'outline': 'CNN/RNN/Transformer架構設計，PyTorch實作，影像分類、物件偵測、影像生成應用。',
            'url': 'https://course.ncku.edu.tw/'
        },
        {
            'code': 'NCKU-NLP01',
            'name': '自然語言處理 NLP',
            'cat': '02',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：NLP、資訊擷取、知識庫',
            'outline': '文字前處理、詞向量、序列模型、BERT/GPT預訓練、機器翻譯、情感分析。',
            'url': 'https://course.ncku.edu.tw/'
        },
        {
            'code': 'NCKU-CV01',
            'name': '電腦視覺與影像處理',
            'cat': '03',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：電腦視覺、影像處理、醫學影像',
            'outline': '影像處理基礎、特徵描述、深度視覺模型、影像分割，醫療/工業視覺應用。',
            'url': 'https://course.ncku.edu.tw/'
        },
        {
            'code': 'NCKU-SM01',
            'name': '智慧製造與工業AI',
            'cat': '08',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：工業與資訊管理學系｜專長：智慧製造、品質工程、預測維護',
            'outline': '工業4.0架構、AI品質檢測、預測性維護、製程最佳化，半導體製造AI應用案例。',
            'url': 'https://course.ncku.edu.tw/'
        },
        {
            'code': 'NCKU-AIoT01',
            'name': 'AIoT與嵌入式AI系統',
            'cat': '07',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：電機工程學系｜專長：嵌入式系統、IoT、邊緣運算',
            'outline': 'AIoT系統設計、TinyML、邊緣AI部署（Raspberry Pi/Jetson），工業IoT與智慧感測應用。',
            'url': 'https://course.ncku.edu.tw/'
        },
        {
            'code': 'NCKU-GenAI01',
            'name': '生成式AI與大型語言模型應用',
            'cat': '02',
            'hours': '3學分（每週3小時）',
            'fee': '洽詢授課教授',
            'target': '授課教授：資訊工程學系｜專長：生成式AI、LLM、對話系統',
            'outline': 'LLM架構原理、RAG系統建置、AI Agent設計、Fine-tuning技術，企業生成式AI應用。',
            'url': 'https://course.ncku.edu.tw/'
        },
    ],
}


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
    existing_codes = [c['code'] for c in existing_courses if c.get('inst') == inst_id]
    known = KNOWN_COURSES.get(inst_id, [])

    new_ones = []
    for course in known:
        if course['code'] not in existing_codes:
            c = dict(course)
            c['inst'] = inst_id
            c['type'] = univ['type']
            new_ones.append(c)

    # 嘗試爬網站補充
    page_contents = []
    for crawl_url in univ.get('crawl_urls', [])[:2]:
        print('   爬取: ' + crawl_url)
        content = await fetch_page_playwright(crawl_url)
        if not content.startswith('[爬取失敗') and len(content) > 300:
            page_contents.append('[來源:' + crawl_url + ']\n' + content[:2000])
        await asyncio.sleep(3)

    if page_contents:
        known_names = [c['name'][:20] for c in known]
        existing_names = [c['name'][:20] for c in existing_courses if c.get('inst') == inst_id]
        all_existing = '、'.join(known_names + existing_names)

        prompt = (
            '你是 Realtek 研發創新學院課程顧問。\n'
            '從以下「' + univ['name'] + '」課程資訊，找出【額外的】AI相關課程。\n'
            '重點：每筆資料的 target 欄位必須填入「授課教授姓名（所屬系所）｜專長領域」。\n'
            '排除已有：' + all_existing + '\n\n'
            '網站內容：\n' + '\n'.join(page_contents) + '\n\n'
            '只回傳JSON陣列，無新課程回傳[]：\n'
            '[{"code":"' + inst_id + '-XX01","name":"課程名稱","cat":"03",'
            '"hours":"3學分","fee":"洽詢授課教授",'
            '"target":"授課教授：姓名（系所）｜專長：領域",'
            '"outline":"課程重點與適合邀請企業內訓的理由（80字）","url":"課程頁面URL"}]\n'
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
            if match:
                extra = json.loads(match.group(0))
                for s in extra:
                    s['inst'] = inst_id
                    s['type'] = univ['type']
                    name = s.get('name', '')
                    if len(name) < 3:
                        continue
                    if not any(c.get('inst') == inst_id and c.get('name', '')[:20] == name[:20]
                               for c in existing_courses + new_ones):
                        new_ones.append(s)
        except Exception as e:
            print('   API 補充失敗：' + str(e))

    return new_ones, '找到 ' + str(len(new_ones)) + ' 門課程'


async def main():
    print('大學教授課程地圖刷新 ' + datetime.now(TW).strftime('%Y-%m-%d %H:%M'))
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
        print('\n[' + str(i+1) + '/' + str(len(UNIVERSITIES)) + '] ' + univ['id'])
        new_ones, msg = await refresh_university(univ, courses)
        log['results'][univ['id']] = msg
        print('   -> ' + msg)
        if new_ones:
            courses.extend(new_ones)
            total_new += len(new_ones)
            print('   新增：' + str([c['name'] for c in new_ones]))
        if i < len(UNIVERSITIES) - 1:
            print('   等待 60 秒...')
            await asyncio.sleep(60)

    log['total_new'] = total_new
    save_courses(courses, log)
    print('\n完成！新增 ' + str(total_new) + ' 門，共 ' + str(len(courses)) + ' 筆')


if __name__ == '__main__':
    asyncio.run(main())
