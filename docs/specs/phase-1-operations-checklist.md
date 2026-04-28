# 一期操作清单 / 验收清单

> 目标：让你只看这一页，就知道当前一期系统已经有什么、平时怎么跑、以及什么时候算“一期可以先收口”。

## 1. 当前一期核心对象

一期默认围绕以下 6 类核心对象运转：

1. live facts
2. topic batch
3. publish day
4. column lifecycle
5. daily column allocation
6. column portfolio review

如果某次改动不直接服务这 6 类对象之一，就应先问一句：

- 它是不是已经超出一期边界？

---

## 2. 当前一期核心 artifacts

你现在最常看的正式产物是：

### 2.1 账号事实层
- `data/intel/accounts/*_live.{json,md}`
- `data/intel/accounts/*_full.{json,md}`

### 2.2 选题层
- `data/business/topic_batches/topic-batch_*.{json,md}`

### 2.3 当日执行层
- `data/daily_plans/YYYY-MM-DD.json`
- `data/daily_publish/YYYY-MM-DD/publish-day_YYYY-MM-DD.{json,md}`
- `data/daily_publish/YYYY-MM-DD/*_prompt.md`
- `data/daily_publish/YYYY-MM-DD/*_draft.md`

### 2.4 专栏经营层
- `data/business/column_allocations/daily-column-allocation_YYYY-MM-DD_<account>.{json,md}`
- `data/business/column_portfolio/column-portfolio-review_YYYY-MM-DD_<account>.{json,md}`

### 2.5 状态层
- `data/state/ledger/column/*.json`
- `data/state/ledger/column_allocation/*.json`
- `data/state/snapshots/YYYY-MM-DD.{json,md}`

---

## 3. 日常操作清单

### A. 先拿 live facts
如果你今天要基于真实账号状态决定写什么：

```bash
python -m app.main capture-csdn-live \
  --date YYYY-MM-DD \
  --account 技术小甜甜 \
  --profile new-main
```

如果需要更完整的专栏/历史内容层：
- 使用 full capture 流程对应产物
- 或继续使用已有 `*_full.json`

### B. 生成正式 topic batch
```bash
python -m app.main plan-topic-batch-from-live \
  --date YYYY-MM-DD \
  --account 技术小甜甜 \
  --snapshot-path data/intel/accounts/YYYY-MM-DD_技术小甜甜_live.json
```

你应该检查：
- 前 2 个执行位是否优先落到不同专栏
- 第二专栏选择是否带解释信号

### C. 生成当天发文包
```bash
python -m app.main prepare-publish-day \
  --plan-json-path data/daily_publish_inputs/YYYY-MM-DD_publish-plan.json
```

你应该检查：
- `daily_plans/YYYY-MM-DD.json`
- `publish-day_YYYY-MM-DD.json`
- 当天的 `*_prompt.md` / `*_draft.md`
- 自动生成的 `daily-column-allocation_YYYY-MM-DD_<account>.json`

### D. 维护专栏生命周期
```bash
python -m app.main set-column-lifecycle \
  --date YYYY-MM-DD \
  --account 技术小甜甜 \
  --column "AI实践-Dify专栏" \
  --lifecycle-state active_revenue \
  --role flagship_revenue
```

常用生命周期：
- `active_revenue`
- `active_traffic`
- `incubating`
- `paused`
- `deprecated`

### E. 生成专栏组合经营视图
```bash
python -m app.main column-portfolio-review \
  --date YYYY-MM-DD \
  --account 技术小甜甜
```

你应该检查：
- 当前有哪些专栏
- 各自 lifecycle 是什么
- 最近分配趋势
- 哪些专栏建议继续做收益位 / 引流位 / 试投 / 暂停 / 停止

---

## 4. 一期验收清单

只要下面都成立，就可以认为一期系统已经能稳定使用：

### 4.1 事实层
- [ ] 能抓或导入 live snapshot
- [ ] 能拿到 full capture / 历史专栏层信息

### 4.2 选题层
- [ ] 能生成正式 topic batch
- [ ] 前 2 个执行位能体现“2 篇/日 + 不同专栏优先”
- [ ] 第二专栏有可解释评分来源

### 4.3 执行层
- [ ] 能生成当天发文包
- [ ] prompt / draft / manifest 完整可用

### 4.4 专栏经营层
- [ ] 能记录 column lifecycle
- [ ] 能自动生成 daily column allocation
- [ ] 能生成 column portfolio review

### 4.5 状态层
- [ ] 关键对象有 state ledger
- [ ] 能生成 state snapshot

### 4.6 人工协同层
- [ ] 你能看懂每一步 artifact
- [ ] 你能手改 / 复核 / 继续推进
- [ ] 系统输出的是建议，不替代最终经营裁决

---

## 5. 哪些情况说明已经在超出一期范围

如果后续需求开始出现这些倾向，就说明可能要停一下，重新判断是否进入二期：

- 想同时优化新号和老号的全局调度
- 想直接做自动发布
- 想做精细收益预测或 ROI 模型
- 想把所有运营概念都做成独立对象
- 想在没有新增闭环价值的情况下继续加 artifact

判断标准：
- 没它是否就无法决策？
- 没它是否就无法执行或复盘？

如果两个答案都是否，那通常不该进入一期。

---

## 6. 当前推荐工作方式

对于现在这个阶段，最推荐的节奏是：

1. 抓 live facts
2. 出 topic batch
3. 做当天 2 篇专栏分配
4. 生成 publish day
5. 看 column portfolio review
6. 你做人类裁决
7. 系统保留 artifact 和状态，供下一轮继续使用

一句话：
- 先把 `技术小甜甜` 单账号 2 篇/日 的可解释经营闭环用顺，再考虑二期扩张。
