# Claude AI Integration Guide

## 概要

このプロジェクトでは、AnthropicのClaude AIを統合して、LINE Botカウンセリングアプリケーションの機能を拡張しています。Claude AIは、GPT-4と並行して使用され、より高度な自然言語処理とカウンセリング機能を提供します。

## Claude AIの特徴

### 1. 高度な自然言語理解
- 文脈の深い理解
- 複雑な感情表現の認識
- 日本語の自然な処理

### 2. 安全性と倫理
- 安全なAI設計
- 倫理的な応答生成
- 有害コンテンツの自動フィルタリング

### 3. カスタマイズ性
- プロジェクト固有の設定
- カウンセリング手法の調整
- 応答スタイルの制御

## 設定ファイル

### 基本設定 (.claude/claude.yml)

```yaml
# Claude AI Configuration
claude:
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.7
  
# Project-specific settings
project:
  name: "LINE Bot カウンセリングアプリケーション"
  description: "AI-powered counseling application using LINE Bot and GPT-4"
  language: "Japanese"
  
# Development settings
development:
  debug: true
  log_level: "INFO"
  
# AI Behavior Configuration
ai_behavior:
  system_prompt: |
    You are a supportive, Japanese-speaking counselor using the Listen-Back method.
    Follow the structured counseling approach with Listen-Back 1, Listen-Back 2, and questions.
    Maintain a warm, empathetic tone while providing professional guidance.
  
# Integration settings
integrations:
  line_bot: true
  openai: true
  stripe: true
  postgresql: true
  
# Security settings
security:
  api_key_rotation: true
  rate_limiting: true
  input_validation: true
```

## 実装例

### Claude AI クライアントの設定

```python
import anthropic
import os
import logging

class ClaudeAIClient:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("CLAUDE_API_KEY")
        )
        self.model = "claude-3-5-sonnet-20241022"
        self.logger = logging.getLogger(__name__)
    
    def generate_response(self, prompt, conversation_history=None):
        """
        Claude AIを使用してカウンセリング応答を生成
        
        Args:
            prompt (str): ユーザーからのメッセージ
            conversation_history (list): 会話履歴
            
        Returns:
            str: Claude AIからの応答
        """
        try:
            # システムプロンプトの設定
            system_prompt = self._get_system_prompt()
            
            # メッセージの構築
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Claude AI API呼び出し
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0.7,
                system=system_prompt,
                messages=messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            self.logger.error(f"Claude AI API error: {e}")
            return "申し訳ございません。一時的なエラーが発生しました。"
    
    def _get_system_prompt(self):
        """カウンセリング用システムプロンプトを取得"""
        return """
        You are a supportive, Japanese-speaking counselor using the Listen-Back method.
        
        Your role is to provide empathetic counseling following this structured approach:
        
        1. Listen-Back 1: Paraphrase the user's statement in one sentence, adding a new nuance or interpretation
        2. Wait for the user's response to your Listen-Back 1
        3. Listen-Back 2: Further paraphrase their reply, condensing it into one sentence and adding another layer of meaning
        4. After completing Listen-Back 1 and Listen-Back 2, ask structured questions in order
        5. Never ask consecutive questions - always follow the Listen-Back pattern
        
        Question order:
        1. Ask about something particularly troubling
        2. Inquire about ideal outcomes
        3. Ask about what they've already done
        4. Explore current actions
        5. Discuss potential resources
        6. Talk about immediate actions
        7. Encourage the first step and ask to close the conversation
        
        Maintain a warm, empathetic tone while providing professional guidance.
        Always respond in Japanese.
        """
```

### メインアプリケーションへの統合

