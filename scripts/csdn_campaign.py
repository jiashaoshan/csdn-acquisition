#!/usr/bin/env python3
"""
CSDN 获客技能 - 评论区获客入口
"""
import os, sys, argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csdn_comment_acquisition import acquire_comments

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SKILL_DIR, "data")


def main():
    parser = argparse.ArgumentParser(description="CSDN 评论区获客")
    parser.add_argument("-u", "--product-url", default="", help="产品链接")
    parser.add_argument("-n", "--product-name", default="", help="产品名称")
    parser.add_argument("-k", "--keywords", default="", help="关键词（逗号分隔）")
    parser.add_argument("-m", "--max-comments", type=int, default=5, help="最大评论数")
    parser.add_argument("--dry-run", action="store_true", help="仅测试不执行")
    args = parser.parse_args()

    kw = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else None

    if not args.product_url:
        args.product_url = os.environ.get("CSDN_PRODUCT_URL", "")
    if not args.product_url:
        print("错误: 需要 -u/--product-url 或 CSDN_PRODUCT_URL 环境变量")
        return

    result = acquire_comments(args.product_url, args.product_name, kw,
                               args.max_comments, args.dry_run)
    print(f"\n{'='*40}")
    print(f"结果: {'✅ 成功' if result.get('success') else '❌ 失败'}")
    print(f"共评论: {result.get('total', 0)} 条")
    for c in result.get("comments", []):
        print(f"  {c.get('article_url','')[:50]}...")


if __name__ == "__main__":
    main()
