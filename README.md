# LiteLLM Proxy with Rakuten LLM

This project sets up a LiteLLM proxy server on Fly.io to provide LLM services to users with API key authentication, enhanced with privacy protection, cost optimization features, and integration with a self-hosted Rakuten LLM.

## Features

- OpenAI-compatible API endpoints
- API key management (create, list, delete)
- Model routing to different LLM providers
- Usage tracking and cost monitoring
- CORS support for web applications
- **Automatic model selection** based on prompt content
- **Rakuten LLM integration** for e-commerce related queries

### Privacy Protection Features

- **PII Detection and Masking**: Automatically detects and masks personal identifiable information (PII) such as:
  - Email addresses
  - Phone numbers
  - Credit card numbers
  - Physical addresses
  - Names in various formats

- **API Key Protection**: Prevents API keys from being sent to LLM providers

- **Request Sanitization**: Removes sensitive parameters from requests before processing

### Cost Optimization Features

- **Budget Management**:
  - Set global budget limits
  - Set per-user budget limits
  - Track usage in real-time

- **Caching**:
  - Redis-based response caching
  - Configurable TTL (Time-To-Live)
  - Reduces duplicate requests to LLM providers

- **Model Fallbacks**:
  - Automatically falls back to cheaper models when appropriate
  - Context window optimization
  - Token usage optimization

- **Rate Limiting**:
  - Prevents excessive usage
  - Configurable limits per user/API key

## Deployment

### Prerequisites

- Fly.io account
- Fly CLI installed
- OpenAI API key (or other LLM provider keys)

### Steps to Deploy

1. Log in to Fly.io:
   ```
   fly auth login
   ```

2. Create a Fly.io app:
   ```
   fly apps create litellm-proxy
   ```

3. Create a volume for persistent data:
   ```
   fly volumes create litellm_data --size 1 --region nrt
   ```

4. Set your API keys as secrets:
   ```
   fly secrets set OPENAI_API_KEY=your_openai_api_key
   fly secrets set ANTHROPIC_API_KEY=your_anthropic_api_key
   ```

5. Deploy the application:
   ```
   fly deploy
   ```

6. Access your proxy at:
   ```
   https://litellm-proxy.fly.dev
   ```

## API Usage

### Authentication

All API requests require an API key in the `Authorization` header:

```
Authorization: Bearer your_api_key
```

### API Key Management

- Create a new API key:
  ```
  POST /api/keys
  ```
  Parameters:
  ```json
  {
    "name": "user-name",
    "expires_at": "2025-12-31T23:59:59Z",
    "models": ["gpt-3.5-turbo", "gpt-4"],
    "max_budget": 50.0
  }
  ```

- List all API keys:
  ```
  GET /api/keys
  ```

- Delete an API key:
  ```
  DELETE /api/keys/{key_id}
  ```

- Get usage statistics:
  ```
  GET /api/usage?key_id=sk-your-key-id
  ```

### LLM API Endpoints

The proxy provides OpenAI-compatible endpoints:

- Chat completions:
  ```
  POST /v1/chat/completions
  ```

- Completions:
  ```
  POST /v1/completions
  ```

- Embeddings:
  ```
  POST /v1/embeddings
  ```

### Automatic Model Selection

Use the automatic model selection feature by specifying `"auto"` as the model:

```bash
curl -X POST https://your-litellm-proxy/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "楽天で買える良いスマートフォンを教えてください"}]
  }'
```

This example will detect e-commerce related keywords ("楽天", "買える") and Japanese language, and automatically select the Rakuten LLM.

You can also provide preferences to guide the selection:

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

### Using Rakuten LLM Directly

To use the Rakuten LLM directly, specify it as the model:

```bash
curl -X POST https://your-litellm-proxy/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "rakuten-llm",
    "messages": [{"role": "user", "content": "楽天市場でおすすめの商品を教えてください"}]
  }'
```

## Configuration

Edit the `config.yaml` file to:
- Add more models
- Configure rate limits
- Set up model fallbacks
- Configure caching
- Set budget limits

## Environment Variables

- `ENABLE_CACHING`: Enable/disable caching (default: true)
- `CACHE_TTL`: Cache time-to-live in seconds (default: 3600)
- `MAX_TOKENS_PER_REQUEST`: Maximum tokens per request (default: 4000)
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `RAKUTEN_LLM_API_BASE`: URL of your Rakuten LLM server

## Running with Docker Compose

You can run the entire stack (LiteLLM Proxy, Rakuten LLM, and Redis) using Docker Compose:

```bash
docker-compose up -d
```

This will:
1. Build and start the LiteLLM Proxy
2. Build and start the Rakuten LLM server
3. Start a Redis server for caching

## About Rakuten LLM

The Rakuten LLM is based on [rinna/japanese-gpt-neox-3.6b-instruction-ppo](https://huggingface.co/rinna/japanese-gpt-neox-3.6b-instruction-ppo), a Japanese language model fine-tuned for instruction following. It has been further optimized for e-commerce related queries and product recommendations.

Features:
- Optimized for Japanese language
- Specialized knowledge about products and shopping
- Integrated with the automatic model selection system

## License

MIT