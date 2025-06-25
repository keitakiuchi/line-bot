# LINE Bot カウンセリングアプリケーション

## 概要

このプロジェクトは、LINE Botを使用したAIカウンセリングアプリケーションです。OpenAIのGPT-4を活用して、ユーザーとの対話を通じたカウンセリングサービスを提供します。

## 機能

- **AIカウンセリング**: GPT-4を使用した対話型カウンセリング
- **会話履歴管理**: PostgreSQLを使用した会話履歴の保存と管理
- **サブスクリプション管理**: Stripeを使用した有料プランの管理
- **利用制限**: 無料ユーザーは24時間で5回まで利用可能
- **Listen-Back手法**: 構造化されたカウンセリング手法の実装

## 技術スタック

- **Backend**: Python 3.11.9, Flask
- **AI**: OpenAI GPT-4
- **Database**: PostgreSQL
- **Payment**: Stripe
- **Messaging**: LINE Bot SDK
- **Deployment**: Heroku

## セットアップ

### 前提条件

- Python 3.11.9
- PostgreSQL データベース
- LINE Bot チャンネル
- OpenAI API キー
- Stripe アカウント

### 環境変数

以下の環境変数を設定してください：

```bash
# LINE Bot設定
YOUR_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
YOUR_CHANNEL_SECRET=your_line_channel_secret

# OpenAI設定
OPENAI_API_KEY=your_openai_api_key

# Stripe設定
STRIPE_SECRET_KEY=your_stripe_secret_key
SUBSCRIPTION_PRICE_ID=your_stripe_price_id

# データベース設定
DB_HOST=your_db_host
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASS=your_db_password
```

### インストール

1. リポジトリをクローン
```bash
git clone <repository-url>
cd line-bot
```

2. 依存関係をインストール
```bash
pip install -r requirements.txt
```

3. データベーステーブルを作成
```sql
CREATE TABLE line_bot_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP,
    sender VARCHAR(10),
    lineId VARCHAR(50),
    stripeId VARCHAR(50),
    message TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sys_prompt TEXT
);
```

4. アプリケーションを起動
```bash
python main.py
```

## デプロイ

### Heroku

1. Heroku CLIをインストール
2. Herokuアプリを作成
```bash
heroku create your-app-name
```

3. 環境変数を設定
```bash
heroku config:set YOUR_CHANNEL_ACCESS_TOKEN=your_token
heroku config:set YOUR_CHANNEL_SECRET=your_secret
# 他の環境変数も同様に設定
```

4. PostgreSQLアドオンを追加
```bash
heroku addons:create heroku-postgresql:mini
```

5. デプロイ
```bash
git push heroku main
```

## 使用方法

1. LINE Botを友達追加
2. 「スタート」と送信してカウンセリングを開始
3. 無料プラン：24時間で5回まで利用可能
4. 有料プラン：回数無制限

## カウンセリング手法

このアプリケーションは「Listen-Back」手法を採用しています：

1. **Listen-Back 1**: ユーザーの発言を1文で言い換え、新しい解釈を加える
2. **Listen-Back 2**: ユーザーの返答をさらに言い換え、意味の層を追加
3. **質問**: 構造化された質問を順序通りに実施

## API エンドポイント

- `GET /`: ヘルスチェック
- `POST /callback`: LINE Bot Webhook

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

プルリクエストやイシューの報告を歓迎します。

## サポート

問題が発生した場合は、GitHubのイシューページで報告してください。