```python
# main.py への追加
from claude_client import ClaudeAIClient

# Claude AI クライアントの初期化
claude_client = ClaudeAIClient()

def generate_claude_response(prompt, userId):
    """
    Claude AIを使用した応答生成
    """
    conversation_history = get_conversation_history(userId)
    return claude_client.generate_response(prompt, conversation_history)

@handler.add(MessageEvent, message=TextMessage)
def handle_line_message(event):
    userId = getattr(event.source, 'user_id', None)
    
    if event.message.text == "スタート" and userId:
        deactivate_conversation_history(userId)
        reply_text = "頼りにしてくださりありがとうございます。今日はどんなお話をうかがいましょうか？"
    else:
        current_timestamp = datetime.datetime.now()
        
        if userId:
            subscription_details = get_subscription_details_for_user(userId, STRIPE_PRICE_ID)
            subscription_status = subscription_details['status'] if subscription_details else None
            
            log_to_database(current_timestamp, 'user', userId, None, event.message.text, True)
            
            if subscription_status == "active":
                # 有料ユーザー: Claude AIまたはGPT-4を使用
                if use_claude_for_user(userId):
                    reply_text = generate_claude_response(event.message.text, userId)
                else:
                    reply_text = generate_gpt4_response(event.message.text, userId)
            else:
                # 無料ユーザー: 利用制限チェック
                response_count = get_system_responses_in_last_24_hours(userId)
                if response_count < 5:
                    reply_text = generate_claude_response(event.message.text, userId)
                else:
                    reply_text = "利用回数の上限に達しました。24時間後に再度お試しください。"
        else:
            reply_text = "エラーが発生しました。"
        
        log_to_database(current_timestamp, 'system', userId, None, reply_text, True)
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

def use_claude_for_user(userId):
    """
    ユーザーがClaude AIを使用するかどうかを決定
    """
    # ユーザー設定やランダム選択などで決定
    return True  # 例: すべてのユーザーにClaude AIを使用
```

## 環境変数の設定

```bash
# Claude AI設定
CLAUDE_API_KEY=your_claude_api_key

# その他の設定
OPENAI_API_KEY=your_openai_api_key
YOUR_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
YOUR_CHANNEL_SECRET=your_line_channel_secret
```

## 依存関係の追加

```bash
# requirements.txt に追加
anthropic>=0.7.0
```

## テスト

### Claude AI のテスト

```python
import pytest
from claude_client import ClaudeAIClient

class TestClaudeAI:
    def setup_method(self):
        self.client = ClaudeAIClient()
    
    def test_generate_response(self):
        """Claude AI応答生成のテスト"""
        prompt = "最近、仕事でストレスを感じています。"
        response = self.client.generate_response(prompt)
        
        assert response is not None
        assert len(response) > 0
        assert "申し訳ございません" not in response  # エラーレスポンスでないことを確認
    
    def test_conversation_history(self):
        """会話履歴を含む応答生成のテスト"""
        conversation_history = [
            {"role": "user", "content": "こんにちは"},
            {"role": "assistant", "content": "こんにちは。今日はどんなお話をうかがいましょうか？"}
        ]
        prompt = "仕事のことで悩んでいます。"
        
        response = self.client.generate_response(prompt, conversation_history)
        
        assert response is not None
        assert len(response) > 0
```

## 監視とログ

### ログ設定

```python
import logging

# Claude AI専用ロガー
claude_logger = logging.getLogger('claude_ai')
claude_logger.setLevel(logging.INFO)

# ファイルハンドラー
file_handler = logging.FileHandler('claude_ai.log')
file_handler.setLevel(logging.INFO)

# フォーマッター
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)

claude_logger.addHandler(file_handler)
```

### メトリクス収集

```python
import time
from datetime import datetime

class ClaudeMetrics:
    def __init__(self):
        self.response_times = []
        self.error_count = 0
        self.success_count = 0
    
    def record_response_time(self, start_time):
        """応答時間を記録"""
        response_time = time.time() - start_time
        self.response_times.append(response_time)
    
    def record_success(self):
        """成功を記録"""
        self.success_count += 1
    
    def record_error(self):
        """エラーを記録"""
        self.error_count += 1
    
    def get_average_response_time(self):
        """平均応答時間を取得"""
        if self.response_times:
            return sum(self.response_times) / len(self.response_times)
        return 0
    
    def get_success_rate(self):
        """成功率を取得"""
        total = self.success_count + self.error_count
        if total > 0:
            return self.success_count / total
        return 0
```

## トラブルシューティング

### よくある問題

1. **API キーエラー**
   - 環境変数の確認
   - API キーの有効性確認
   - レート制限の確認

2. **応答時間の遅延**
   - ネットワーク接続の確認
   - モデルサイズの調整
   - キャッシュの活用

3. **メモリ使用量の増加**
   - 会話履歴の制限
   - 不要なデータのクリーンアップ
   - 接続プールの最適化

### デバッグ方法

```python
# デバッグモードの有効化
DEBUG_MODE = True

if DEBUG_MODE:
    claude_logger.setLevel(logging.DEBUG)
    
# 詳細なログ出力
claude_logger.debug(f"Input prompt: {prompt}")
claude_logger.debug(f"Conversation history: {conversation_history}")
claude_logger.debug(f"Response: {response}")
```

## 今後の拡張予定

- **マルチモーダル対応**: 画像や音声の処理
- **感情分析**: ユーザーの感情状態の分析
- **パーソナライゼーション**: ユーザー固有の応答スタイル
- **学習機能**: 会話履歴からの継続的学習 