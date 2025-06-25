# AI Agents Configuration

## 概要

このプロジェクトでは、複数のAIエージェントを統合してLINE Botカウンセリングアプリケーションを構築しています。各エージェントは特定の役割を持ち、協調してサービスを提供します。

## エージェント構成

### 1. メインカウンセリングエージェント (GPT-4)

**役割**: プライマリカウンセラー
- **モデル**: GPT-4 (gpt-4o)
- **機能**: Listen-Back手法による構造化カウンセリング
- **設定**: 
  - Temperature: 1.0
  - Max Tokens: 4096
  - System Prompt: 日本語カウンセリング用

**使用方法**:
```python
def generate_gpt4_response(prompt, userId):
    # GPT-4を使用したカウンセリング応答生成
    conversation_history = get_conversation_history(userId)
    # システムプロンプトと会話履歴を組み合わせて応答生成
```

### 2. セキュリティエージェント

**役割**: セキュリティ監視と保護
- **機能**: 
  - 入力検証
  - レート制限
  - 異常検知
  - データ保護

**実装例**:
```python
def security_check(user_input, user_id):
    # 入力の安全性チェック
    # レート制限の確認
    # 異常なパターンの検知
```

### 3. データ管理エージェント

**役割**: データベース操作と会話履歴管理
- **機能**:
  - 会話履歴の保存
  - データベース接続管理
  - データ整合性チェック

**実装例**:
```python
def log_to_database(timestamp, sender, userId, stripeId, message, is_active=True, sys_prompt=''):
    # データベースへの安全なログ保存
```

### 4. 決済管理エージェント (Stripe)

**役割**: サブスクリプションと決済管理
- **機能**:
  - サブスクリプション状態確認
  - 利用制限の管理
  - 決済処理

**実装例**:
```python
def get_subscription_details_for_user(userId, STRIPE_PRICE_ID):
    # Stripe APIを使用したサブスクリプション情報取得
```

## エージェント間通信

### メッセージングパターン

1. **同期通信**: 即座の応答が必要な場合
2. **非同期通信**: バックグラウンド処理が必要な場合
3. **イベント駆動**: 特定のイベントに基づく処理

### データフロー

```
LINE Bot → セキュリティエージェント → メインカウンセリングエージェント
                ↓
        データ管理エージェント ← 決済管理エージェント
```

## エージェント設定

### 環境変数

```bash
# AI エージェント設定
OPENAI_API_KEY=your_openai_api_key
CLAUDE_API_KEY=your_claude_api_key

# セキュリティ設定
SECURITY_LEVEL=high
RATE_LIMIT_PER_HOUR=100

# データベース設定
DB_HOST=your_db_host
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASS=your_db_password

# 決済設定
STRIPE_SECRET_KEY=your_stripe_secret_key
SUBSCRIPTION_PRICE_ID=your_price_id
```

### エージェント設定ファイル

```yaml
# .claude/claude.yml
claude:
  model: claude-3-5-sonnet-20241022
  max_tokens: 4096
  temperature: 0.7

ai_behavior:
  system_prompt: |
    You are a supportive, Japanese-speaking counselor using the Listen-Back method.
    Follow the structured counseling approach with Listen-Back 1, Listen-Back 2, and questions.
    Maintain a warm, empathetic tone while providing professional guidance.
```

## エージェント監視

### メトリクス

- **応答時間**: 各エージェントの処理時間
- **成功率**: エージェントの処理成功率
- **エラー率**: エラー発生率
- **リソース使用量**: CPU、メモリ使用量

### ログ設定

```python
import logging

# エージェント別ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agents.log'),
        logging.StreamHandler()
    ]
)

# エージェント別ロガー
counseling_logger = logging.getLogger('counseling_agent')
security_logger = logging.getLogger('security_agent')
data_logger = logging.getLogger('data_agent')
payment_logger = logging.getLogger('payment_agent')
```

## エージェント拡張

### 新しいエージェントの追加

1. **エージェントクラスの定義**
```python
class NewAgent:
    def __init__(self, config):
        self.config = config
        
    def process(self, input_data):
        # エージェントの処理ロジック
        pass
```

2. **設定ファイルの更新**
3. **メインアプリケーションへの統合**
4. **テストの追加**

### エージェントの組み合わせ

```python
def process_user_message(message, user_id):
    # セキュリティチェック
    if not security_agent.validate(message):
        return "セキュリティエラー"
    
    # カウンセリング応答生成
    response = counseling_agent.generate_response(message, user_id)
    
    # データ保存
    data_agent.save_conversation(user_id, message, response)
    
    return response
```

## トラブルシューティング

### よくある問題

1. **エージェント間通信エラー**
   - ネットワーク接続の確認
   - API キーの有効性確認
   - レート制限の確認

2. **メモリ使用量の増加**
   - エージェントのリソース監視
   - 不要なデータのクリーンアップ
   - 接続プールの最適化

3. **応答時間の遅延**
   - エージェントの並列処理
   - キャッシュの活用
   - データベースクエリの最適化

### デバッグ方法

```python
# デバッグモードの有効化
DEBUG_MODE = True

if DEBUG_MODE:
    logging.getLogger().setLevel(logging.DEBUG)
    
# エージェントの状態確認
def check_agent_status():
    agents = {
        'counseling': counseling_agent.status(),
        'security': security_agent.status(),
        'data': data_agent.status(),
        'payment': payment_agent.status()
    }
    return agents
```

## 今後の拡張予定

- **感情分析エージェント**: ユーザーの感情状態を分析
- **多言語対応エージェント**: 英語、中国語などの対応
- **学習エージェント**: 会話履歴からの学習機能
- **予測エージェント**: ユーザーの行動予測 