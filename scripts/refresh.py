"""
每日課程刷新腳本（Playwright 版）
- 使用 Playwright 模擬瀏覽器，支援動態 JavaScript 渲染頁面
- 讓 Claude 分析分類新課程
- 每個機構間隔 60 秒，避免 rate limit
"""
import os, json, time, re, asyncio
from datetime import datetime
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
    {
        'id': '商發署', 'name': '經濟部商業發展署', 'type': 'ext',
        'url': 'https://serv.gcis.nat.gov.tw/AOCAI/Course',
        'crawl_urls': [
            'https://serv.gcis.nat.gov.tw/AOCAI/Course',
        ]
    },
