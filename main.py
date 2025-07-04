from flask import Flask, request, abort
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
import requests
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__) # stripeの情報の確認
import stripe
import psycopg2
from psycopg2 import pool
import datetime
import re

app = Flask(__name__)

# 環境変数取得
YOUR_CHANNEL_ACCESS_TOKEN = os.environ["YOUR_CHANNEL_ACCESS_TOKEN"]
YOUR_CHANNEL_SECRET = os.environ["YOUR_CHANNEL_SECRET"]
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GPT4_API_URL = 'https://api.openai.com/v1/chat/completions'

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_PRICE_ID = os.environ["SUBSCRIPTION_PRICE_ID"]

# オーナー（管理者）のLINE ID（環境変数から取得、設定されていない場合はNone）
OWNER_LINE_ID = os.environ.get("OWNER_LINE_ID")

# データベース接続プール
connection_pool = None

def init_connection_pool():
    global connection_pool
    try:
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=database_url
            )
        else:
            dsn = f"host={os.environ['DB_HOST']} " \
                  f"port=5432 " \
                  f"dbname={os.environ['DB_NAME']} " \
                  f"user={os.environ['DB_USER']} " \
                  f"password={os.environ['DB_PASS']}"
            connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dsn=dsn
            )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise

def get_connection():
    global connection_pool
    if connection_pool is None:
        init_connection_pool()
    try:
        return connection_pool.getconn()
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise

def put_connection(connection):
    global connection_pool
    if connection_pool and connection:
        connection_pool.putconn(connection)

@app.route("/")
def hello_world():
    return "hello world!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    # app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 入力検証関数
def validate_message(message):
    if not message or not isinstance(message, str):
        raise ValueError("Invalid message format")
    
    # メッセージ長制限
    if len(message) > 2000:
        raise ValueError("Message too long")
    
    # 空文字やスペースのみのチェック
    if not message.strip():
        raise ValueError("Empty message")
    
    # 危険な文字列パターンのチェック
    dangerous_patterns = [
        r'<script.*?>.*?</script>',  # XSS
        r'javascript:',  # JavaScript injection
        r'vbscript:',   # VBScript injection
        r'data:text/html',  # Data URI XSS
    ]
    
    message_lower = message.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, message_lower, re.IGNORECASE | re.DOTALL):
            raise ValueError("Potentially dangerous content detected")
    
    return message.strip()

sys_prompt = "You will be playing the role of a supportive, Japanese-speaking counselor. Here is the conversation history so far:\n\n<conversation_history>\n{{CONVERSATION_HISTORY}}\n</conversation_history>\n\nThe user has just said:\n<user_statement>\n{{QUESTION}}\n</user_statement>\n\nPlease carefully review the conversation history and the user's latest statement. Your goal is to provide supportive counseling while following this specific method:\n\n1. Listen-Back 1: After the user makes a statement, paraphrase it into a single sentence while adding a new nuance or interpretation. \n2. Wait for the user's reply to your Listen-Back 1.\n3. Listen-Back 2: After receiving the user's response, further paraphrase their reply, condensing it into one sentence and adding another layer of meaning or interpretation.\n4. Once you've done Listen-Back 1 and Listen-Back 2 and received a response from the user, you may then pose a question from the list below, in the specified order. Do not ask a question out of order.\n5. After the user answers your question, return to Listen-Back 1 - paraphrase their answer in one sentence and introduce a new nuance or interpretation. \n6. You can ask your next question only after receiving a response to your Listen-Back 1, providing your Listen-Back 2, and getting another response from the user.\n\nIn essence, never ask consecutive questions. Always follow the pattern of Listen-Back 1, user response, Listen-Back 2, another user response before moving on to the next question.\n\nHere is the order in which you should ask questions:\n1. Start by asking the user about something they find particularly troubling.\n2. Then, inquire about how they'd envision the ideal outcome. \n3. Proceed by asking about what little they've already done.\n4. Follow up by exploring other actions they're currently undertaking.\n5. Delve into potential resources that could aid in achieving their goals.\n6. Discuss the immediate actions they can take to move closer to their aspirations.\n7. Lastly, encourage them to complete the very first step in that direction with some positive feedback, and ask if you can close the conversation.\n\n<example>\nUser: I'm so busy I don't even have time to sleep.\nYou: You are having trouble getting enough sleep.\nUser: Yes.\nYou: You are so busy that you want to manage to get some sleep.\nUser: Yes.\nYou: In what way do you have problems when you get less sleep?\n</example>\n\n<example>  \nUser: I get sick when I get less sleep.\nYou: You are worried about getting sick.\nUser: Yes.\nYou: You feel that sleep time is important to stay healthy.\nUser: That is right.\nYou: What do you hope to become?\n</example>\n\n<example>\nUser: I want to be free from suffering. But I cannot relinquish responsibility.\nYou: You want to be free from suffering, but at the same time you can't give up your responsibility.\nUser: Exactly.\nYou: You are searching for your own way forward.\nUser: Maybe so.\nYou: When do you think you are getting closer to the path you should be on, even if only a little?  \n</example>\n\nPlease follow the above procedures strictly for the consultation."

