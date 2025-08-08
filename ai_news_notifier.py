import os
import requests
import json
from datetime import datetime, timedelta
from groq import Groq

# --- 環境変数からAPIキーとURLを取得 ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 必要な環境変数が設定されているかチェック
if not all([NEWS_API_KEY, GROQ_API_KEY, DISCORD_WEBHOOK_URL]):
    raise ValueError("必要な環境変数が設定されていません: NEWS_API_KEY, GROQ_API_KEY, DISCORD_WEBHOOK_URL")

def get_ai_news():
    """News APIからAI関連の最新ニュースを5件取得する"""
    print("AI関連ニュースを取得中...")
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    from_date = yesterday.strftime('%Y-%m-%d')

    # News APIのエンドポイントとパラメータ
    url = (f"https://newsapi.org/v2/everything?"
           f"q=AI&"
           f"from={from_date}&"
           f"sortBy=popularity&"
           f"language=en&"
           f"pageSize=5&"
           f"apiKey={NEWS_API_KEY}")

    try:
        response = requests.get(url)
        response.raise_for_status()  # HTTPエラーがあれば例外を発生させる
        news_data = response.json()
        articles = news_data.get("articles", [])
        if not articles:
            print("ニュースが見つかりませんでした。")
            return []
        print(f"{len(articles)}件のニュースを取得しました。")
        return articles
    except requests.exceptions.RequestException as e:
        print(f"News APIからのニュース取得に失敗しました: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"News APIのレスポンス解析に失敗しました: {e}")
        return []


def summarize_and_categorize_with_groq(article_content: str):
    """Groq APIを使用して記事を要約し、カテゴリ分けする"""
    if not article_content:
        return {"summary": "記事の内容が空のため、要約できませんでした。", "category": "不明"}

    print("Groqで要約とカテゴリ分けを実行中...")
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたは優秀なAIニュースのアナリストです。"
                        "提供されたニュース記事の本文を日本語で3文で簡潔に要約し、"
                        "内容に最も適したカテゴリを['技術開発', 'ビジネス応用', '倫理・規制', '研究', 'その他']の中から一つ選んでください。"
                        "出力は必ず以下のJSON形式で返してください。\n"
                        "例: {\"summary\": \"要約文...\", \"category\": \"カテゴリ名\"}"
                    )
                },
                {
                    "role": "user",
                    "content": f"以下の記事を要約・カテゴリ分けしてください:\n\n{article_content}"
                }
            ],
            model="llama3-70b-8192",
            temperature=0.5,
            max_tokens=1024,
            top_p=1,
            stream=False,
            response_format={"type": "json_object"},
        )
        response_content = chat_completion.choices[0].message.content
        return json.loads(response_content)
    except Exception as e:
        print(f"Groq APIの処理中にエラーが発生しました: {e}")
        return {"summary": "要約中にエラーが発生しました。", "category": "エラー"}

def send_to_discord(articles_with_summaries):
    """整形したニュースをDiscordに送信する"""
    print("Discordへ通知を送信中...")

    # DiscordのEmbedsを使った見やすいフォーマットを作成
    embeds = []
    for article in articles_with_summaries:
        embed = {
            "title": f"📰 {article['title']}",
            "url": article['url'],
            "description": article['summary_data']['summary'],
            "color": 0x5865F2, # Discordのブランドカラー
            "fields": [
                {
                    "name": "カテゴリ",
                    "value": f"`{article['summary_data']['category']}`",
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Published at: {datetime.strptime(article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d %H:%M')}"
            }
        }
        embeds.append(embed)

    # Webhookに送信するペイロード
    payload = {
        "username": "AI News Notifier",
        "avatar_url": "https://i.imgur.com/4M34hi2.png",
        "content": f"## 📢 今日のAIニューストレンド ({datetime.now().strftime('%Y-%m-%d')})",
        "embeds": embeds
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Discordへの通知が正常に完了しました。")
    except requests.exceptions.RequestException as e:
        print(f"Discordへの通知送信に失敗しました: {e}")

def main():
    """メイン処理"""
    print("AI News Notifierを開始します...")
    articles = get_ai_news()
    if not articles:
        print("取得できるニュースがないため、処理を終了します。")
        return

    articles_with_summaries = []
    for article in articles:
        # 記事の本文または説明文を要約対象とする
        content_to_summarize = article.get('content') or article.get('description', '')
        summary_data = summarize_and_categorize_with_groq(content_to_summarize)

        # 元の記事情報と要約結果を結合
        article_info = {
            "title": article['title'],
            "url": article['url'],
            "publishedAt": article['publishedAt'],
            "summary_data": summary_data
        }
        articles_with_summaries.append(article_info)

    if articles_with_summaries:
        send_to_discord(articles_with_summaries)
        print("AI News Notifierの処理が正常に完了しました。")

if __name__ == "__main__":
    main()
