from flask import Flask, request, abort, jsonify
import os
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
import logging
import time
import psutil
from functools import lru_cache
from contextlib import contextmanager
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import stripe
import psycopg2
import datetime
from psycopg2.pool import SimpleConnectionPool
from openai import OpenAI

app = Flask(__name__)

# 環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

# OpenAIクライアントの初期化
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_PRICE_ID = os.environ["SUBSCRIPTION_PRICE_ID"]

# データベース接続プール
db_pool = None

def init_db_pool():
    """データベース接続プールを初期化"""
    global db_pool
    if db_pool is None:
        db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.environ['DB_HOST'],
            port=5432,
            dbname=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASS']
        )

@contextmanager
def get_db_connection():
    """データベース接続のコンテキストマネージャー"""
    if db_pool is None:
        init_db_pool()
    
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

@app.route("/")
def hello_world():
    return "hello world!"

@app.route("/health")
def health_check():
    """ヘルスチェックエンドポイント"""
    try:
        # メモリ使用量をチェック
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        # データベース接続をチェック
        db_status = "healthy"
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        return jsonify({
            "status": "healthy",
            "memory_usage_percent": memory_usage,
            "database": db_status,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

sys_prompt = "You are a supportive Japanese counselor using the Listen-Back method. Follow this pattern: 1) Listen-Back 1: Paraphrase user's statement with new nuance, 2) Wait for response, 3) Listen-Back 2: Further paraphrase with additional meaning, 4) Ask structured questions in order. Never ask consecutive questions. Question order: 1) What troubles you most? 2) Ideal outcome? 3) What have you done? 4) Current actions? 5) Available resources? 6) Immediate steps? 7) First step with encouragement. Always respond in Japanese with empathy."

def generate_gpt4_response(prompt, userId):
    """OpenAI APIを使用してGPT-4応答を生成（最新ライブラリ使用）"""
    try:
        # 過去の会話履歴を取得（最新5件に制限）
        conversation_history = get_conversation_history(userId)
        
        # メッセージリストを構築
        messages = [
            {"role": "system", "content": sys_prompt}
        ]
        
        # 会話履歴を追加
        for msg in conversation_history:
            messages.append(msg)
        
        # ユーザーの最新メッセージを追加
        messages.append({"role": "user", "content": prompt})

        # OpenAI APIを呼び出し（タイムアウト設定付き）
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # より軽量で高速なモデル
            messages=messages,
            temperature=1.0,
            max_tokens=300,  # さらに短縮
            timeout=20.0  # タイムアウトを短縮
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "申し訳ございません。一時的なエラーが発生しました。"

@lru_cache(maxsize=1000)
def get_system_responses_in_last_24_hours(userId):
    """24時間以内のシステム応答数を取得（キャッシュ付き）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            query = """
            SELECT COUNT(*) FROM line_bot_logs 
            WHERE sender='system' AND lineId=%s AND timestamp > NOW() - INTERVAL '24 HOURS';
            """
            cursor.execute(query, (userId,))
            result = cursor.fetchone()
            return result[0]
        except Exception as e:
            logger.error(f"Database error: {e}")
            return 0
        finally:
            cursor.close()

def deactivate_conversation_history(userId):
    """会話履歴を非アクティブ化"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            query = """
            UPDATE line_bot_logs SET is_active=FALSE 
            WHERE lineId=%s;
            """
            cursor.execute(query, (userId,))
            conn.commit()
        except Exception as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
        finally:
            cursor.close()

# LINEからのメッセージを処理
@handler.add(MessageEvent, message=TextMessage)
def handle_line_message(event):
    start_time = time.time()
    userId = getattr(event.source, 'user_id', None)

    try:
        if event.message.text == "スタート" and userId:
            deactivate_conversation_history(userId)
            reply_text = "頼りにしてくださりありがとうございます。今日はどんなお話をうかがいましょうか？"
        else:
            current_timestamp = datetime.datetime.now()

            if userId:
                # Stripe情報を取得
                subscription_details = get_subscription_details_for_user(userId, STRIPE_PRICE_ID)
                stripe_id = subscription_details['stripeId'] if subscription_details else None
                subscription_status = subscription_details['status'] if subscription_details else None

                # ユーザーメッセージをログに保存
                log_to_database(current_timestamp, 'user', userId, stripe_id, event.message.text, True, sys_prompt)

                if subscription_status == "active":
                    reply_text = generate_gpt4_response(event.message.text, userId)
                else:
                    response_count = get_system_responses_in_last_24_hours(userId)
                    if response_count < 5: 
                        reply_text = generate_gpt4_response(event.message.text, userId)
                    else:
                        reply_text = "利用回数の上限に達しました。24時間後に再度お試しください。こちらから回数無制限の有料プランに申し込むこともできます：https://line-login-3fbeac7c6978.herokuapp.com/"
            else:
                reply_text = "エラーが発生しました。"

            # システム応答をログに保存
            log_to_database(current_timestamp, 'system', userId, stripe_id, reply_text, True, sys_prompt)

        # 処理時間をログに記録
        processing_time = time.time() - start_time
        logger.info(f"Message processing time: {processing_time:.2f}s for user {userId}")

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        
    except Exception as e:
        logger.error(f"Error in handle_line_message: {e}")
        # エラー時のフォールバック応答
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="申し訳ございません。一時的なエラーが発生しました。"))
        except:
            pass

def get_subscription_details_for_user(userId, STRIPE_PRICE_ID):
    """Stripeサブスクリプション情報を取得（最適化版）"""
    try:
        # より効率的なクエリ（limitを削減）
        subscriptions = stripe.Subscription.list(
            limit=50,  # 100から50に削減
            status='active',
            expand=['data.items.data.price']
        )
        
        for subscription in subscriptions.data:
            if (subscription["items"]["data"][0]["price"]["id"] == STRIPE_PRICE_ID and 
                subscription["metadata"].get("line_user") == userId):
                return {
                    'status': subscription["status"],
                    'stripeId': subscription["customer"]
                }
        return None
    except Exception as e:
        logger.error(f"Stripe API error: {e}")
        return None

def log_to_database(timestamp, sender, userId, stripeId, message, is_active=True, sys_prompt=''):
    """データベースにログを保存"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            query = """
            INSERT INTO line_bot_logs (timestamp, sender, lineId, stripeId, message, is_active, sys_prompt) 
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            cursor.execute(query, (timestamp, sender, userId, stripeId, message, is_active, sys_prompt))
            conn.commit()
        except Exception as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
        finally:
            cursor.close()

def get_conversation_history(userId):
    """会話履歴を取得（最新5件に制限）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        conversations = []

        try:
            query = """
            SELECT sender, message FROM line_bot_logs 
            WHERE lineId=%s AND is_active=TRUE 
            ORDER BY timestamp DESC LIMIT 5;
            """
            cursor.execute(query, (userId,))
            
            results = cursor.fetchall()
            for result in results:
                role = 'user' if result[0] == 'user' else 'assistant'
                conversations.append({"role": role, "content": result[1]})
        except Exception as e:
            logger.error(f"Database error: {e}")
        finally:
            cursor.close()

        return conversations[::-1]

if __name__ == "__main__":
    # データベース接続プールを初期化
    init_db_pool()
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
