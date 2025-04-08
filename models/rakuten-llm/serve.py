#!/usr/bin/env python3
import os
import argparse
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
import time
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# モデル設定
MODEL_NAME = os.environ.get("MODEL_NAME", "rinna/japanese-gpt-neox-3.6b-instruction-ppo")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MAX_LENGTH = int(os.environ.get("MAX_LENGTH", "4096"))
TEMPERATURE = float(os.environ.get("TEMPERATURE", "0.7"))
TOP_P = float(os.environ.get("TOP_P", "0.9"))

# FastAPIアプリケーションの初期化
app = FastAPI(title="Rakuten LLM API")

# CORSミドルウェアの追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# モデルとトークナイザーの読み込み
print(f"Loading model {MODEL_NAME} on {DEVICE}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
    device_map="auto" if DEVICE == "cuda" else None,
    load_in_8bit=DEVICE == "cuda",
)

# 日本語指示チューニングモデル用のプロンプトテンプレート
def create_prompt(messages):
    prompt = ""
    for message in messages:
        role = message["role"]
        content = message["content"]
        
        if role == "system":
            prompt += f"システム: {content}\n"
        elif role == "user":
            prompt += f"ユーザー: {content}\n"
        elif role == "assistant":
            prompt += f"アシスタント: {content}\n"
    
    # 最後のアシスタントの応答を促すプロンプト
    prompt += "アシスタント: "
    return prompt

# OpenAI互換のリクエストモデル
class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = TEMPERATURE
    top_p: Optional[float] = TOP_P
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = False
    user: Optional[str] = None

# OpenAI互換のレスポンスモデル
class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]

# チャット完了エンドポイント
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    try:
        # プロンプトの作成
        prompt = create_prompt(request.messages)
        
        # 入力トークン数の計算
        input_ids = tokenizer.encode(prompt, return_tensors="pt").to(DEVICE)
        input_tokens = input_ids.shape[1]
        
        # 生成パラメータの設定
        gen_params = {
            "input_ids": input_ids,
            "max_length": input_tokens + request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "do_sample": request.temperature > 0,
            "pad_token_id": tokenizer.eos_token_id
        }
        
        # テキスト生成
        start_time = time.time()
        output = model.generate(**gen_params)
        
        # 生成されたテキストのデコード
        generated_text = tokenizer.decode(output[0], skip_special_tokens=True)
        
        # プロンプト部分を削除して応答のみを取得
        response_text = generated_text[len(prompt):]
        
        # 出力トークン数の計算
        output_tokens = len(tokenizer.encode(response_text))
        
        # レスポンスの作成
        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens
            }
        }
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# モデル情報エンドポイント
@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "rakuten-llm",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "rakuten"
            }
        ]
    }

# ヘルスチェックエンドポイント
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    uvicorn.run(app, host=args.host, port=args.port)