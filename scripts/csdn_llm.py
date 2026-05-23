#!/usr/bin/env python3
"""
CSDN 获客技能 - LLM API 封装
支持 DeepSeek (默认) 和 Baidu Qianfan 等多个 LLM 提供商
"""
import os, sys, json, re, requests
from typing import Optional, List, Dict, Any

DEFAULT_PROVIDER = "deepseek"


def _load_providers() -> dict:
    """从 openclaw.json 加载所有 LLM 提供商配置"""
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    if not os.path.exists(cfg_path):
        return {}
    with open(cfg_path) as f:
        cfg = json.load(f)
    providers = cfg.get("models", {}).get("providers", {})
    if isinstance(providers, dict):
        return providers
    return {}


def _resolve_provider_config(provider: str) -> dict:
    """解析指定提供商的 API 配置"""
    # 先查 openclaw.json
    providers = _load_providers()
    if provider in providers:
        p = providers[provider]
        model_list = p.get("models", [])
        model_id = model_list[0]["id"] if model_list else ""
        return {
            "base_url": p["baseUrl"].rstrip("/"),
            "api_key": p["apiKey"],
            "model": model_id,
        }

    # DeepSeek 回退
    if provider == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            cfg = os.path.expanduser("~/.openclaw/openclaw.json")
            if os.path.exists(cfg):
                with open(cfg) as f:
                    env = json.load(f).get("env", {})
                    if isinstance(env, dict):
                        key = env.get("DEEPSEEK_API_KEY", "")
        if key:
            return {
                "base_url": "https://api.deepseek.com",
                "api_key": key,
                "model": "deepseek-v4-flash",
            }
        raise ValueError("DEEPSEEK_API_KEY not set")

    raise ValueError(f"Unknown LLM provider: {provider}")


def list_providers() -> List[str]:
    """列出所有可用 LLM 提供商"""
    providers = _load_providers()
    names = list(providers.keys())
    if "deepseek" not in names:
        names.insert(0, "deepseek")
    return names


def call_llm(prompt: str, system_prompt: Optional[str] = None,
             temperature: float = 0.7, max_tokens: int = 4000,
             provider: str = DEFAULT_PROVIDER) -> str:
    cfg = _resolve_provider_config(provider)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        resp = requests.post(url,
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] LLM call failed ({provider}): {e}")
        if resp.text:
            print(f"[ERROR] Response: {resp.text[:300]}")
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


def generate_keywords(product_url: str, product_name: str = "",
                      provider: str = DEFAULT_PROVIDER) -> List[str]:
    """根据产品信息生成 CSDN 搜索关键词"""
    sys_prompt = """你是关键词研究专家。根据产品信息生成适合CSDN（中国开发者社区）搜索的关键词。
要求：5-10个中文关键词，覆盖产品类型、技术栈、应用场景、行业痛点。输出JSON数组。"""
    prompt = f"""产品链接：{product_url}
产品名称：{product_name or "未指定"}

生成5-10个CSDN搜索关键词，中文。输出JSON数组格式。"""
    try:
        resp = call_llm(prompt, sys_prompt, temperature=0.3, provider=provider)
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
                            product_name: str = "",
                            provider: str = DEFAULT_PROVIDER) -> List[Dict]:
    """
    批量生成评论（一次LLM调用，节省token）

    Args:
        articles: [{"title": "标题", "url": "链接", "content": "内容片段"}]
        product_url: 产品链接
        product_name: 产品名称
        provider: LLM 提供商
    Returns:
        [{"article_url": "链接", "comment": "评论内容"}]
    """
    def clean_url(u):
        return u.split("?")[0].split("#")[0].rstrip("/")
    articles_text = "\n\n".join([
        f"--- 文章{i+1} ---\n标题：{a.get('title','')}\n链接：{clean_url(a.get('url',''))}\n正文：{a.get('content','')[:2500]}"
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
        resp = call_llm(prompt, sys_prompt, temperature=0.8, max_tokens=8000, provider=provider)
        comments = _parse_llm_comments(resp)
        print(f"[INFO] LLM 返回 {len(comments)} 条原始评论")

        if not comments:
            return []

        def normalize_url(u):
            return (u or "").split("?")[0].split("#")[0].rstrip("/")

        def extract_article_id(u):
            m = re.search(r'/details/(\d+)', u)
            return m.group(1) if m else ""

        article_id_map = {}
        url_to_article = {}
        for i, a in enumerate(articles):
            original = a["url"]
            nid = extract_article_id(original)
            if nid:
                article_id_map[nid] = original
            url_to_article[normalize_url(original)] = original

        result = []
        for c in comments:
            raw_url = c.get("article_url", "")
            comment_text = c.get("comment", "")
            cu = normalize_url(raw_url)
            matched_url = None

            if cu in url_to_article:
                matched_url = url_to_article[cu]

            if not matched_url:
                nid = extract_article_id(raw_url)
                if nid and nid in article_id_map:
                    matched_url = article_id_map[nid]

            if not matched_url and len(result) < len(articles):
                matched_url = articles[len(result)]["url"]

            if matched_url and len(comment_text) > 10:
                c["article_url"] = matched_url
                result.append(c)
            else:
                print(f"[WARN] 跳过评论: URL={raw_url[:50]}... match={'yes' if matched_url else 'no'} len={len(comment_text)}")

        print(f"[INFO] URL 匹配后 {len(result)} 条有效评论")
        return result
    except Exception as e:
        print(f"[ERROR] Batch comment generation failed: {e}")
        return []


def _parse_llm_comments(raw: str) -> list:
    text = raw.strip()

    m = re.match(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
            if "article_url" in data or "comment" in data:
                return [data]
    except (json.JSONDecodeError, Exception):
        pass

    m = re.search(r'\[.*\]', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except (json.JSONDecodeError, Exception):
            pass

    print(f"[WARN] 无法解析 LLM 返回的评论 JSON: {raw[:200]}...")
    return []
