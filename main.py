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
from concurrent.futures import ThreadPoolExecutor
import threading
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

# OpenAIクライアントの初期化（タイムアウト設定付き）
openai_client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"], 
    timeout=20.0
)

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_PRICE_ID = os.environ["SUBSCRIPTION_PRICE_ID"]

# データベース接続プール
db_pool = None

# 非同期処理用のスレッドプール
executor = ThreadPoolExecutor(max_workers=4)

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
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return 'ERROR', 500
    return 'OK'

sys_prompt = "You will be playing the role of a supportive, Japanese-speaking counselor. Here is the conversation history so far:\n\n<conversation_history>\n{{CONVERSATION_HISTORY}}\n</conversation_history>\n\nThe user has just said:\n<user_statement>\n{{QUESTION}}\n</user_statement>\n\nPlease carefully review the conversation history and the user's latest statement. Your goal is to provide supportive counseling while following this specific method:\n\n1. Listen-Back 1: After the user makes a statement, paraphrase it into a single sentence while adding a new nuance or interpretation. \n2. Wait for the user's reply to your Listen-Back 1.\n3. Listen-Back 2: After receiving the user's response, further paraphrase their reply, condensing it into one sentence and adding another layer of meaning or interpretation.\n4. Once you've done Listen-Back 1 and Listen-Back 2 and received a response from the user, you may then pose a question from the list below, in the specified order. Do not ask a question out of order.\n5. After the user answers your question, return to Listen-Back 1 - paraphrase their answer in one sentence and introduce a new nuance or interpretation. \n6. You can ask your next question only after receiving a response to your Listen-Back 1, providing your Listen-Back 2, and getting another response from the user.\n\nIn essence, never ask consecutive questions. Always follow the pattern of Listen-Back 1, user response, Listen-Back 2, another user response before moving on to the next question.\n\nHere is the order in which you should ask questions:\n1. Start by asking the user about something they find particularly troubling.\n2. Then, inquire about how they'd envision the ideal outcome. \n3. Proceed by asking about what little they've already done.\n4. Follow up by exploring other actions they're currently undertaking.\n5. Delve into potential resources that could aid in achieving their goals.\n6. Discuss the immediate actions they can take to move closer to their aspirations.\n7. Lastly, encourage them to complete the very first step in that direction with some positive feedback, and ask if you can close the conversation.\n\n<example>\nUser: I'm so busy I don't even have time to sleep.\nYou: You are having trouble getting enough sleep.\nUser: Yes.\nYou: You are so busy that you want to manage to get some sleep.\nUser: Yes.\nYou: In what way do you have problems when you get less sleep?\n</example>\n\n<example>  \nUser: I get sick when I get less sleep.\nYou: You are worried about getting sick.\nUser: Yes.\nYou: You feel that sleep time is important to stay healthy.\nUser: That is right.\nYou: What do you hope to become?\n</example>\n\n<example>\nUser: I want to be free from suffering. But I cannot relinquish responsibility.\nYou: You want to be free from suffering, but at the same time you can't give up your responsibility.\nUser: Exactly.\nYou: You are searching for your own way forward.\nUser: Maybe so.\nYou: When do you think you are getting closer to the path you should be on, even if only a little?  \n</example>\n\nPlease follow the above procedures strictly for the consultation."

def generate_gpt4_response(prompt, userId):
    """OpenAI APIを使用してGPT-4応答を生成（ストリーミング対応）"""
    try:
        # 過去の会話履歴を取得（最新3件に制限）
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

        # OpenAI APIを呼び出し（ストリーミング対応）
        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=1.0,
            max_tokens=150,
            stream=True  # ストリーミングで高速化
        )
        
        # ストリーミングレスポンスを結合
        chunks = []
        for part in stream:
            if part.choices[0].delta.content:
                chunks.append(part.choices[0].delta.content)
        
        return "".join(chunks).strip()
        
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

def process_and_push_message(event):
    """バックグラウンドでメッセージを処理してプッシュ送信"""
    start_time = time.time()
    userId = getattr(event.source, 'user_id', None)

    try:
        if event.message.text == "スタート" and userId:
            reply_text = "頼りにしてくださりありがとうございます。今日はどんなお話をうかがいましょうか？"
            # 非同期でログ処理
            try:
                deactivate_conversation_history(userId)
            except:
                pass
        else:
            current_timestamp = datetime.datetime.now()
            stripe_id = None
            subscription_status = None

            if userId:
                # Stripe情報を取得（タイムアウト付き）
                try:
                    subscription_details = get_subscription_details_for_user(userId, STRIPE_PRICE_ID)
                    if subscription_details:
                        stripe_id = subscription_details['stripeId']
                        subscription_status = subscription_details['status']
                except:
                    pass

                # 非同期でユーザーメッセージをログに保存
                try:
                    log_to_database(current_timestamp, 'user', userId, stripe_id, event.message.text, True, "")
                except:
                    pass

                if subscription_status == "active":
                    reply_text = generate_gpt4_response(event.message.text, userId)
                else:
                    try:
                        response_count = get_system_responses_in_last_24_hours(userId)
                        if response_count < 5: 
                            reply_text = generate_gpt4_response(event.message.text, userId)
                        else:
                            reply_text = "利用回数の上限に達しました。24時間後に再度お試しください。"
                    except:
                        reply_text = generate_gpt4_response(event.message.text, userId)
            else:
                reply_text = "エラーが発生しました。"

            # 非同期でシステム応答をログに保存
            try:
                log_to_database(current_timestamp, 'system', userId, stripe_id, reply_text, True, "")
            except:
                pass

        # 処理時間をログに記録
        processing_time = time.time() - start_time
        if processing_time > 5:
            logger.warning(f"Slow processing: {processing_time:.2f}s for user {userId}")

        # プッシュメッセージで最終回答を送信
        line_bot_api.push_message(userId, TextSendMessage(text=reply_text))
        
    except Exception as e:
        logger.error(f"Error in process_and_push_message: {e}")
        # エラー時のフォールバック応答
        try:
            line_bot_api.push_message(userId, TextSendMessage(text="申し訳ございません。一時的なエラーが発生しました。"))
        except:
            pass

# LINEからのメッセージを処理（非同期化）
@handler.add(MessageEvent, message=TextMessage)
def handle_line_message(event):
    userId = getattr(event.source, 'user_id', None)

    try:
        # 1) すぐに仮返信（即座に200 OKを返すため）
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="回答を生成中です…"))
        
        # 2) 裏で重い処理を実行（非同期）
        executor.submit(process_and_push_message, event)
        
    except Exception as e:
        logger.error(f"Error in handle_line_message: {e}")
        # エラー時のフォールバック応答
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="申し訳ございません。一時的なエラーが発生しました。"))
        except:
            pass

@lru_cache(maxsize=100)
def get_subscription_details_for_user(userId, STRIPE_PRICE_ID):
    """Stripeサブスクリプション情報を取得（キャッシュ付き）"""
    try:
        # より効率的なクエリ（limitをさらに削減）
        subscriptions = stripe.Subscription.list(
            limit=10,  # 20から10に削減
            status='active'
        )
        
        for subscription in subscriptions.data:
            if subscription.get("metadata", {}).get("line_user") == userId:
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
    """会話履歴を取得（最新3件に制限）"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        conversations = []

        try:
            query = """
            SELECT sender, message FROM line_bot_logs 
            WHERE lineId=%s AND is_active=TRUE 
            ORDER BY timestamp DESC LIMIT 3;
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
