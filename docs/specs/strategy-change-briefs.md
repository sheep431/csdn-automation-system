# 策略变更简报与审批规则

> 目标：把“策略变化要先告知、你同意后才能正式落地”这件事，固定成标准格式和工程流程。

## 1. 核心规则

- 系统可以推导策略变更建议
- 但不能直接把建议写成正式策略输出
- 任何策略新增、删减、改权重、改方向，都必须先形成一份“策略变更简报”
- 用户明确同意后，才能生成或覆盖正式 strategy output

## 2. 标准简报格式

每份策略变更简报至少要包含：
- 日期
- 账号
- 当前阶段目标
- 目标专栏
- 当前策略摘要
- 建议策略摘要
- 为什么建议改
- 预计影响
- 风险与注意点
- 来源信号
- 当前状态（默认 `pending_approval`）

## 3. 数据落点

策略提案：
- `data/business/strategy_proposals/`

正式策略：
- `data/business/strategy_outputs/`

含义：
- proposal 是待审批版本
- output 是批准后的正式版本

## 4. 当前已接入命令

生成策略变更简报：
```bash
python -m app.main propose-strategy-change \
  --date 2026-04-20 \
  --account 技术小甜甜 \
  --stage-goal "提高专栏转化" \
  --target-column "CSDN专栏增长" \
  --current-summary "当前以引流题为主" \
  --proposed-summary "增加免费文到专栏的桥接题比例" \
  --reason "最近转化桥接不足" \
  --expected-effect "增加转化型题目" \
  --risk "可能影响阅读体验" \
  --source-signal "sales 周报"
```

从现有 intel / columns / strategy outputs 自动归纳提案：
```bash
python -m app.main auto-propose-strategy-change \
  --date 2026-04-21 \
  --account 技术小甜甜 \
  --stage-goal "提升专栏转化" \
  --target-column "CSDN专栏增长"
```

批准后正式落地：
```bash
python -m app.main approve-strategy-change \
  --proposal-path data/business/strategy_proposals/xxx.json
```

## 5. 运行规则

后续自动流程应遵守：
1. 先读取现有正式 strategy output
2. 如果发现新输入足以触发策略变化，可以手动提案，也可以自动归纳 proposal
3. 但都只能生成 proposal，不能直接落正式策略
4. 必须先把 proposal 简报发给用户
5. 只有用户明确同意，才能执行 approve 并写正式 strategy output

## 6. 和选题流程的关系

- proposal 不直接约束选题，只是待审批建议
- 正式 strategy output 才能作为选题标准输入
- 这样可以保证：
  - 自动系统能持续学习
  - 但策略方向不会绕过用户决策权
