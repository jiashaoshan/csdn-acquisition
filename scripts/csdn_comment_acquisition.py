#!/usr/bin/env python3
"""
CSDN 评论区获客模块
功能：搜索文章 → AI评分 → 批量生成评论 → BW评论
"""
import os, sys, json, time, random, requests
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csdn_llm import generate_keywords, generate_comments_batch

# BrowserWing
BW_EXECUTOR_URL = os.getenv("BROWSERWING_EXECUTOR_URL", "http://127.0.0.1:8080")
BW_SEARCH_SCRIPT_ID = "fd1119b5-2546-4791-8efb-76f7d865a1e1"
BW_COMMENT_SCRIPT_ID = "23d2a4a9-97d2-4d9c-821b-9ec2e2dd07f7"
BW_ARTICLE_CONTENT_SCRIPT_ID = "csdn-article-content-000000000000"  # 导入 bw-scripts/csdn-article-content.json 后替换为真实 UUID

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "commented-history.json")
FILTER_FILE = os.path.join(SKILL_DIR, "config", "filter.json")

os.makedirs(DATA_DIR, exist_ok=True)

def _base_url(url: str) -> str:
    """去掉追踪参数，用 base URL 做去重"""
    return url.split("?")[0].split("#")[0].rstrip("/")


def load_config() -> dict:
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE) as f:
            return json.load(f)
    return {}

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history: list):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def search_articles(keyword: str) -> List[Dict]:
    """调用 BW 脚本搜索 CSDN 文章"""
    url = f"{BW_EXECUTOR_URL}/api/v1/scripts/{BW_SEARCH_SCRIPT_ID}/play"
    payload = {"params": {"关键词": keyword}}
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                              json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        # 从 result.result.extracted_data.js_result_0 提取
        extracted = (result.get("result", {}) or {}).get("extracted_data", {}) or {}
        articles = extracted.get("js_result_0", []) or []
        if not isinstance(articles, list):
            articles = []
        # 标准化字段名
        normalized = []
        seen_bases = set()
        for a in articles:
            if not isinstance(a, dict):
                continue
            article_url = a.get("link", "") or a.get("url", "")
            base = _base_url(article_url)
            if not article_url or base in seen_bases:
                continue
            seen_bases.add(base)
            normalized.append({
                "title": a.get("title", "") or "",
                "url": article_url,
                "base_url": base,
                "content": a.get("content", "") or a.get("desc", "") or "",
                "createTime": a.get("createTime", "") or "",
            })
        print(f"[INFO] 搜索 '{keyword}' 找到 {len(normalized)} 篇")
        return normalized
    except Exception as e:
        print(f"[ERROR] 搜索失败: {e}")
        return []


def fetch_article_content(article_url: str, timeout: int = 20) -> dict:
    """
    调用 BW 脚本打开 CSDN 文章页，滚动触发懒加载后提取全文。
    多个选择器降级兼容不同 CSDN 皮肤/版本。
    
    Returns:
        dict: {"title": str, "content": str}, content 最多 5000 字
        失败返回 {"title": "", "content": ""}
    """
    url = f"{BW_EXECUTOR_URL}/api/v1/scripts/{BW_ARTICLE_CONTENT_SCRIPT_ID}/play"
    payload = {"params": {"链接": article_url}}
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                             json=payload, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()
        extracted = (result.get("result", {}) or {}).get("extracted_data", {}) or {}
        data = extracted.get("js_result_0", {}) or {}
        if not isinstance(data, dict):
            data = {}
        title = data.get("title", "").strip()
        content = data.get("content", "").strip()
        if content:
            print(f"[INFO]   全文获取: {len(content)} 字")
            return {"title": title, "content": content}
        else:
            print(f"[WARN]   全文获取失败，fallback 到搜索摘要")
            return {"title": title, "content": ""}
    except Exception as e:
        print(f"[WARN]   文章内容获取异常: {e}，fallback 到搜索摘要")
        return {"title": "", "content": ""}


def comment_on_article(article_url: str, content: str, dry_run: bool = False) -> dict:
    """调用 BW 脚本发表评论（含反爬延迟）"""
    if dry_run:
        print(f"[DRY-RUN] 评论: {content[:50]}... → {article_url}")
        return {"success": True, "message": "Dry run"}

    url = f"{BW_EXECUTOR_URL}/api/v1/scripts/{BW_COMMENT_SCRIPT_ID}/play"
    payload = {"params": {"内容": content, "链接": article_url}}
    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                              json=payload, timeout=120)
        resp.raise_for_status()
        print(f"[INFO] ✅ 评论成功: {article_url[:50]}...")
        return {"success": True, "raw": resp.json()}
    except Exception as e:
        print(f"[ERROR] ❌ 评论失败 {article_url[:30]}...: {e}")
        return {"success": False, "message": str(e)}

def anti_scrape_delay(config: dict):
    """反爬延迟（随机抖动）"""
    base = config.get("base_interval_seconds", 180)
    jitter_ratio = config.get("jitter_ratio", 0.3)
    delay = base * (1 + random.uniform(-jitter_ratio, jitter_ratio))
    delay = max(delay, 30)  # 最少30秒
    print(f"[INFO] 等待 {delay:.0f} 秒（反爬延迟）...")
    time.sleep(delay)

