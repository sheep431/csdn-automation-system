# 选题批次文件格式规范

> 目标：把 cron 产出的 topic batch 固定成统一结构，确保后续的人工审阅、反馈落库、修订批次、学习规则都能无缝衔接。

## 1. 标准输出文件

每次选题批次必须同时产出两份文件：

- `data/business/topic_batches/topic-batch_YYYYMMDDHHMMSS.json`
- `data/business/topic_batches/topic-batch_YYYYMMDDHHMMSS.md`

说明：
- `.json` 是机器主读取格式
- `.md` 是人工审阅格式
- 两者必须表达同一批内容

## 2. 顶层 JSON 结构

必须包含这些字段：

- `account`
- `generated_at`
- `batch_strategy`
- `writing_order`
- `topics`

可选字段：
- `changes_from_previous`
- `source_signals`
- `notes`

## 3. topics 列表规则

- 必须刚好 8 个
- 前 6 个默认是主推
- 后 2 个默认是备用
- 每个 topic 都要有唯一编号

每个 topic 必须包含：
- `number`
- `title`
- `audience`
- `account`
- `column`
- `reason`
- `expected_value`
- `why_now`
- `cta`
- `role`
- `risk`
- `priority`

其中：
- `role` 只能是：`引流题` / `信任题` / `转化题`
- `priority` 只能是：`主推` / `备用`

## 4. Markdown 展示要求

`.md` 文件至少要包含：
- 批次标题
- 账号
- 生成时间
- 批次策略
- 建议写作顺序
- 与上一批的变化（如果有）
- 每个 topic 的完整摘要

每个 topic 在 markdown 中必须展示：
- 标题
- 优先级
- 目标读者
- 账号
- 专栏/系列
- 选择理由
- 预期价值
- 为什么现在写
- CTA
- 题型角色
- 风险/不确定点

## 5. 为什么要固定这个格式

固定格式之后，系统才能稳定完成下面这条链：

- cron 生成批次
- 用户审阅批次
- `apply-topic-feedback` 读取原始批次
- 系统生成 revised batch
- 系统更新 learning rules
- 下一批显式说明学到了什么

## 6. 当前已接入命令

现在已经有一个最小命令用于校验并落库 topic batch：

```bash
python -m app.main save-topic-batch \
  --date 2026-04-20 \
  --batch-json-path /path/to/batch.json
```

这个命令会：
- 校验 JSON 结构是否符合规范
- 自动生成标准 `.json`
- 自动生成标准 `.md`
- 统一保存到 `data/business/topic_batches/`

## 7. 与 cron 的衔接规则

后续 cron 生成 topic batch 时，应该按这个流程：

1. 先读取 `data/business/topic_usage/topic_usage_ledger.json`（如果存在）
2. 把状态为 `approved` / `used` / `published` 的选题视为已消费题
3. 对这些已消费题做硬去重：
   - 同标题直接禁止再次生成
   - 高相似切角默认降权，除非明确说明是升级版/补充版
4. 再生成一份符合规范的 JSON
5. 再调用 `save-topic-batch`
6. 让系统产出标准 JSON + Markdown
7. 再把批次内容发回当前对话给用户审阅

这样后续用户一旦修改，就能直接调用 `apply-topic-feedback`，不需要额外格式转换。
