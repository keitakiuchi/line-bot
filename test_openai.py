#!/usr/bin/env python3
"""
OpenAI API テストスクリプト
main.pyと同じ方法でOpenAI APIが使用できるかテストする
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_openai_api():
    """OpenAI APIの動作テスト"""
    
    # .envファイルから環境変数を読み込み
    load_dotenv()
    
    # APIキーを取得
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY が .env ファイルに設定されていません")
        return False
    
    print(f"✅ APIキーが設定されています: {api_key[:10]}...")
    
    try:
        # main.pyと同じ方法でOpenAIクライアントを初期化
        openai_client = OpenAI(api_key=api_key)
        print("✅ OpenAIクライアントの初期化に成功しました")
        
        # 簡単なテストメッセージ
        test_messages = [
            {"role": "system", "content": "あなたは親切なアシスタントです。"},
            {"role": "user", "content": "こんにちは！簡単な挨拶をしてください。"}
        ]
        
        print("🔄 OpenAI APIにリクエストを送信中...")
        
        # main.pyと同じ設定でAPIを呼び出し
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=test_messages,
            temperature=1.0,
            max_tokens=150,
            timeout=5.0
        )
        
        # レスポンスを取得
        reply = response.choices[0].message.content.strip()
        print(f"✅ API呼び出しに成功しました！")
        print(f"📝 レスポンス: {reply}")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI API エラー: {e}")
        return False

def test_streaming():
    """ストリーミング機能のテスト"""
    
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OPENAI_API_KEY が設定されていません")
        return False
    
    try:
        openai_client = OpenAI(api_key=api_key, timeout=20.0)
        print("🔄 ストリーミングテストを開始...")
        
        test_messages = [
            {"role": "system", "content": "あなたは親切なアシスタントです。"},
            {"role": "user", "content": "短い詩を作ってください。"}
        ]
        
        # ストリーミングでAPIを呼び出し
        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=test_messages,
            temperature=0.2,
            stream=True
        )
        
        print("📝 ストリーミングレスポンス:")
        chunks = []
        for part in stream:
            content = part.choices[0].delta.content or ""
            if content:
                print(content, end="", flush=True)
                chunks.append(content)
        
        print("\n✅ ストリーミングテストに成功しました！")
        return True
        
    except Exception as e:
        print(f"❌ ストリーミングテスト エラー: {e}")
        return False

if __name__ == "__main__":
    print("🚀 OpenAI API テストを開始します...")
    print("=" * 50)
    
    # 通常のAPIテスト
    print("1️⃣ 通常のAPI呼び出しテスト")
    success1 = test_openai_api()
    
    print("\n" + "=" * 50)
    
    # ストリーミングテスト
    print("2️⃣ ストリーミングAPI呼び出しテスト")
    success2 = test_streaming()
    
    print("\n" + "=" * 50)
    
    # 結果サマリー
    if success1 and success2:
        print("🎉 すべてのテストが成功しました！")
        print("✅ main.pyと同じ方法でOpenAI APIが使用できます")
    else:
        print("⚠️  一部のテストが失敗しました")
        if not success1:
            print("❌ 通常のAPI呼び出しに問題があります")
        if not success2:
            print("❌ ストリーミングAPI呼び出しに問題があります") 