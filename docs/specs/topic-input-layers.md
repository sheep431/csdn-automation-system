# 选题标准输入层：策略输出与专栏资产

> 目标：把“自动进化策略流程输出”和“已有专栏/专栏空缺”都变成选题流程的标准输入，而不是散落在线索里的临时参考。

## 1. 大结构

固定关系：
- 自动进化策略流程输出 -> 选题流程输入之一
- 专栏资产/空缺图 -> 选题流程输入之一
- 选题流程输出 -> 发布/执行流程输入

也就是说，选题不是直接从零开始拍脑袋生成，而是优先读取三类中间产物：
1. live account snapshot
2. strategy output
3. column inventory / gap map

## 2. 实时账号事实层

目录：
- `data/intel/accounts/`

作用：
- 把账号当前页面真实采集到的专栏、文章标题、列表页信息沉淀成标准化快照
- 让当天选题先建立在“账号里现在真实有什么、刚发了什么、主打什么”之上，而不是旧文档推测
- 为发布后的 `published` 回写提供事实依据

当前已接入命令：
- `capture-csdn-live`
- `import-csdn-live-snapshot`
- `sync-published-from-live`
- `refresh-csdn-publish-facts`
- `plan-topic-batch-from-live`

推荐使用方式：

```bash
python -m app.main capture-csdn-live \
  --date 2026-04-21 \
  --account 技术小甜甜 \
  --profile new-main

# 如果登录态仍有效，发布后可直接自动刷新已发布事实：
python -m app.main refresh-csdn-publish-facts \
  --date 2026-04-21 \
  --account 技术小甜甜 \
  --profile new-main
```

会产出：
- `data/intel/accounts/YYYY-MM-DD_<account>_live.json`
- `data/intel/accounts/YYYY-MM-DD_<account>_live.md`
- `data/intel/accounts/YYYY-MM-DD_<account>_publish-sync.md`

## 3. 策略输出层

目录：
- `data/business/strategy_outputs/`

作用：
- 把截至当前时点的反馈、经营判断、竞品启发、转化偏好，整理成一份本轮选题策略文件

重要规则：
- 用户不接受手动填写策略文件
- 策略输出应尽量由系统根据已有经营输入、反馈、专栏资产、竞品参考自动归纳生成
- 但系统不能擅自把“新增或修改后的策略”直接落地为正式版本
- 只要策略有新增、删减、改权重、改方向，必须先生成简报告知用户
- 只有在用户明确同意后，策略修改才能正式写入或覆盖现有策略输出

当前已接入命令：
- `build-strategy-output`

这个命令当前保留为工程接口，但在实际工作流里应遵守上面的审批规则：
- 先给用户看策略简报
- 用户同意后再落策略文件

它会产出：
- `.json`
- `.md`

## 3. 专栏资产/空缺层

目录：
- `data/business/columns/`

作用：
- 记录某个专栏当前已有题目、还缺哪些题、希望承担什么角色、可参考哪些同类专栏

当前已接入命令：
- `build-column-asset`

示例：

```bash
python -m app.main build-column-asset \
  --date 2026-04-20 \
  --account 技术小甜甜 \
  --column "CSDN专栏增长" \
  --goal "补齐从起号到转化的主题缺口" \
  --existing-topic "起号最小闭环" \
  --gap-topic "免费文如何自然导向专栏" \
  --topic-role "引流题" \
  --topic-role "转化题" \
  --competitor-reference "某同类专栏把案例和CTA捆绑"
```

它会产出：
- `.json`
- `.md`

## 5. 选题流程如何读取它们

`plan-topic` 现在已经支持显式附带：
- `--strategy-path`
- `--column-asset-path`

示例：

```bash
python -m app.main plan-topic \
  --date 2026-04-20 \
  --account 技术小甜甜 \
  --title "免费文如何自然引导用户进入专栏" \
  --audience "想提高专栏转化的作者" \
  --column "CSDN专栏增长" \
  --angle "从免费文承接到专栏页设计" \
  --value "补齐转化桥接空缺" \
  --cta "引导进入专栏看完整设计" \
  --strategy-path data/business/strategy_outputs/xxx.md \
  --column-asset-path data/business/columns/yyy.md
```

这样生成的选题 brief 里，会明确记下：
- 这条题用了哪份策略输出
- 这条题用了哪份专栏资产/空缺图

## 5. 同类专栏学习如何接进来

当前规则是：
- 同类专栏/竞品启发先沉淀到 strategy output
- 同类专栏结构差异也可以沉淀到 column asset
- 后续 topic batch 生成时，必须优先读取这两类中间产物，而不是只看零散反馈

所以“找同类专栏去学习进化”这件事，现在开始有正式落点：
- `competitor_insight`
- `competitor_reference`

## 6. 下一步接线原则

后续 cron/topic batch 应该优先读取：
1. 最近的 live account snapshot
2. 最近的 strategy output
3. 最近的 column asset
4. learning rules
5. topic usage ledger
6. intel/business/process 最新记录

同时增加一条审批规则：
- cron 和自动流程可以读取已有 strategy output
- 也可以基于新输入推导“策略变更建议”
- 但不能未经用户同意直接覆写正式 strategy output
- 一旦发现策略需要新增或修改，应先向用户输出简报，等待用户批准后再正式落地

这样选题流程才真正成为：
- 由策略约束
- 由专栏空缺驱动
- 由反馈学习优化
- 由 usage ledger 避免重复
