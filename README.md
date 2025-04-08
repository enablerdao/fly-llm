# Fly-LLM: 統合AIプロキシサービス

Fly-LLMは、複数のLLMプロバイダーへのアクセスを単一のAPIで提供する統合AIプロキシサービスです。自動モデル選択、コスト最適化、プライバシー保護機能を備えています。

## 主な機能

- **統合API**: OpenAI互換APIを通じて複数のLLMプロバイダーにアクセス
- **自動モデル選択**: 言語、複雑さ、タスクタイプに基づいて最適なモデルを自動選択
- **コスト最適化**: インテリジェントなキャッシング、予算管理、モデルフォールバック
- **プライバシー保護**: 個人情報の自動検出とマスキング
- **Stripe決済統合**: クレジットカード決済によるAPIクレジットのチャージ
- **楽天LLM統合**: 日本語Eコマースクエリに特化したモデル
- **APIキー管理**: 作成、リスト表示、削除、使用量制限の設定

## アーキテクチャ

システムは以下のコンポーネントで構成されています：

1. **LiteLLM Proxy**: メインのAPIプロキシサーバー
   - OpenAI互換API
   - モデルルーティング
   - APIキー管理
   - 使用量追跡

2. **Rakuten LLM Server**: 日本語特化モデル用サーバー
   - llama.cpp + GGUF形式モデル
   - 低リソース要件
   - 高速推論

3. **Stripe決済システム**: 支払い処理
   - クレジットカード決済
   - 使用量に応じた課金
   - クレジット管理

## デプロイ構成

サービスはFly.ioにデプロイされています：

- **メインプロキシ**: https://fly-llm-api.fly.dev/
  - 標準VMで動作
  - Redis for caching
  - API管理

- **Rakuten LLMサーバー**: https://rakuten-llm-server.fly.dev/
  - 専用VM (2 CPU, 8GB RAM)
  - 永続ボリューム (10GB)
  - llama.cpp推論エンジン

## 使用方法

### APIキーの取得

1. 管理パネル (https://fly-llm-api.fly.dev/admin) にアクセス
2. 新しいAPIキーを作成
3. クレジットをチャージ (Stripe決済)

### APIリクエスト

```bash
curl -X POST https://fly-llm-api.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "What is the capital of Japan?"}]
  }'
```

### 自動モデル選択

`"model": "auto"`を指定すると、システムが最適なモデルを自動選択します。

### 特定モデルの指定

```bash
curl -X POST https://fly-llm-api.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Explain quantum computing"}]
  }'
```

## 料金プラン

- **スターター**: $10 / ¥1,000 (最低チャージ額)
- **プロ**: $50 / ¥5,000 (5%ボーナスクレジット)
- **エンタープライズ**: $200 / ¥20,000 (10%ボーナスクレジット)

## 開発者向け情報

### ローカル開発環境のセットアップ

```bash
# リポジトリのクローン
git clone https://github.com/enablerdao/fly-llm.git
cd fly-llm

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.sample .env
# .envファイルを編集してAPIキーを設定

# サーバーの起動
python main.py
```

### Fly.ioへのデプロイ

```bash
# Fly.ioのセットアップ
fly auth login

# アプリのデプロイ
fly deploy

# シークレットの設定
fly secrets set OPENAI_API_KEY=sk-xxx ANTHROPIC_API_KEY=sk-ant-xxx
```

### APIエンドポイント

#### 認証

すべてのAPIリクエストには`Authorization`ヘッダーにAPIキーが必要です：

```
Authorization: Bearer your_api_key
```

#### APIキー管理

- 新しいAPIキーの作成:
  ```
  POST /api/keys
  ```
  パラメータ:
  ```json
  {
    "name": "ユーザー名",
    "expires_at": "2025-12-31T23:59:59Z",
    "models": ["gpt-3.5-turbo", "gpt-4"],
    "max_budget": 50.0
  }
  ```

- APIキー一覧の取得:
  ```
  GET /api/keys
  ```

- APIキーの削除:
  ```
  DELETE /api/keys/{key_id}
  ```

- 使用統計の取得:
  ```
  GET /api/usage?key_id=sk-your-key-id
  ```

#### 自動モデル選択の詳細設定

自動モデル選択機能を使用する際に、ユーザー設定を指定できます：

```json
{
  "model": "auto",
  "messages": [...],
  "user_preferences": {
    "prefer_quality": true,
    "prefer_local": true,
    "max_cost": 0.05
  }
}
```

#### 楽天LLMの直接使用

楽天LLMを直接使用するには、モデルとして指定します：

```bash
curl -X POST https://fly-llm-api.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "rakuten-llm",
    "messages": [{"role": "user", "content": "楽天市場でおすすめの商品を教えてください"}]
  }'
```

## 設定

`config.yaml`ファイルを編集して以下の設定が可能です：
- モデルの追加
- レート制限の設定
- モデルフォールバックの設定
- キャッシュの設定
- 予算制限の設定

## 環境変数

- `ENABLE_CACHING`: キャッシュの有効/無効 (デフォルト: true)
- `CACHE_TTL`: キャッシュの有効期間（秒） (デフォルト: 3600)
- `MAX_TOKENS_PER_REQUEST`: リクエストあたりの最大トークン数 (デフォルト: 4000)
- `OPENAI_API_KEY`: OpenAI APIキー
- `ANTHROPIC_API_KEY`: Anthropic APIキー
- `RAKUTEN_LLM_API_BASE`: 楽天LLMサーバーのURL

## Dockerでの実行

Docker Composeを使用して全スタック（LiteLLM Proxy、Rakuten LLM、Redis）を実行できます：

```bash
docker-compose up -d
```

これにより以下が実行されます：
1. LiteLLM Proxyのビルドと起動
2. Rakuten LLMサーバーのビルドと起動
3. キャッシュ用Redisサーバーの起動

## 楽天LLMについて

楽天LLMは[RakutenAI-2.0-mini-instruct](https://huggingface.co/staccat0/RakutenAI-2.0-mini-instruct-Q8_0-GGUF)をベースにしており、GGUF形式に量子化されています。llama.cppを使用して低リソースでの推論が可能です。

特徴：
- 日本語に最適化
- 商品や買い物に関する専門知識
- 自動モデル選択システムとの統合
- 低リソース要件（CPU推論可能）

## 技術スタック

- **バックエンド**: FastAPI, Python, LiteLLM
- **データベース**: Redis, ファイルベースJSON
- **決済**: Stripe
- **推論エンジン**: llama.cpp
- **デプロイ**: Fly.io

## ライセンス

MIT