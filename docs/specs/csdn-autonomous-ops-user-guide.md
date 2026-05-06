# CSDN 自主运营系统使用手册

> 目标：把这套系统从“设计文档”变成“你每天能直接拿来做决策、下命令、看结果”的操作手册。

## 1. 这套系统怎么帮你参与决策

系统的核心不是替你写文章，而是把你每天的判断拆成几类输入，再把输入变成下一步动作：

- 看什么：账号表现、用户反馈、对标账号、市场信号、专栏转化
- 怎么记：统一进 `data/intel/`
- 怎么判断：通过 `review-intel`、`plan-topic`、`score-topic` 等命令
- 怎么落地：通过 `plan-workflow`、`execute-topic`、`check-publish` 等命令
- 怎么复盘：通过 `review-business`、`review-process`、`review-rules`、`state-snapshot`

一句话：

- 第 0 层负责告诉你“现在该看什么”
- 自动进化策略流程的输出，是选题流程的输入之一
- 选题流程的输出，是发布流程的输入
- 第 1~4 层负责告诉你“该怎么想”
- 第 5~6 层负责告诉你“该怎么做、做到了什么”

---

## 2. 默认资源放哪里

除非你特别指定，新资源默认都放在项目目录：

- `/mnt/e/个人项目/CSDN账号运营/content-ops/`
- `/mnt/e/个人项目/CSDN账号运营/automation-system/`

其中：

- `content-ops/` 更适合放内容参考、草稿、运营记录
- `automation-system/` 更适合放代码、CLI、状态数据、规范文档

---

## 3. 你日常最常用的 5 类动作

### 3.1 先收集经营输入

当你看到一条有价值的信息，就先记下来，不要靠脑子硬扛。

如果你想让选题依据直接来自账号实时页面，而不是旧文档，可先做实时采集：

```bash
python -m app.main capture-csdn-live \
  --date 2026-04-21 \
  --account 技术小甜甜 \
  --profile new-main
```

采完后，再基于实时事实生成正式 topic batch：

```bash
python -m app.main plan-topic-batch-from-live \
  --date 2026-04-21 \
  --account 技术小甜甜 \
  --snapshot-path data/intel/accounts/2026-04-21_技术小甜甜_live.json
```

这个命令会把 live snapshot 作为正式选题依据；没有 snapshot 时，不应使用它产出正式 batch。

对于 `技术小甜甜` 的默认日更节奏，正式 batch 里的前 2 个执行位应优先视为“当天两篇”，因此只要 live facts 里能识别出可用第二专栏，就应尽量把前 2 个题分散到不同专栏，而不是都压到同一专栏。

当存在同日多个候选专栏时，系统应优先使用可解释评分来选择第二专栏，至少综合：与旗舰专栏的互补性、专栏是否付费、历史文章数、可见互动/指标、当前状态。

如果工作区里已经存在该账号的 strategy outputs、column assets、sales/click 记录、feedback 记录，这些业务信号也应参与第二专栏评分，而不是只看 live snapshot 的表面专栏名。

同时要注意：候选专栏不只包括收益型/付费专栏，也包括承担引流任务的免费专栏。也就是说，系统未来不该只做“收益点专栏分配”，而应做“收益专栏 + 免费引流专栏”的联合分配。

再往后一步，专栏分配不只是当天发哪两个专栏的问题，还应逐步支持专栏生命周期管理：新增专栏、暂停/停止更新专栏、恢复更新专栏。

当前已经增加两个基础命令用于承接这层能力：

```bash
python -m app.main set-column-lifecycle \
  --date 2026-04-25 \
  --account 技术小甜甜 \
  --column "AI实践-Dify专栏" \
  --lifecycle-state active_revenue \
  --role flagship_revenue

python -m app.main write-daily-column-allocation \
  --date 2026-04-25 \
  --account 技术小甜甜 \
  --slot "1|AI实践-Dify专栏|flagship_revenue|active_revenue|旗舰收益位|9.8|live batch;strategy" \
  --slot "2|技术前沿每日速读|traffic_support|active_traffic|免费引流位|7.1|traffic signal;feedback"

python -m app.main column-portfolio-review \
  --date 2026-04-25 \
  --account 技术小甜甜
```

