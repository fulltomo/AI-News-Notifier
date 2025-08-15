import os
import requests
import json
from datetime import datetime, timedelta, timezone
import google.generativeai as genai

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not all([GNEWS_API_KEY, GEMINI_API_KEY, DISCORD_WEBHOOK_URL]):
    raise ValueError("APIキーまたはWebhook URLが設定されていません")

genai.configure(api_key=GEMINI_API_KEY)

def get_ai_news():
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    url = (f"https://gnews.io/api/v4/search?q=AI&lang=ja&max=5&"
           f"from={yesterday.strftime('%Y-%m-%dT%H:%M:%SZ')}&"
           f"to={now.strftime('%Y-%m-%dT%H:%M:%SZ')}&token={GNEWS_API_KEY}")

    try:
        return requests.get(url).json().get("articles", [])
    except:
        return []

def summarize_with_gemini(content):
    if not content:
        return {"summary": "内容が取得できませんでした", "category": "不明"}

    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        "以下のAIニュースを3文で要約し、"
        "['技術開発', 'ビジネス応用', '倫理・規制', '研究', 'その他']"
        "からカテゴリを選んで、必ず以下の形式で返してください：\n"
        '{"summary": "要約文", "category": "カテゴリ名"}\n\n'
        f"記事: {content}"
    )

    try:
        response = model.generate_content(prompt,
            generation_config=genai.types.GenerationConfig(response_mime_type="application/json"))
        return json.loads(response.text)
    except:
        return {"summary": "要約に失敗しました", "category": "エラー"}

def send_to_discord(articles):
    embeds = []
    for article in articles:
        published_utc = datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00'))
        published_jst = published_utc.astimezone(timezone(timedelta(hours=9)))

        embeds.append({
            "title": f"📰 {article['title']}",
            "url": article['url'],
            "description": article['summary_data']['summary'],
            "color": 0x5865F2,
            "fields": [{"name": "カテゴリ", "value": f"`{article['summary_data']['category']}`", "inline": True}],
            "footer": {"text": f"公開日: {published_jst.strftime('%Y-%m-%d %H:%M')}"}
        })

    payload = {
        "username": "AI News Bot",
        "content": f"## 📢 今日のAIニュース ({datetime.now().strftime('%Y-%m-%d')})",
        "embeds": embeds
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload).raise_for_status()
    except:
        pass

def main():
    articles = get_ai_news()
    if not articles:
        return

    processed_articles = []
    for article in articles:
        content = article.get('description') or article.get('content', '')
        summary_data = summarize_with_gemini(content)
        processed_articles.append({
            "title": article['title'],
            "url": article['url'],
            "publishedAt": article['publishedAt'],
            "summary_data": summary_data
        })

    send_to_discord(processed_articles)

if __name__ == "__main__":
    main()
