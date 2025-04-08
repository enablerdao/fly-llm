import re
import json
from typing import Dict, List, Any, Optional, Union

# モデルの特性と料金情報
MODEL_INFO = {
    "gpt-3.5-turbo": {
        "capabilities": ["general", "coding", "translation"],
        "cost_per_1k_tokens": 0.0015,
        "max_tokens": 4000,
        "complexity": "low"
    },
    "gpt-4": {
        "capabilities": ["general", "coding", "reasoning", "complex", "creative"],
        "cost_per_1k_tokens": 0.03,
        "max_tokens": 8000,
        "complexity": "high"
    },
    "claude-3-haiku": {
        "capabilities": ["general", "translation", "summarization"],
        "cost_per_1k_tokens": 0.00025,
        "max_tokens": 4000,
        "complexity": "low"
    },
    "claude-3-sonnet": {
        "capabilities": ["general", "reasoning", "creative", "analysis"],
        "cost_per_1k_tokens": 0.003,
        "max_tokens": 4000,
        "complexity": "medium"
    },
    "claude-3-opus": {
        "capabilities": ["general", "reasoning", "complex", "creative", "analysis"],
        "cost_per_1k_tokens": 0.015,
        "max_tokens": 4000,
        "complexity": "high"
    },
    "mistral-medium": {
        "capabilities": ["general", "coding", "reasoning"],
        "cost_per_1k_tokens": 0.002,
        "max_tokens": 4000,
        "complexity": "medium"
    },
    "deepseek-chat": {
        "capabilities": ["general", "coding", "translation"],
        "cost_per_1k_tokens": 0.0015,
        "max_tokens": 4000,
        "complexity": "low"
    },
    "rakuten-llm": {
        "capabilities": ["general", "japanese", "e-commerce", "product-knowledge"],
        "cost_per_1k_tokens": 0.0005,  # 自前のLLMなので低コスト
        "max_tokens": 4000,
        "complexity": "medium",
        "is_local": True
    }
}

# 言語検出パターン
LANGUAGE_PATTERNS = {
    "japanese": r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]',
    "chinese": r'[\u4E00-\u9FFF\u3400-\u4DBF\u20000-\u2A6DF\u2A700-\u2B73F\u2B740-\u2B81F\u2B820-\u2CEAF]',
    "korean": r'[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\uA960-\uA97F\uD7B0-\uD7FF]',
    "russian": r'[А-Яа-я]',
    "arabic": r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]',
    "thai": r'[\u0E00-\u0E7F]'
}

# コード検出パターン
CODE_PATTERNS = {
    "python": r'(import\s+[a-zA-Z0-9_]+|def\s+[a-zA-Z0-9_]+\s*\(|class\s+[a-zA-Z0-9_]+\s*:|\s*if\s+.*:\s*$)',
    "javascript": r'(function\s+[a-zA-Z0-9_]+\s*\(|const\s+[a-zA-Z0-9_]+\s*=|let\s+[a-zA-Z0-9_]+\s*=|var\s+[a-zA-Z0-9_]+\s*=)',
    "html": r'(<html|<body|<div|<p>|<script|<style)',
    "sql": r'(SELECT\s+.*\s+FROM|INSERT\s+INTO|UPDATE\s+.*\s+SET|DELETE\s+FROM)',
    "general_code": r'(for\s*\(|while\s*\(|\{\s*$|\}\s*$|if\s*\(.*\)\s*\{)'
}

# 複雑な推論を必要とするタスクのキーワード
COMPLEX_REASONING_KEYWORDS = [
    "analyze", "compare", "contrast", "evaluate", "explain", "synthesize", 
    "理由", "分析", "比較", "評価", "説明", "合成", "なぜ", "どのように", "どうして",
    "pros and cons", "advantages and disadvantages", "メリット", "デメリット", "長所", "短所"
]

# 創造的なタスクのキーワード
CREATIVE_KEYWORDS = [
    "create", "design", "generate", "write", "story", "poem", "creative", "imagine",
    "作成", "デザイン", "生成", "書く", "物語", "詩", "創造的", "想像"
]

