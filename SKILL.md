---
name: csdn-acquisition
description: |
  CSDN 平台获客技能
  功能：评论区获客
  基于 BrowserWing 实现浏览器自动化 + DeepSeek API 驱动 AI 内容生成
metadata:
  openclaw:
    emoji: "💻"
    requires:
      env: ["BROWSERWING_EXECUTOR_URL", "DEEPSEEK_API_KEY"]
    category: "acquisition"
    tags: ["csdn", "acquisition", "comment", "browserwing", "ai"]
---

# CSDN 平台获客技能 (csdn-acquisition)

AI 驱动的 CSDN 技术社区获客解决方案。

## 功能矩阵

| 功能 | 状态 | 说明 |
|------|------|------|
| 🎯 评论区获客 | ✅ 可用 | 关键词搜索 → 文章列表 → 批量LLM评论 → BW评论 |
| 📝 文章自动化 | ⏳ 待实现 | - |

## 依赖

- Python 3.8+
- BrowserWing 服务（默认 `http://127.0.0.1:8080`）
- DeepSeek API Key（环境变量 `DEEPSEEK_API_KEY`）
- BrowserWing 注册脚本：
  - `fd1119b5-2546-4791-8efb-76f7d865a1e1` — CSDN 搜索文章
  - `23d2a4a9-97d2-4d9c-821b-9ec2e2dd07f7` — CSDN 文章评论

## 快速使用

```bash
# 完整流程：生成关键词 → 搜索 → 过滤 → 批量评论
python3 scripts/csdn_campaign.py --acquire --product-url "https://ai.hcrzx.com"

# 指定关键词
python3 scripts/csdn_campaign.py --acquire --product-url "https://ai.hcrzx.com" --keywords "OpenClaw,AI agent"

# Dry-run 安全测试
python3 scripts/csdn_campaign.py --acquire --product-url "https://ai.hcrzx.com" --dry-run

# 限制评论数
python3 scripts/csdn_campaign.py --acquire --product-url "https://ai.hcrzx.com" --max-comments 3
```

## 评论区获客流程

```
[1. 关键词] → LLM 根据产品链接生成CSDN搜索关键词
      ↓
[2. 搜索] → BW 脚本搜索 CSDN，获取文章列表（标题+链接）
      ↓
[3. 过滤] → 去重（历史记录），过滤已评论文
      ↓
[4. 评论内容] → LLM 批量生成评论（一次调用，省token）
      ↓
[5. 发送] → BW 脚本逐条发表评论（带随机延迟反爬）
      ↓
[6. 记录] → JSON 持久化已评论文章，避免重复
```

### 反爬策略

- 每次评论间隔随机延迟（180-300秒抖动）
- 每日评论上限（默认20条）
- 每小时评论上限（默认5条）
- 活跃时段限制（8:00-23:00）
- 已评论文章永久去重

## 文件结构

```
csdn-acquisition/
├── SKILL.md                       ← 本文
├── scripts/
│   ├── csdn_campaign.py           ← 统一编排入口
│   ├── csdn_comment_acquisition.py ← 评论区获客模块
│   └── csdn_llm.py                ← LLM API 封装
├── templates/
│   ├── comment-prompt.md           ← 评论生成提示词
│   └── keyword-generation.md       ← 关键词生成提示词
├── config/
│   ├── keywords.json               ← 种子关键词
│   └── filter.json                 ← 风控配置
├── bw-scripts/
│   └── csdn-search.json            ← BW 搜索脚本参考
└── data/                           ← 运行时数据（评论历史）
```

## 配置

`config/filter.json`:

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_comments_per_run | 5 | 每次运行最多评论 |
| max_comments_per_day | 20 | 每天评论上限 |
| max_comments_per_hour | 5 | 每小时评论上限 |
| base_interval_seconds | 180 | 评论间隔（秒） |
| jitter_ratio | 0.3 | 抖动比例 |
| active_hours_start | 8 | 活跃时段开始 |
| active_hours_end | 23 | 活跃时段结束 |
| min_score_threshold | 60 | 最低评分阈值 |
| comment_max_chars | 1000 | 评论最大字符数 |
