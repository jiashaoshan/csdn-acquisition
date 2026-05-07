# 💻 CSDN 获客技能 (csdn-acquisition)

> AI 驱动的 CSDN 技术社区自动化获客解决方案。基于 BrowserWing 浏览器自动化 + DeepSeek API 驱动 AI 内容生成。

---

## 功能矩阵

| 功能 | 状态 | 说明 |
|------|------|------|
| 🎯 **评论区获客** | ✅ 可用 | 关键词搜索 → 文章列表 → AI评分 → 批量LLM评论 → BW评论 |
| 📝 **CSDN 文章发布** | ⏳ 待实现 | - |

---

## 系统架构

```
┌──────────────────────────────────────────────────────┐
│                  入口层 csdn_campaign.py               │
│  --acquire（评论区获客）                               │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│             csdn_comment_acquisition.py                │
│                                                        │
│  1. 关键词生成 (LLM) → 2. BW搜索 → 3. 历史去重        │
│  4. 批量评论生成 (LLM, 一次调用) → 5. BW评论 + 反爬    │
└──────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
┌──────────────────┐   ┌──────────────────────────┐
│    csdn_llm.py    │   │   BrowserWing (8080)      │
│  DeepSeek API 封装 │   │                           │
│  - 关键词生成      │   │  fd1119b5 → 搜索CSDN文章  │
│  - 批量评论生成    │   │  23d2a4a9 → 发表评论      │
└──────────────────┘   └──────────────────────────┘
```

---

## 评论区获客流程

```
[1. 关键词] → LLM 根据产品链接生成 CSDN 搜索关键词
      ↓
[2. 搜索] → BW 脚本搜索 CSDN，获取文章列表（标题+链接+内容摘要）
      ↓
[3. 过滤] → 去重（base URL，去除追踪参数）→ 过滤已评论历史
      ↓
[4. 批量生成评论] → LLM 一次调用生成所有评论（节省 token）
      │               每条评论 50-500 字
      │               产品链接自然融入正文中间
      │               风格多样：赞同/补充/提问/经验分享
      ↓
[5. 逐条评论] → BW 脚本逐条发表评论
      │               反爬策略：30s 随机延迟抖动
      │               每日上限 20 条 / 每小时 5 条
      ↓
[6. 记录] → JSON 持久化已评论文章 base URL，避免重复
```

### 评论风格

每条评论像真实开发者写的，产品链接自然融入正文：

```
❌ 硬广风：
"写得不错！推荐大家试试 PDP 性格测试 https://xxx"

✅ 自然风：
"之前团队做项目时用过PDP性格测试(https://xxx)，分析成员风格还挺准的"
```

| 技巧 | 示例 |
|------|------|
| 经验分享型 | "之前做XX的时候试过XX(链接)，感觉…" |
| 问题关联型 | "这个问题让我想到XX(链接)…" |
| 对比讨论型 | "MBTI偏自我认知，PDP(链接)更侧重行为风格" |
| 亲身经历型 | "我测完发现自己属于XX型(链接)，才知道为什么" |

---

## 安装与依赖

### Python 依赖

```bash
pip install requests
```

### BrowserWing

需要 BrowserWing 服务运行中（默认 `http://127.0.0.1:8080`），并已注册以下脚本：

| 脚本 ID | 功能 | 参数 |
|---------|------|------|
| `fd1119b5-2546-4791-8efb-76f7d865a1e1` | CSDN 关键词搜索文章 | `{"关键词": "..."}` |
| `23d2a4a9-97d2-4d9c-821b-9ec2e2dd07f7` | CSDN 文章评论 | `{"内容": "...", "链接": "..."}` |

脚本 JSON 定义见 `bw-scripts/` 目录。

### DeepSeek API

需要 `DEEPSEEK_API_KEY` 环境变量，或配置在 `~/.openclaw/openclaw.json`：

```json
{
  "env": {
    "DEEPSEEK_API_KEY": "sk-xxx"
  }
}
```

---

## 配置

`config/filter.json` — 风控和运行参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_comments_per_run` | 5 | 每次运行最多评论 |
| `max_comments_per_day` | 20 | 每天评论上限 |
| `max_comments_per_hour` | 5 | 每小时评论上限 |
| `base_interval_seconds` | 30 | 评论间隔（秒） |
| `jitter_ratio` | 0.2 | 抖动比例 |
| `active_hours_start` | 8 | 活跃时段开始 |
| `active_hours_end` | 23 | 活跃时段结束 |
| `min_score_threshold` | 60 | 最低评分阈值 |
| `comment_max_chars` | 1000 | 评论最大字符数 |

`config/keywords.json` — 种子关键词（LLM 生成失败时的 fallback）。

---

## 快速开始

```bash
# 完整流程：生成关键词 → 搜索 → 评分 → 批量生成评论 → 逐条评论
python3 scripts/csdn_campaign.py \
  --acquire \
  --product-url "https://your-product.com" \
  --product-name "产品名"

# 指定搜索关键词
python3 scripts/csdn_campaign.py \
  --acquire \
  --product-url "https://your-product.com" \
  --keywords "OpenClaw,AI agent"

# Dry-run 安全测试（不发表真实评论）
python3 scripts/csdn_campaign.py \
  --acquire \
  --product-url "https://your-product.com" \
  --dry-run

# 限制评论数（反爬间隔更短）
python3 scripts/csdn_campaign.py \
  --acquire \
  --product-url "https://your-product.com" \
  --max-comments 3
```

---

## 文件结构

```
csdn-acquisition/
├── SKILL.md                           ← OpenClaw 技能描述
├── README.md                          ← 本文
├── scripts/
│   ├── csdn_campaign.py               ← 统一编排入口
│   ├── csdn_comment_acquisition.py    ← 评论区获客核心
│   │   ├ LLM关键词 → BW搜索 → 过滤历史
│   │   ├ 批量生成评论（一次LLM调用，省token）
│   │   └ BW逐条评论 + 反爬延迟 + 速率限制
│   └── csdn_llm.py                    ← LLM封装
├── templates/
│   ├── comment-prompt.md               ← 评论生成提示词
│   └── keyword-generation.md           ← 关键词生成提示词
├── bw-scripts/
│   ├── csdn-search.json                ← BW搜索脚本定义
│   └── csdn-comment.json               ← BW评论脚本定义
├── config/
│   ├── keywords.json                   ← 种子关键词
│   └── filter.json                     ← 风控配置
└── data/
    └── commented-history.json          ← 评论历史（去重用）
```

---

## 验收清单

- [x] BW 搜索脚本返回 CSDN 文章列表（标题+链接+内容摘要+时间）
- [x] LLM 根据产品生成搜索关键词
- [x] base URL 去重（去除追踪参数）
- [x] 历史记录过滤（已评论不重复）
- [x] 批量评论生成（一次 LLM 调用，多条评论）
- [x] 评论含产品链接，自然融入正文
- [x] BW 评论脚本成功发表
- [x] 反爬策略：随机延迟 + 日/小时上限
- [x] Json 持久化评论历史
- [ ] CSDN 文章自动编写（待实现）