def check_rate_limit(history: list, config: dict) -> bool:
    """检查是否超过速率限制（含日/小时上限 + 工作时段）"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    # commented_at 存的是 ISO 格式 "2026-05-21T14:35:22" 含 T，不是空格
    this_hour = now.strftime("%Y-%m-%dT%H")

    today_count = sum(1 for h in history if h.get("commented_at", "").startswith(today))
    hour_count = sum(1 for h in history if h.get("commented_at", "").startswith(this_hour))

    max_day = config.get("max_comments_per_day", 20)
    max_hour = config.get("max_comments_per_hour", 5)

    if today_count >= max_day:
        print(f"[WARN] 今日评论已达上限 ({max_day})")
        return False
    if hour_count >= max_hour:
        print(f"[WARN] 本小时评论已达上限 ({max_hour})")
        return False

    # 工作时段检查
    hour = now.hour
    start = config.get("active_hours_start", 8)
    end = config.get("active_hours_end", 23)
    if hour < start or hour >= end:
        print(f"[WARN] 不在工作时段内 ({start}:00-{end}:00)")
        return False
    return True

def acquire_comments(product_url: str, product_name: str = "",
                     keywords: List[str] = None, max_comments: int = 5,
                     dry_run: bool = False) -> dict:
    """评论区获客主流程"""
    config = load_config()
    min_score = config.get("min_score_threshold", 60)
    max_comments = min(max_comments, config.get("max_comments_per_run", 5))

    print(f"[INFO] CSDN 评论区获客: {product_url}")
    print(f"[INFO] 最大评论: {max_comments}, 最低评分: {min_score}")

    # 1. 生成关键词
    if not keywords:
        print("[INFO] 生成关键词...")
        keywords = generate_keywords(product_url, product_name)
    print(f"[INFO] 关键词: {keywords}")

    # 2. 加载历史（用base URL做去重）
    history = load_history()
    commented_bases = {_base_url(h.get("article_url", "")) for h in history}
    print(f"[INFO] 已评论 {len(commented_bases)} 篇（去追踪参数）")

    # 3. 搜索（含随机间隔避免触发 CSDN 反爬）
    all_articles = []
    search_kws = keywords[:3]  # 最多 3 个关键词
    for i, kw in enumerate(search_kws):
        if i > 0:
            delay = random.uniform(5, 10)
            print(f"[INFO] 搜索间隔 {delay:.1f} 秒...")
            time.sleep(delay)
        articles = search_articles(kw)
        all_articles.extend(articles)

    # 再次去重（不同关键词可能搜到同一篇）
    seen_bases = set()
    unique_articles = []
    for a in all_articles:
        base = a.get("base_url", "") or _base_url(a.get("url", ""))
        if base and base not in seen_bases:
            seen_bases.add(base)
            unique_articles.append(a)
    print(f"[INFO] 去重后 {len(unique_articles)} 篇")

    # 4. 过滤已评论（用base URL）
    new_articles = [a for a in unique_articles
                    if (a.get("base_url", "") or _base_url(a.get("url", ""))) not in commented_bases]
    print(f"[INFO] 未评论 {len(new_articles)} 篇")

    if not new_articles:
        return {"success": True, "total": 0, "comments": [], "message": "无新文章"}

    # 5. 取候选文章 + 抓取全文（fallback 到搜索摘要）
    candidates = new_articles[:15]
    articles_for_llm = []
    for i, a in enumerate(candidates[:max_comments]):
        article_url = a.get("url", "") or a.get("link", "")
        print(f"[INFO] 获取全文 [{i+1}/{min(max_comments, len(candidates))}]: {article_url[:60]}...")

        full = {"title": a.get("title", ""), "content": ""}
        if article_url:
            # 非首篇文章间加延迟
            if i > 0:
                delay = random.uniform(3, 6)
                print(f"[INFO]   文章间隔 {delay:.1f} 秒...")
                time.sleep(delay)
            full = fetch_article_content(article_url)

        articles_for_llm.append({
            "title": full.get("title") or a.get("title", ""),
            "url": article_url,
            # 优先全文，fallback 到搜索摘要（最多 500 字，原先是 300）
            "content": full.get("content") or a.get("content", "") or a.get("desc", "") or "",
        })

    print(f"[INFO] 批量生成 {len(articles_for_llm)} 条评论...")
    comments_data = generate_comments_batch(articles_for_llm, product_url, product_name)
    print(f"[INFO] 生成评论: {len(comments_data)} 条")

    # 7. 逐条发表
    comments_made = []
    for i, cd in enumerate(comments_data):
        if not check_rate_limit(history, config):
            break

        # 反爬延迟（dry-run 跳过，第一条不延时）
        if i > 0 and not dry_run:
            anti_scrape_delay(config)

        result = comment_on_article(cd["article_url"], cd["comment"], dry_run)
        if result["success"]:
            record = {
                "article_url": cd["article_url"],
                "comment": cd["comment"],
                "commented_at": datetime.now().isoformat(),
            }
            comments_made.append(record)
            if not dry_run:
                history.append(record)
                save_history(history)
        else:
            print(f"[WARN] 跳过 {cd['article_url'][:30]}...: {result.get('message')}")

    print(f"[INFO] 获客完成: {len(comments_made)} 条评论")
    return {"success": True, "total": len(comments_made), "comments": comments_made}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CSDN 评论区获客")
    parser.add_argument("--product-url", required=True, help="产品链接")
    parser.add_argument("--product-name", default="", help="产品名称")
    parser.add_argument("--keywords", default="", help="关键词（逗号分隔）")
    parser.add_argument("--max-comments", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    kw = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else None
    result = acquire_comments(args.product_url, args.product_name, kw,
                               args.max_comments, args.dry_run)
    print(f"\n{'='*40}")
    print(f"共评论: {result['total']} 条")
    for c in result.get("comments", []):
        print(f"  {c['article_url'][:50]}... → {c['comment'][:40]}...")
