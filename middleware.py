from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import json
from model_router import route_request
import logging

logger = logging.getLogger("litellm-proxy")

class ModelRouterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # /v1/chat/completionsエンドポイントのみを処理
        if request.url.path == "/v1/chat/completions" and request.method == "POST":
            # リクエストボディを読み取り
            body = await request.body()
            request_data = json.loads(body)
            
            # モデルが "auto" の場合、自動選択を行う
            if request_data.get("model") == "auto":
                # リクエストをルーティング
                routed_request = route_request(request_data)
                selected_model = routed_request["model"]
                logger.info(f"Auto-selected model: {selected_model} for request")
                
                # リクエストを更新
                body = json.dumps(routed_request).encode()
                
                # 新しいリクエストを作成
                request._body = body
        
        # 次のミドルウェアまたはエンドポイントにリクエストを渡す
        response = await call_next(request)
        return response