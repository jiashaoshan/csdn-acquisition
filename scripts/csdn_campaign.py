#!/usr/bin/env python3
"""
CSDN 获客技能 - 统一编排入口
"""
import os, sys, argparse, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csdn_comment_acquisition import acquire_comments
from csdn_publish import generate_article, publish_article

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_DIR, "data")


def main():
    parser = argparse.ArgumentParser(description="CSDN 获客技能")
    # 模式
    parser.add_argument("--acquire", action="store_true", help="评论区获客")
    parser.add_argument("--publish", action="store_true", help="发布文章（LLM生成 → BW发布）")
    parser.add_argument("--gen-article", metavar="TOPIC", default="", help="仅生成文章并保存，不发布")
    # acquire 参数
    parser.add_argument("-u", "--product-url", default="", help="产品链接")
    parser.add_argument("-n", "--product-name", default="", help="产品名称")
    parser.add_argument("-k", "--keywords", default="", help="关键词（逗号分隔）")
    parser.add_argument("-m", "--max-comments", type=int, default=5, help="最大评论数")
    # publish 参数
    parser.add_argument("-s", "--style", default="技术教程", help="文章风格")
    parser.add_argument("-t", "--topic", default="", help="文章主题")
    parser.add_argument("-f", "--file", default="", help="从 JSON 文件读取文章发布")
    # 通用
    parser.add_argument("--dry-run", action="store_true", help="仅测试不执行")
    args = parser.parse_args()

    # ── 仅生成文章 ──
    if args.gen_article:
        article = generate_article(args.gen_article, args.style)
        if not article:
            print("[ERROR] 文章生成失败")
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, f"article_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)
        print(f"\n标题: {article.get('title')}")
        print(f"已保存: {path}")
        return

    # ── 发布文章 ──
    if args.publish:
        article = None
        if args.file:
            with open(args.file, encoding="utf-8") as f:
                article = json.load(f)
        elif args.topic:
            article = generate_article(args.topic, args.style)
        else:
            print("发布文章需要指定 --topic 或 --file")
            return

        if not article:
            print("[ERROR] 文章生成失败")
            return

        print(f"\n标题: {article.get('title')}")
        print(f"字数: {len(article.get('content', ''))}")

        result = publish_article(article, dry_run=args.dry_run)

        print(f"\n{'='*40}")
        if result.get("success") and not args.dry_run:
            url = result.get("url", "")
            if url and not result.get("is_draft", True):
                print(f"结果: ✅ 文章已发布！")
                print(f"  {url}")
            elif url:
                print(f"结果: ⚠️ 文章可能仍为草稿，请检查 CSDN 后台")
                print(f"  {url}")
            else:
                print(f"结果: ✅ BW 执行完成，请检查 CSDN 后台")
        elif result.get("success") and args.dry_run:
            print(f"结果: ✅ Dry-Run（未实际发布）")
        else:
            print(f"结果: ❌ 发布失败")
            print(f"  {result.get('error', '未知错误')}")
        return

    # ── 评论区获客 ──
    kw = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else None

    if args.acquire:
        if not args.product_url:
            args.product_url = os.environ.get("CSDN_PRODUCT_URL", "")
        if not args.product_url:
            print("错误: 评论区获客需要 -u/--product-url 或 CSDN_PRODUCT_URL 环境变量")
            return

        result = acquire_comments(args.product_url, args.product_name, kw,
                                   args.max_comments, args.dry_run)
        print(f"\n{'='*40}")
        print(f"结果: {'✅ 成功' if result.get('success') else '❌ 失败'}")
        print(f"共评论: {result.get('total', 0)} 条")
        for c in result.get("comments", []):
            print(f"  {c.get('article_url','')[:50]}...")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