# Eコマース関連のキーワード（楽天LLM向け）
ECOMMERCE_KEYWORDS = [
    "product", "shopping", "buy", "purchase", "price", "discount", "sale", "shop", "store", "retail", "order", "shipping",
    "商品", "ショッピング", "買う", "購入", "価格", "割引", "セール", "店舗", "小売", "注文", "配送", "楽天", "rakuten"
]

def detect_language(text: str) -> Optional[str]:
    """テキストの主要言語を検出する"""
    language_counts = {}
    
    for language, pattern in LANGUAGE_PATTERNS.items():
        matches = re.findall(pattern, text)
        language_counts[language] = len(matches)
    
    if not language_counts or max(language_counts.values()) == 0:
        return None
    
    return max(language_counts.items(), key=lambda x: x[1])[0]

def contains_code(text: str) -> bool:
    """テキストにコードが含まれているかを検出する"""
    for pattern_name, pattern in CODE_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            return True
    return False

def estimate_complexity(text: str) -> str:
    """テキストの複雑さを推定する"""
    # 文字数による基本的な複雑さの推定
    if len(text) > 1000:
        base_complexity = "medium"
    elif len(text) > 3000:
        base_complexity = "high"
    else:
        base_complexity = "low"
    
    # 複雑な推論キーワードの検出
    for keyword in COMPLEX_REASONING_KEYWORDS:
        if keyword.lower() in text.lower():
            return "high"
    
    # 創造的なタスクの検出
    creative_count = 0
    for keyword in CREATIVE_KEYWORDS:
        if keyword.lower() in text.lower():
            creative_count += 1
    
    if creative_count >= 2:
        return "medium" if base_complexity == "low" else "high"
    
    return base_complexity

def contains_ecommerce_keywords(text: str) -> bool:
    """テキストにEコマース関連のキーワードが含まれているかを検出する"""
    text_lower = text.lower()
    for keyword in ECOMMERCE_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    return False

def select_best_model(messages: List[Dict[str, str]], user_preferences: Optional[Dict[str, Any]] = None) -> str:
    """メッセージの内容に基づいて最適なモデルを選択する"""
    # メッセージからユーザーの入力を抽出
    user_inputs = " ".join([msg["content"] for msg in messages if msg["role"] == "user"])
    
    # 言語の検出
    language = detect_language(user_inputs)
    
    # コードの検出
    has_code = contains_code(user_inputs)
    
    # Eコマース関連キーワードの検出
    has_ecommerce = contains_ecommerce_keywords(user_inputs)
    
    # 複雑さの推定
    complexity = estimate_complexity(user_inputs)
    
    # ローカルモデルを優先するかどうか
    prefer_local = user_preferences and user_preferences.get("prefer_local", False)
    
    # Eコマース関連の質問で日本語の場合は楽天LLMを優先
    if has_ecommerce and (language == "japanese" or prefer_local):
        return "rakuten-llm"
    
    # 日本語の場合はClaude-3-Haikuが優先（Eコマース以外）
    if language == "japanese":
        if complexity == "high":
            return "claude-3-sonnet"
        else:
            return "claude-3-haiku"
    
    # コードを含む場合
    if has_code:
        if complexity == "high":
            return "gpt-4"
        else:
            return "gpt-3.5-turbo"
    
    # 複雑さに基づく選択
    if complexity == "high":
        return "gpt-4" if user_preferences and user_preferences.get("prefer_quality", False) else "claude-3-sonnet"
    elif complexity == "medium":
        # Eコマース関連の質問の場合は楽天LLMを使用
        if has_ecommerce:
            return "rakuten-llm"
        return "mistral-medium"
    else:
        return "claude-3-haiku"  # 最も安価なモデル

def route_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """リクエストを受け取り、必要に応じてモデルを自動選択して更新したリクエストを返す"""
    # リクエストのコピーを作成
    updated_request = request_data.copy()
    
    # モデルが "auto" の場合、自動選択を行う
    if updated_request.get("model") == "auto":
        messages = updated_request.get("messages", [])
        user_preferences = updated_request.get("user_preferences", {})
        
        # 最適なモデルを選択
        best_model = select_best_model(messages, user_preferences)
        
        # リクエストのモデルを更新
        updated_request["model"] = best_model
        
        # ユーザープリファレンスを削除（APIに送信しない）
        if "user_preferences" in updated_request:
            del updated_request["user_preferences"]
    
    return updated_request