而且 `prepare-publish-day` 现在也会自动生成对应的 daily-column-allocation artifact，不需要再手工补一份当日专栏分配说明。
`column-portfolio-review` 会把 lifecycle、最近专栏分配、以及 strategy / column asset / sales / feedback 信号汇总成一份专栏组合经营视图。

这个命令会打开带登录态的浏览器 profile，并按提示让你依次切到：
- 专栏/专辑列表页
- 专栏/专辑数据页
- 历史文章列表页

采集完成后会生成：
- `data/intel/accounts/YYYY-MM-DD_<account>_live.json`
- `data/intel/accounts/YYYY-MM-DD_<account>_live.md`

如果你已经有外部脚本抓到的原始 JSON，也可以导入：

```bash
python -m app.main import-csdn-live-snapshot \
  --date 2026-04-21 \
  --account 技术小甜甜 \
  --snapshot-json-path /path/to/raw-live.json
```

常用命令：

```bash
python -m app.main collect-intel --kind feedback --date 2026-04-19 --account 技术小甜甜 --summary "评论里有人问如何从零开始做 CSDN 专栏"
```

其他常见记录：

```bash
python -m app.main log-feedback --date 2026-04-19 --account 技术小甜甜 --source review --feedback-type needs_revision --content "标题要更具体"
python -m app.main log-competitor --date 2026-04-19 --account 技术小甜甜 --url "https://example.com" --notes "这个标题结构很强"
python -m app.main log-sales --date 2026-04-19 --account 技术小甜甜 --column "CSDN专栏" --metric click --value 18 --notes "CTA 放在文末效果更好"
```

### 3.2 每周/每月先看复盘

先看经营输入，再决定下一轮写什么。

```bash
python -m app.main review-intel --period week --date 2026-04-19
python -m app.main review-intel --period month --date 2026-04-30
```

如果你想看某个账号的局部情况，可以加 `--account`。

### 3.3 决定写什么

当你已经知道要写什么，就把它变成“业务决策单”。

```bash
python -m app.main plan-topic \
  --date 2026-04-19 \
  --account 技术小甜甜 \
  --title "新手如何快速做出第一个 CSDN 专栏" \
  --audience "刚开始做技术内容、想要稳定增长的人" \
  --column "专栏增长" \
  --angle "从0到1的最小闭环" \
  --value "把复杂流程拆成可执行步骤" \
  --cta "引导进入专栏/系列文章" \
  --why-now "新号需要优先做低门槛、强转化内容"
```

这个命令会生成一个业务 brief，告诉系统：

- 这题是谁写
- 给谁看
- 为什么值得写
- 怎么导向专栏或转化

### 3.4 把题目变成今天可执行的发文包

如果你今天就要在新旧账号各发 2 篇，先准备当日发文包：

```bash
python -m app.main prepare-publish-day \
  --plan-json-path data/daily_publish_inputs/2026-04-21_publish-plan.json
```

这个命令会一次性产出：

- 当日排期板：`data/daily_plans/YYYY-MM-DD.json`
- 每个槽位的 `*_prompt.md` 写作提示词
- 每个槽位的 `*_draft.md` 草稿模板
- 当日总清单：`data/daily_publish/YYYY-MM-DD/publish-day_YYYY-MM-DD.{json,md}`

推荐顺序：

1. 先打开 `*_prompt.md` 交给写作模型生成正文
2. 把正文回填到 `*_draft.md`，人工快速修一轮
3. 再用下面的 `plan-workflow` / `execute-topic` 把它送进草稿保存流程

### 3.5 把题目变成流程和待审任务

如果已经有正文草稿，就直接落成流程任务：

```bash
python -m app.main plan-workflow \
  --date 2026-04-19 \
  --account 技术小甜甜 \
  --title "新手如何快速做出第一个 CSDN 专栏" \
  --body-markdown "这里是正文草稿..." \
  --column "专栏增长" \
  --tag CSDN --tag 专栏 --tag 增长
```

如果你想一步到位，让系统同时生成业务 brief、流程任务、状态记录，就用：

```bash
python -m app.main execute-topic \
  --date 2026-04-19 \
  --account 技术小甜甜 \
  --title "新手如何快速做出第一个 CSDN 专栏" \
  --audience "刚开始做技术内容、想要稳定增长的人" \
  --column "专栏增长" \
  --angle "从0到1的最小闭环" \
  --value "把复杂流程拆成可执行步骤" \
  --cta "引导进入专栏/系列文章" \
  --body-markdown "这里是正文草稿..."
```

