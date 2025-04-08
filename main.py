
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from litellm.proxy.proxy_server import router as litellm_router
from model_router import route_request
from middleware import ModelRouterMiddleware
import os
import uuid
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import litellm
from litellm.proxy.proxy_server import ProxyConfig
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("litellm-proxy")

# Initialize FastAPI app
app = FastAPI(title="LiteLLM API Proxy")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Include LiteLLM router
app.include_router(litellm_router, tags=["LiteLLM"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add model router middleware
app.add_middleware(ModelRouterMiddleware)

# API key header for authentication
api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# Path to store API keys
API_KEYS_FILE = os.environ.get("API_KEYS_FILE", "/app/api_keys.json")

# Cost optimization settings
MAX_TOKENS_PER_REQUEST = int(os.environ.get("MAX_TOKENS_PER_REQUEST", 4000))
CACHE_TTL = int(os.environ.get("CACHE_TTL", 3600))  # Cache TTL in seconds
ENABLE_CACHING = os.environ.get("ENABLE_CACHING", "true").lower() == "true"

# PII filtering patterns
PII_PATTERNS = {
    "email": r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}',
    "phone_jp": r'0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{4}',
    "credit_card": r'(?:\d{4}[-\s]?){3}\d{4}',
    "address_jp": r'〒?\d{3}[-\s]?\d{4}',
}

# Models for API key management
class APIKeyCreate(BaseModel):
    name: str
    expires_at: Optional[datetime] = None
    models: Optional[List[str]] = None
    metadata: Optional[Dict] = None
    max_budget: Optional[float] = None

class APIKeyResponse(BaseModel):
    key: str
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    models: Optional[List[str]] = None
    metadata: Optional[Dict] = None
    max_budget: Optional[float] = None
    current_usage: Optional[float] = 0.0

# Initialize API keys storage
def init_api_keys():
    if not os.path.exists(os.path.dirname(API_KEYS_FILE)):
        os.makedirs(os.path.dirname(API_KEYS_FILE), exist_ok=True)
    
    if not os.path.exists(API_KEYS_FILE):
        with open(API_KEYS_FILE, "w") as f:
            json.dump({"keys": {}, "usage": []}, f)

# Load API keys from file
def load_api_keys():
    try:
        with open(API_KEYS_FILE, "r") as f:
            data = json.load(f)
            return data.get("keys", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Load usage logs from file
def load_usage_logs():
    try:
        with open(API_KEYS_FILE, "r") as f:
            data = json.load(f)
            return data.get("usage", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Save all data to file
def save_data(api_keys, usage_logs):
    with open(API_KEYS_FILE, "w") as f:
        json.dump({
            "keys": api_keys,
            "usage": usage_logs
        }, f)

# Mask PII information
def mask_pii(text):
    masked_text = text
    for pattern_name, pattern in PII_PATTERNS.items():
        masked_text = re.sub(pattern, f"[{pattern_name}]", masked_text)
    return masked_text

# Calculate cost
def calculate_cost(model, input_tokens, output_tokens):
    cost_map = {
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "gpt-4": {"input": 0.03, "output": 0.06},
    }
    
    if model in cost_map:
        return (input_tokens / 1000 * cost_map[model]["input"]) + (output_tokens / 1000 * cost_map[model]["output"])
    else:
        return (input_tokens / 1000 * 0.002) + (output_tokens / 1000 * 0.002)

# Log usage
def log_usage(key_id, model, input_tokens, output_tokens, request_id):
    api_keys = load_api_keys()
    usage_logs = load_usage_logs()
    
    cost = calculate_cost(model, input_tokens, output_tokens)
    
    usage_logs.append({
        "key_id": key_id,
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "request_id": request_id
    })
    
    # Update API key usage
    if key_id in api_keys:
        if "usage" not in api_keys[key_id]:
            api_keys[key_id]["usage"] = 0.0
        
        api_keys[key_id]["usage"] = api_keys[key_id].get("usage", 0.0) + cost
    
    save_data(api_keys, usage_logs)
    logger.info(f"Usage logged: key={key_id}, model={model}, cost={cost}")

# Verify API key
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is missing",
        )
    
    # Remove 'Bearer ' prefix if present
    if api_key.startswith("Bearer "):
        api_key = api_key[7:]
    
    api_keys = load_api_keys()
    
    if api_key not in api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    
    # Check if key is expired
    key_data = api_keys[api_key]
    if key_data.get("expires_at") and datetime.fromisoformat(key_data["expires_at"]) < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )
    
    # Check if budget is exceeded
    if key_data.get("max_budget") and key_data.get("usage", 0.0) >= key_data.get("max_budget"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Budget limit reached",
        )
    
    return api_key

# API key management endpoints
@app.post("/api/keys", response_model=APIKeyResponse)
async def create_api_key(key_data: APIKeyCreate, _: str = Depends(verify_api_key)):
    """Create a new API key"""
    api_keys = load_api_keys()
    usage_logs = load_usage_logs()
    
    # Generate a new API key
    new_key = f"sk-{uuid.uuid4().hex}"
    
    # Store the key data
    api_keys[new_key] = {
        "name": key_data.name,
        "created_at": datetime.now().isoformat(),
        "expires_at": key_data.expires_at.isoformat() if key_data.expires_at else None,
        "models": key_data.models,
        "metadata": key_data.metadata or {},
        "max_budget": key_data.max_budget,
        "usage": 0.0
    }
    
    save_data(api_keys, usage_logs)
    
    return {
        "key": new_key,
        "name": key_data.name,
        "created_at": datetime.now(),
        "expires_at": key_data.expires_at,
        "models": key_data.models,
        "metadata": key_data.metadata or {},
        "max_budget": key_data.max_budget,
        "current_usage": 0.0
    }

@app.get("/api/keys", response_model=List[APIKeyResponse])
async def list_api_keys(_: str = Depends(verify_api_key)):
    """List all API keys"""
    api_keys = load_api_keys()
    
    return [
        {
            "key": key,
            "name": data["name"],
            "created_at": datetime.fromisoformat(data["created_at"]),
            "expires_at": datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            "models": data.get("models"),
            "metadata": data.get("metadata", {}),
            "max_budget": data.get("max_budget"),
            "current_usage": data.get("usage", 0.0)
        }
        for key, data in api_keys.items()
    ]

@app.delete("/api/keys/{key_id}")
async def delete_api_key(key_id: str, _: str = Depends(verify_api_key)):
    """Delete an API key"""
    api_keys = load_api_keys()
    usage_logs = load_usage_logs()
    
    if key_id not in api_keys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    
    del api_keys[key_id]
    save_data(api_keys, usage_logs)
    
    return {"message": "API key deleted successfully"}

@app.get("/api/usage")
async def get_usage(key_id: Optional[str] = None, _: str = Depends(verify_api_key)):
    """Get usage statistics"""
    usage_logs = load_usage_logs()
    
    if key_id:
        # Return usage for specific key only
        filtered_logs = [log for log in usage_logs if log["key_id"] == key_id]
        
        total_cost = sum(log["cost"] for log in filtered_logs)
        model_usage = {}
        
        for log in filtered_logs:
            model = log["model"]
            if model not in model_usage:
                model_usage[model] = {"cost": 0.0, "requests": 0}
            
            model_usage[model]["cost"] += log["cost"]
            model_usage[model]["requests"] += 1
        
        return {
            "key_id": key_id,
            "total_cost": total_cost,
            "model_usage": model_usage,
            "request_count": len(filtered_logs)
        }
    else:
        # Return all usage
        total_cost = sum(log["cost"] for log in usage_logs)
        key_usage = {}
        model_usage = {}
        
        for log in usage_logs:
            key = log["key_id"]
            model = log["model"]
            
            if key not in key_usage:
                key_usage[key] = {"cost": 0.0, "requests": 0}
            
            if model not in model_usage:
                model_usage[model] = {"cost": 0.0, "requests": 0}
            
            key_usage[key]["cost"] += log["cost"]
            key_usage[key]["requests"] += 1
            
            model_usage[model]["cost"] += log["cost"]
            model_usage[model]["requests"] += 1
        
        return {
            "total_cost": total_cost,
            "key_usage": key_usage,
            "model_usage": model_usage,
            "request_count": len(usage_logs)
        }

# Home page
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    host = request.headers.get("host", "litellm-proxy.fly.dev")
    return templates.TemplateResponse("index.html", {"request": request, "host": host})

# Admin page
@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    """Admin page"""
    host = request.headers.get("host", "litellm-proxy.fly.dev")
    return templates.TemplateResponse("admin.html", {"request": request, "host": host})

# Auto model selection endpoint
@app.post("/v1/chat/completions/auto")
async def auto_chat_completions(request: Request):
    """
    自動モデル選択を行うエンドポイント
    リクエストを受け取り、内容に基づいて最適なモデルを選択し、適切なLLMにルーティングする
    """
    # リクエストボディを取得
    request_data = await request.json()
    
    # 認証ヘッダーを取得
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header is required")
    
    # リクエストをルーティング（モデルを自動選択）
    request_data["model"] = "auto"  # 自動選択モードを設定
    routed_request = route_request(request_data)
    
    # 選択されたモデルをログに記録
    selected_model = routed_request["model"]
    logger.info(f"Auto-selected model: {selected_model} for request")
    
    # 標準のLiteLLMエンドポイントにリダイレクト
    # 新しいリクエストを作成
    new_request = Request(
        scope=request.scope,
        receive=request.receive,
        send=request.send
    )
    
    # ヘッダーとボディを設定
    headers = dict(request.headers)
    headers["content-type"] = "application/json"
    
    # LiteLLMルーターにリクエストを転送
    response = await litellm_router.chat_completions(new_request, body=routed_request)
    
    # レスポンスにモデル選択情報を追加
    response_data = response.body
    if isinstance(response_data, bytes):
        response_data = json.loads(response_data.decode("utf-8"))
    
    # モデル選択情報を追加
    if isinstance(response_data, dict):
        response_data["auto_selected_model"] = selected_model
    
    return JSONResponse(
        content=response_data,
        status_code=response.status_code,
        headers=dict(response.headers)
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

# LiteLLM callback function
def litellm_success_callback(kwargs, response_obj, start_time, end_time):
    try:
        # Get API key
        api_key = kwargs.get("litellm_params", {}).get("metadata", {}).get("api_key")
        
        if not api_key:
            logger.warning("API key not found")
            return
        
        # Get model name
        model = kwargs.get("model", "unknown")
        
        # Get token counts
        input_tokens = response_obj.get("usage", {}).get("prompt_tokens", 0)
        output_tokens = response_obj.get("usage", {}).get("completion_tokens", 0)
        
        # Get request ID
        request_id = response_obj.get("id", str(uuid.uuid4()))
        
        # Log usage
        log_usage(api_key, model, input_tokens, output_tokens, request_id)
        
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")

# Initialize the proxy
@app.on_event("startup")
async def startup():
    # Initialize API keys storage
    init_api_keys()
    
    # Create a default admin API key if none exists
    api_keys = load_api_keys()
    if not api_keys:
        admin_key = f"sk-{uuid.uuid4().hex}"
        api_keys[admin_key] = {
            "name": "admin",
            "created_at": datetime.now().isoformat(),
            "expires_at": None,
            "models": None,
            "metadata": {"role": "admin"},
            "max_budget": None,
            "usage": 0.0
        }
        usage_logs = []
        save_data(api_keys, usage_logs)
        logger.info(f"Created default admin API key: {admin_key}")
    
    # LiteLLM settings
    litellm.success_callback = [litellm_success_callback]
    
    # PII detection settings - add custom function to process prompts
    litellm.add_function_to_prompt = mask_pii
    
    # Enable caching
    if ENABLE_CACHING:
        litellm.cache = litellm.Cache()
        logger.info("Caching enabled")
    
    # Enable cost tracking
    litellm.success_callback = ["litellm.callbacks.track_cost_callback"]
    
    # Initialize proxy config
    proxy_config = ProxyConfig()
    # Load config from file
    litellm.config_path = "config.yaml"
    litellm.set_verbose = True
    
    logger.info("LiteLLM Proxy started")

# Run the proxy server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 12000)), reload=True)
