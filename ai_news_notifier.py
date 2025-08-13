import os
import requests
import json
from datetime import datetime, timedelta
import google.generativeai as genai

# 環境変数の読み込み
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# 必要な環境変数のチェック
if not all([NEWS_API_KEY, GEMINI_API_KEY, DISCORD_WEBHOOK_URL]):
    raise ValueError("環境変数が設定されていません")

# Gemini APIの設定
genai.configure(api_key=GEMINI_API_KEY)


def get_ai_news():
    """News APIからAI関連ニュースを取得"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    url = (f"https://newsapi.org/v2/everything?"
           f"q=AI&from={yesterday}&sortBy=popularity&"
           f"language=en&pageSize=5&apiKey={NEWS_API_KEY}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get("articles", [])
    except requests.RequestException as e:
        print(f"ニュース取得エラー: {e}")
        return []


def summarize_with_gemini(content):
    """Geminiで記事を要約・カテゴリ分け"""
    if not content:
        return {"summary": "内容が取得できませんでした", "category": "不明"}

    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = (
        "以下のAIニュースを日本語で3文で要約し、"
        "['技術開発', 'ビジネス応用', '倫理・規制', '研究', 'その他']"
        "からカテゴリを選んで、必ず以下の形式で返してください：\n"
        '{"summary": "要約文", "category": "カテゴリ名"}\n\n'
        f"記事: {content}"
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"要約エラー: {e}")
        return {"summary": "要約に失敗しました", "category": "エラー"}


def send_to_discord(articles):
    """DiscordのWebhookに送信"""
    embeds = []
    
    for article in articles:
        embed = {
            "title": f"📰 {article['title']}",
            "url": article['url'],
            "description": article['summary_data']['summary'],
            "color": 0x5865F2,
            "fields": [{
                "name": "カテゴリ",
                "value": f"`{article['summary_data']['category']}`",
                "inline": True
            }],
            "footer": {
                "text": f"公開日: {article['publishedAt'][:10]}"
            }
        }
        embeds.append(embed)

    payload = {
        "username": "AI News Bot",
        "content": f"## 📢 今日のAIニュース ({datetime.now().strftime('%Y-%m-%d')})",
        "embeds": embeds
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Discord通知完了")
    except requests.RequestException as e:
        print(f"Discord送信エラー: {e}")


def main():
    """メイン処理"""
    print("AIニュース取得開始...")
    
    # ニュース取得
    articles = get_ai_news()
    if not articles:
        print("取得できるニュースがありません")
        return

    # 各記事を要約・カテゴリ分け
    processed_articles = []
    for article in articles:
        content = article.get('content') or article.get('description', '')
        summary_data = summarize_with_gemini(content)
        
        processed_articles.append({
            "title": article['title'],
            "url": article['url'],
            "publishedAt": article['publishedAt'],
            "summary_data": summary_data
        })

    # Discord通知
    send_to_discord(processed_articles)
    print("処理完了")


if __name__ == "__main__":
    main()
