#!/usr/bin/env python3
"""
CSDN 获客技能 - 统一编排入口
"""
import os, sys, argparse, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csdn_comment_acquisition import acquire_comments

def main():
    parser = argparse.ArgumentParser(description="CSDN 获客技能")
    parser.add_argument("--acquire", action="store_true", help="评论区获客")
    parser.add_argument("--product-url", "-u", required=True, help="产品链接")
    parser.add_argument("--product-name", "-n", default="", help="产品名称")
    parser.add_argument("--keywords", "-k", default="", help="关键词（逗号分隔）")
    parser.add_argument("--max-comments", "-m", type=int, default=5, help="最大评论数")
    parser.add_argument("--dry-run", action="store_true", help="仅测试不评论")
    args = parser.parse_args()

    kw = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else None

    if args.acquire:
        result = acquire_comments(args.product_url, args.product_name, kw,
                                   args.max_comments, args.dry_run)
        print(f"\n{'='*40}")
        print(f"结果: {'✅ 成功' if result.get('success') else '❌ 失败'}")
        print(f"共评论: {result.get('total', 0)} 条")
        for c in result.get("comments", []):
            print(f"  {c.get('article_url','')[:50]}...")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
