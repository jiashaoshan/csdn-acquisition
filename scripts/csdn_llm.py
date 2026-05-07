#!/usr/bin/env python3
"""
CSDN 获客技能 - LLM API 封装
基于 x-acquisition 的 x_llm.py 改造
"""
import os, sys, json, re, requests
from typing import Optional, List, Dict, Any

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"

def _resolve_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    cfg = os.path.expanduser("~/.openclaw/openclaw.json")
    if os.path.exists(cfg):
        import json
        with open(cfg) as f:
            env = json.load(f).get("env", {})
            if isinstance(env, dict):
                key = env.get("DEEPSEEK_API_KEY", "")
                if key:
                    return key
    raise ValueError("DEEPSEEK_API_KEY not set")


def call_llm(prompt: str, system_prompt: Optional[str] = None,
             temperature: float = 0.7, max_tokens: int = 4000) -> str:
    api_key = _resolve_api_key()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": DEEPSEEK_MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    try:
        resp = requests.post(DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        raise

def call_llm_json(*args, **kwargs) -> dict:
    content = call_llm(*args, **kwargs)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r'\[.*\]|\{.*\}', content, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"LLM return non-JSON: {content[:200]}")

def generate_keywords(product_url: str, product_name: str = "") -> List[str]:
    """根据产品信息生成 CSDN 搜索关键词"""
    sys_prompt = """你是关键词研究专家。根据产品信息生成适合CSDN（中国开发者社区）搜索的关键词。
要求：5-10个中文关键词，覆盖产品类型、技术栈、应用场景、行业痛点。输出JSON数组。"""
    prompt = f"""产品链接：{product_url}
产品名称：{product_name or "未指定"}

生成5-10个CSDN搜索关键词，中文。输出JSON数组格式。"""
    try:
        resp = call_llm(prompt, sys_prompt, temperature=0.3)
        data = json.loads(resp)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "keywords" in data:
            return data["keywords"]
    except:
        pass
    # fallback
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config/keywords.json")) as f:
        return json.load(f).get("seed_keywords", ["AI", "工具", "效率"])

def generate_comments_batch(articles: List[Dict], product_url: str,
                            product_name: str = "") -> List[Dict]:
    """
    批量生成评论（一次LLM调用，节省token）
    
    Args:
        articles: [{"title": "标题", "url": "链接", "content": "内容片段"}]
        product_url: 产品链接
        product_name: 产品名称
    Returns:
        [{"article_url": "链接", "comment": "评论内容"}]
    """
    # 传干净URL给LLM（不带追踪参数）
    def clean_url(u):
        return u.split("?")[0].split("#")[0].rstrip("/")
    articles_text = "\n\n".join([
        f"--- 文章{i+1} ---\n标题：{a.get('title','')}\n链接：{clean_url(a.get('url',''))}\n摘要：{a.get('content','')[:300]}"
        for i, a in enumerate(articles)
    ])

    sys_prompt = """你是CSDN技术社区的真实开发者用户。
要求：
1. 每条评论 50-500 字
2. 与对应文章内容相关，像真实开发者
3. 产品链接必须放在正文中间自然融入（不要单独一行，不要"点这里"）
4. 不同文章的评论要不同
5. 风格多样：技术补充、经验分享、提问讨论"""

    prompt = f"""请为以下{len(articles)}篇CSDN文章生成评论。

产品链接（必须自然融入正文，不要单独放末尾）：
- 名称：{product_name or "产品"}
- 链接：{product_url}

文章列表：
{articles_text}

输出JSON数组：
[
  {{"article_url": "文章链接", "comment": "评论内容（50-500字，产品链接自然融入正文中间）"}}
]
"""

    try:
        resp = call_llm(prompt, sys_prompt, temperature=0.8, max_tokens=8000)
        comments = json.loads(resp) if isinstance(json.loads(resp), list) else []
        # 验证每条评论的 URL 匹配（取baseline部分对比，忽略追踪参数）
        def normalize_url(u):
            return u.split("?")[0].split("#")[0].rstrip("/")
        valid_bases = {normalize_url(a["url"]) for a in articles}
        valid_urls = {a["url"] for a in articles}
        result = []
        for c in comments:
            cu = normalize_url(c.get("article_url", ""))
            if cu in valid_bases and len(c.get("comment", "")) > 10:
                # 用原始URL（带参数）替换
                matching = [u for u in valid_urls if normalize_url(u) == cu]
                c["article_url"] = matching[0] if matching else cu
                result.append(c)
        return result
    except Exception as e:
        print(f"[ERROR] Batch comment generation failed: {e}")
        return []
