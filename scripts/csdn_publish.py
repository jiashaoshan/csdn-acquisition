#!/usr/bin/env python3
"""
CSDN 文章发布模块
功能：LLM生成文章 → BW浏览器自动化发布
"""
import json
import os
import re
import sys
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csdn_llm import call_llm

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

BW_EXECUTOR_URL = os.getenv("BROWSERWING_EXECUTOR_URL", "http://127.0.0.1:8080")
BW_PUBLISH_SCRIPT_ID = "csdn-publish-article-v1"


def generate_article(topic: str, style: str = "技术教程") -> dict:
    """LLM 生成 CSDN 文章内容"""
    sys_prompt = """你是一个CSDN技术文章作者。生成一篇高质量的技术博客文章。

输出格式为纯JSON（不要markdown代码块）：
{
  "title": "文章标题（吸引人，含数字或关键词）",
  "content": "完整Markdown内容（1500-3000字，含代码示例、目录结构）",
  "tags": "标签1,标签2,标签3",
  "categories": "分类目录",
  "description": "文章简介（100-150字）"
}"""

    prompt = f"""请生成一篇{style}方向的CSDN技术博客文章。

主题/方向：{topic}

要求：
- 标题吸引人，包含数字或关键词
- 内容 1500-3000 字，Markdown 格式
- 包含实际代码示例和运行效果说明
- 包含目录结构（使用 ### 标题层级）
- 结尾有总结
- 标签 3-5 个
- 分类填写 '{style}'
- 简介 100-150 字

只输出 JSON，不要 markdown 代码块外壳。"""

    print(f"[INFO] 生成文章: {topic}")
    result = call_llm(user_prompt=prompt, system_prompt=sys_prompt,
                      temperature=0.7, max_tokens=8192)

    try:
        data = json.loads(result)
    except json.JSONDecodeError:
        def fix_escapes(s):
            out, i = [], 0
            while i < len(s):
                if s[i] == '\\' and i + 1 < len(s) and s[i + 1] not in '"\\/bfnrtu':
                    out.append('\\\\')
                else:
                    out.append(s[i])
                i += 1
            return ''.join(out)

        try:
            data = json.loads(fix_escapes(result))
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', result, re.DOTALL)
            if m:
                data = json.loads(fix_escapes(m.group()))
            else:
                print(f"[ERROR] LLM 返回格式异常: {result[:300]}")
                return {}

    print(f"[INFO] 文章生成完成: {data.get('title', '未知')}")
    return data


def publish_article(article: dict, dry_run: bool = False) -> dict:
    """通过 BW 浏览器自动化发布文章到 CSDN"""
    title = article.get("title", "")
    content = article.get("content", "")

    if dry_run:
        print(f"[DRY-RUN] 发布文章: {title}")
        print(f"[DRY-RUN] 字数: {len(content)}")
        return {"success": True, "message": "dry_run"}

    print(f"[INFO] 发布文章: {title}（{len(content)} 字）")

    url = f"{BW_EXECUTOR_URL}/api/v1/scripts/{BW_PUBLISH_SCRIPT_ID}/play"
    payload = {"params": {"标题": title, "内容": content}}

    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"},
                             json=payload, timeout=180)
        resp.raise_for_status()
        result = resp.json()

        extracted = (result.get("result", {}) or {}).get("extracted_data", {}) or {}
        js_result = extracted.get("js_result_2", "") or ""

        if js_result:
            try:
                data = json.loads(js_result) if isinstance(js_result, str) else js_result
                return {
                    "success": True,
                    "url": data.get("url", ""),
                    "is_draft": data.get("is_editor", True),
                }
            except json.JSONDecodeError:
                pass

        print(f"[INFO] BW 响应: {json.dumps(result, ensure_ascii=False)[:500]}")
        return {"success": True, "data": result}

    except Exception as e:
        print(f"[ERROR] BW 调用失败: {e}")
        return {"success": False, "error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="CSDN 文章发布（BW版）")
    parser.add_argument("topic", nargs="?", default="", help="文章主题")
    parser.add_argument("-s", "--style", default="技术教程", help="文章风格")
    parser.add_argument("--dry-run", action="store_true", help="仅测试不发布")
    parser.add_argument("--no-generate", action="store_true", help="不生成文章，从文件读取")
    parser.add_argument("-f", "--file", default="", help="文章 JSON 文件路径")
    parser.add_argument("--topic-only", default="", help="只生成文章不发布，保存到文件")
    args = parser.parse_args()

    print("\n  ╔═════════════════════════════════╗")
    print("  ║   CSDN 文章发布（BW版）         ║")
    print("  ║   LLM生成 → BW自动化发布        ║")
    print("  ╚═════════════════════════════════╝\n")

    article = None
    if args.no_generate and args.file:
        with open(args.file) as f:
            article = json.load(f)
    elif args.topic_only:
        article = generate_article(args.topic_only, args.style)
        path = os.path.join(DATA_DIR, f"article_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"[INFO] 文章已保存: {path}")
        return {"success": True, "file": path}
    elif args.topic:
        article = generate_article(args.topic, args.style)
    else:
        topic = input("请输入文章主题: ").strip()
        style = input(f"请输入文章风格 [默认: 技术教程]: ").strip() or "技术教程"
        article = generate_article(topic, style)

    if not article:
        print("[ERROR] 未生成文章")
        return

    print(f"\n标题: {article.get('title')}")
    print(f"字数: {len(article.get('content', ''))}")
    print(f"标签: {article.get('tags')}\n")

    result = publish_article(article, dry_run=args.dry_run)

    print()
    if result.get("success") and not args.dry_run:
        url = result.get("url", "")
        if url and not result.get("is_draft", True):
            print(f"  ✅ 文章已发布！")
            print(f"  {url}")
        elif url:
            print(f"  ⚠️ 请检查 CSDN 后台确认发布结果")
            print(f"  {url}")
        else:
            print(f"  ✅ BW 执行完成，请检查 CSDN 后台")
    elif result.get("success") and args.dry_run:
        print(f"  ✅ Dry-Run 完成")
    else:
        print(f"  ❌ 发布失败: {result.get('error', '未知错误')}")

    return result


if __name__ == "__main__":
    main()
