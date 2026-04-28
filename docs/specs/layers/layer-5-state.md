# CSDN 自主运营系统 - 第 5 层：数据与状态层规范

> 这一层只回答：系统里有哪些对象、这些对象怎么存、状态怎么流转、历史怎么追踪。

## 1. 这一层的职责

数据与状态层负责把前面几层的结果对象化。

只要是系统要追踪、比较、回溯、过滤的东西，都应该在这一层定义清楚。

## 2. 核心对象

建议至少定义以下对象：

- Account：账号
- Topic：选题
- Draft：草稿
- ReviewPackage：审核包
- PublishTask：发布任务
- Feedback：反馈
- DailyPlan：日计划

## 3. 对象最小字段

### 3.1 Account

- account_id
- account_name
- role
- status
- notes

### 3.2 Topic

- topic_id
- title
- account_name
- column_name
- source
- value_score
- relevance_score
- cost_score
- priority_bucket
- status
- notes

### 3.3 Draft

- draft_id
- topic_id
- title
- body
- tags
- account_name
- column_name
- source
- status
- draft_url
- notes

### 3.4 ReviewPackage

- package_id
- draft_id
- title
- account_name
- draft_url
- review_message
- status
- sent_at

### 3.5 PublishTask

- publish_task_id
- draft_id
- status
- published_at
- result
- notes

### 3.6 Feedback

- feedback_id
- draft_id
- source
- comment
- category
- created_at

### 3.7 DailyPlan

- plan_id
- plan_date
- account_name
- topic_ids
- draft_ids
- status

## 4. 状态设计

### 4.1 Topic 状态

- candidate
- scored
- pooled
- selected
- drafted
- archived

### 4.2 Draft 状态

- pending
- generated
- waiting_review
- approved
- needs_revision
- published
- archived

### 4.3 ReviewPackage 状态

- created
- sent
- read
- responded
- closed

### 4.4 PublishTask 状态

- pending
- running
- success
- failed
- skipped

### 4.5 Feedback 状态

- collected
- normalized
- applied

## 5. 状态流转原则

### 5.1 单向优先

状态尽量单向前进，避免同一对象频繁乱跳。

### 5.2 可追踪

任何状态变化都要保留时间和原因。

### 5.3 可恢复

如果中途失败，应该能从历史记录判断下一步怎么补救。

### 5.4 不丢上下文

退回修改或发布失败时，要保留原始草稿和审核信息。

## 6. 历史记录要求

每个对象至少要保留：

- 主键
- 当前状态
- 创建时间
- 更新时间
- 关联对象 ID
- 简要备注

## 7. 当前落地方式

当前代码里已经有一个通用状态层：

- 状态记录最新值保存在 `data/state/ledger/<object_type>/<object_id>.json`
- 状态变更历史追加在 `data/state/history/<object_type>/<object_id>.jsonl`
- 统一快照保存在 `data/state/snapshots/YYYY-MM-DD.md` 和 `.json`

支持的状态对象类型：

- `account`
- `topic`
- `draft`
- `review_package`
- `publish_task`
- `feedback`
- `daily_plan`

## 8. 当前落地接口

这一层已经开始向代码层落地，当前可用接口是：

- `record-state`
  - 用来记录某个对象的最新状态
  - 支持附带属性、来源路径、备注

- `state-snapshot`
  - 用来查看当前状态层的整体快照
  - 会汇总对象数量和状态分布

这一步的作用是把“谁是什么状态、状态改过几次、为什么改”统一保存下来，方便后续复盘和自动化决策。

## 9. 与前面各层的关系

- 战略层决定账号和方向
- 业务层决定内容和账号适配
- 流程层决定对象如何流转
- 规则层决定判断标准
- 数据与状态层决定怎么存、怎么查、怎么追踪

## 10. 下一层接口

数据与状态层完成后，下一层要回答：

- 这些对象对应哪些命令
- 哪些命令创建它们
- 哪些命令查询它们
- 哪些命令改变它们的状态

也就是进入第 6 层：执行层。