def generate_gpt4_response(prompt, userId):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }
    # 過去の会話履歴を取得
    conversation_history = get_conversation_history(userId)
    # sys_promptを会話の最初に追加
    conversation_history.insert(0, {"role": "system", "content": sys_prompt})
    # ユーザーからの最新のメッセージを追加
    conversation_history.append({"role": "user", "content": prompt})

    data = {
        'model': "gpt-4o",
        'messages': conversation_history,
        'temperature': 1
    }
    # ここでconversation_historyの内容をログに出力
    # app.logger.info("Conversation history sent to : " + str(conversation_history))
    # 旧："gpt-4-1106-preview"

    try:
        response = requests.post(GPT4_API_URL, headers=headers, json=data)
        response.raise_for_status()  # Check if the request was successful
        response_json = response.json() # This line has been moved here
        # Add this line to log the response from  API
        # app.logger.info("Response from  API: " + str(response_json))
        return response_json['choices'][0]['message']['content'].strip()
    except requests.RequestException as e:
        # app.logger.error(f" API request failed: {e}")
        return "Sorry, I couldn't understand that."

        
def get_system_responses_in_last_24_hours(userId):
    # この関数の中でデータベースにアクセスして、指定されたユーザーに対する過去24時間以内のシステムの応答数を取得します。
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            query = """
            SELECT COUNT(*) FROM line_bot_logs 
            WHERE sender='system' AND lineId=%s AND timestamp > NOW() - INTERVAL '24 HOURS';
            """
            cursor.execute(query, (userId,))
            result = cursor.fetchone()
            return result[0]
        except Exception as e:
            logger.error(f"Database error in get_system_responses_in_last_24_hours: {e}")
            return 0
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Connection error in get_system_responses_in_last_24_hours: {e}")
        return 0
    finally:
        if connection:
            put_connection(connection)

def deactivate_conversation_history(userId):
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            query = """
            UPDATE line_bot_logs SET is_active=FALSE 
            WHERE lineId=%s;
            """
            cursor.execute(query, (userId,))
            connection.commit()
        except Exception as e:
            logger.error(f"Database error in deactivate_conversation_history: {e}")
            connection.rollback()
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Connection error in deactivate_conversation_history: {e}")
        # データベース接続エラーでもアプリケーションを継続
        pass
    finally:
        if connection:
            put_connection(connection)

