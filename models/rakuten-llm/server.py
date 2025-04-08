#!/usr/bin/env python3
import os
import json
import time
from typing import List, Dict, Any, Optional, Union
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn
from llama_cpp import Llama

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("rakuten-llm-server")

# Initialize FastAPI app
app = FastAPI(title="Rakuten LLM API Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models/rakuten-model.gguf")
CONTEXT_LENGTH = int(os.environ.get("CONTEXT_LENGTH", "4096"))
GPU_LAYERS = int(os.environ.get("GPU_LAYERS", "0"))  # Set to 0 for CPU only, higher for GPU

# Initialize the model
try:
    logger.info(f"Loading model from {MODEL_PATH}")
    model = Llama(
        model_path=MODEL_PATH,
        n_ctx=CONTEXT_LENGTH,
        n_gpu_layers=GPU_LAYERS,
        verbose=False
    )
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load model: {str(e)}")
    raise

# Pydantic models for API
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    max_tokens: Optional[int] = 1024
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None

class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]

# Helper function to format messages for the model
def format_messages(messages: List[Message]) -> str:
    prompt = ""
    for message in messages:
        if message.role == "system":
            prompt += f"<|system|>\n{message.content}\n"
        elif message.role == "user":
            prompt += f"<|user|>\n{message.content}\n"
        elif message.role == "assistant":
            prompt += f"<|assistant|>\n{message.content}\n"
    prompt += "<|assistant|>\n"
    return prompt

# API endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "rakuten-llm",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "rakuten",
                "permission": [],
                "root": "rakuten-llm",
                "parent": None
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completion(request: ChatCompletionRequest, raw_request: Request):
    try:
        # Format the messages into a prompt
        prompt = format_messages(request.messages)
        logger.info(f"Received prompt: {prompt[:100]}...")
        
        # Generate completion
        start_time = time.time()
        
        if request.stream:
            # Streaming response
            def generate_stream():
                completion_id = f"chatcmpl-{int(time.time())}"
                prompt_tokens = len(prompt.split())
                completion_tokens = 0
                
                # Start the stream
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
                
                # Generate tokens
                for token in model.generate(
                    prompt,
                    temp=request.temperature,
                    top_p=request.top_p,
                    max_tokens=request.max_tokens,
                    stop=request.stop or []
                ):
                    completion_tokens += 1
                    content = token
                    
                    # Send the token
                    yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': None}]})}\n\n"
                
                # End the stream
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(generate_stream(), media_type="text/event-stream")
        else:
            # Non-streaming response
            completion = model.create_completion(
                prompt=prompt,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=request.stop or []
            )
            
            # Calculate token counts
            prompt_tokens = len(prompt.split())
            completion_tokens = len(completion['choices'][0]['text'].split())
            
            # Format the response
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
                            "content": completion['choices'][0]['text']
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }
            
            logger.info(f"Generated response in {time.time() - start_time:.2f}s")
            return JSONResponse(content=response)
    
    except Exception as e:
        logger.error(f"Error generating completion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, log_level="info")