### 3.5 决定能不能发

发之前先过规则：

```bash
python -m app.main score-topic \
  --date 2026-04-19 \
  --title "新手如何快速做出第一个 CSDN 专栏" \
  --value-score 5 \
  --relevance-score 4 \
  --cost-score 4
```

草稿是否够发：

```bash
python -m app.main check-draft --title "新手如何快速做出第一个 CSDN 专栏" --body-markdown "这里是正文草稿..."
```

发布前检查：

```bash
python -m app.main check-publish --draft-exists --review-status approved --draft-url "https://editor.csdn.net/md?articleId=160311196" --owner 技术小甜甜
```

---

## 4. 每天怎么跑

如果你想把这套系统变成日常习惯，可以按下面顺序：

1. 先记今天看到的反馈、数据、竞品
2. 看 `review-intel` 的周/月结论
3. 更新 `plan-topic`，确定下一篇写什么
4. 先跑 `prepare-publish-day` 生成当天 4 个槽位的发文包
5. 用生成的 prompt/draft 模板写完正文，再跑 `plan-workflow` 或 `execute-topic`
6. 通过 `score-topic`、`check-draft`、`check-publish` 控制是否发布
7. 发布后先让人完成最终发布动作
8. 如果只是单次同步，跑 `sync-published-from-live`
9. 如果登录态还有效并且想直接从账号页面刷新，跑 `refresh-csdn-publish-facts`
10. 如果流量券管理页已有可用券，跑 `prepare-csdn-coupon-use` 做挂券执行、结果确认、“券是否仍被占用”的判断，以及一句话运营结论；是否还能挂，优先看第一张流量券是 `去使用` 还是 `已完成`
11. 最后再 `record-state` 或 `state-snapshot`

建议节奏：

- 日：收集输入、跑任务、看待审内容
- 周：做一次经营输入复盘
- 月：修战略、修专栏、修转化路径

---

## 5. 各层分别怎么看

### 第 0 层：经营输入与决策层

你要先看：

- 今天有哪些反馈
- 哪类题表现好
- 竞品在写什么
- 专栏点击和购买有没有变化

常用命令：

- `collect-intel`
- `review-intel`
- `log-feedback`
- `log-competitor`
- `log-sales`

### 第 1 层：战略层

看项目的大方向：

- 新号/旧号怎么分工
- 现在主推什么
- 哪些内容先不做

### 第 2 层：业务层

看一篇题值不值得写：

- 给谁看
- 为什么值
- 怎么导向专栏

常用命令：

- `plan-topic`
- `review-business`

### 第 3 层：流程层

看事情怎么推进：

- 选题 -> 草稿 -> 审核 -> 发布 -> 反馈

常用命令：

- `plan-workflow`
- `review-process`

### 第 4 层：规则层

看判断标准是否一致：

- 题该不该写
- 草稿能不能发
- 发布前是否满足条件

常用命令：

- `score-topic`
- `check-draft`
- `check-publish`
- `review-rules`

### 第 5 层：数据与状态层

看对象现在处于什么状态：

- topic
- draft
- review_package
- publish_task
- feedback
- daily_plan

常用命令：

- `record-state`
- `state-snapshot`

### 第 6 层：执行层

看代码层怎么一键串起来：

- `execute-topic`

它适合在你已经确定方向时直接执行整条链路。

---

## 6. 推荐决策顺序

如果你现在正卡在“这篇到底写不写、值不值得发”这种问题，按这个顺序来：

1. 看经营输入
2. 看业务 brief
3. 看流程任务
4. 看规则评分
5. 看状态
6. 最后再决定发不发

不要反过来。

---

## 7. 最适合你的使用方式

你这个项目最适合的方式不是“先做完大系统再用”，而是：

- 先把一个动作跑通
- 再把这个动作接入数据
- 再把数据接入决策
- 再把决策接入执行

所以建议你从这条主线开始：

`collect-intel -> review-intel -> plan-topic -> execute-topic -> score/check -> record-state`

如果你只想记住一句话：

1. 先收集输入，再做决定，再执行，再复盘。
2. 策略文件不接受手动填写；策略如有新增或修改，必须先用简报告知你，得到同意后才能正式落地。