# LINEからのメッセージを処理し、必要に応じてStripeの情報も確認します。
@handler.add(MessageEvent, message=TextMessage)
def handle_line_message(event):
    userId = getattr(event.source, 'user_id', None)

    try:
        # 入力検証
        validated_message = validate_message(event.message.text)
        
        if validated_message == "スタート" and userId:
            deactivate_conversation_history(userId)
            reply_text = "頼りにしてくださりありがとうございます。今日はどんなお話をうかがいましょうか？"
        else:
            # 現在のタイムスタンプを取得
            current_timestamp = datetime.datetime.now()

            if userId:
                subscription_details = get_subscription_details_for_user(userId, STRIPE_PRICE_ID)
                stripe_id = subscription_details['stripeId'] if subscription_details else None
                subscription_status = subscription_details['status'] if subscription_details else None

                log_to_database(current_timestamp, 'user', userId, stripe_id, validated_message, True, sys_prompt)  # is_activeをTrueで保存

                # オーナーIDの場合は無制限で利用可能
                if userId == OWNER_LINE_ID:
                    reply_text = generate_gpt4_response(validated_message, userId)
                elif subscription_status == "active": ####################本番はactive################
                    reply_text = generate_gpt4_response(validated_message, userId)
                else:
                    # オーナーIDでない場合のみ24時間制限をチェック
                    response_count = get_system_responses_in_last_24_hours(userId)
                    if response_count < 5: 
                        reply_text = generate_gpt4_response(validated_message, userId)
                    else:
                        reply_text = "利用回数の上限に達しました。24時間後に再度お試しください。こちらから回数無制限の有料プランに申し込むこともできます：https://line-login-3fbeac7c6978.herokuapp.com/"
            else:
                reply_text = "エラーが発生しました。"

            # メッセージをログに保存
            log_to_database(current_timestamp, 'system', userId, stripe_id, reply_text, True, sys_prompt)  # is_activeをTrueで保存

    except ValueError as e:
        # 入力検証エラーの場合
        logger.warning(f"Invalid input from user {userId}: {e}")
        reply_text = "申し訳ございませんが、メッセージの形式に問題があります。もう一度お試しください。"
    except Exception as e:
        # その他のエラー
        logger.error(f"Unexpected error in handle_line_message: {e}")
        reply_text = "申し訳ございません。一時的なエラーが発生しました。しばらくしてから再度お試しください。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

# stripeの情報を参照
def get_subscription_details_for_user(userId, STRIPE_PRICE_ID):
    subscriptions = stripe.Subscription.list(limit=100)
    for subscription in subscriptions.data:
        if subscription["items"]["data"][0]["price"]["id"] == STRIPE_PRICE_ID and subscription["metadata"].get("line_user") == userId:
            return {
                'status': subscription["status"],
                'stripeId': subscription["customer"]
            }
    return None

# Stripeの情報を確認する関数
def check_subscription_status(userId):
    return get_subscription_details_for_user(userId, STRIPE_PRICE_ID)

# データをdbに入れる関数
def log_to_database(timestamp, sender, userId, stripeId, message, is_active=True, sys_prompt=''):
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            query = """
            INSERT INTO line_bot_logs (timestamp, sender, lineId, stripeId, message, is_active, sys_prompt) 
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            cursor.execute(query, (timestamp, sender, userId, stripeId, message, is_active, sys_prompt))
            connection.commit()
        except Exception as e:
            logger.error(f"Database error in log_to_database: {e}")
            connection.rollback()
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Connection error in log_to_database: {e}")
        # データベース接続エラーでもアプリケーションを継続
        pass
    finally:
        if connection:
            put_connection(connection)

# 会話履歴を参照する関数
def get_conversation_history(userId):
    conversations = []
    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            query = """
            SELECT sender, message FROM line_bot_logs 
            WHERE lineId=%s AND is_active=TRUE 
            ORDER BY timestamp DESC LIMIT 10;
            """
            cursor.execute(query, (userId,))
            
            results = cursor.fetchall()
            for result in results:
                role = 'user' if result[0] == 'user' else 'assistant'
                conversations.append({"role": role, "content": result[1]})
        except Exception as e:
            logger.error(f"Database error in get_conversation_history: {e}")
        finally:
            cursor.close()
    except Exception as e:
        logger.error(f"Connection error in get_conversation_history: {e}")
    finally:
        if connection:
            put_connection(connection)

    # 最新の会話が最後に来るように反転
    return conversations[::-1]

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
