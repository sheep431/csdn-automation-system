# CSDN 自主运营系统规范索引

> 建议按从上到下的顺序阅读和落地。

## 阅读顺序

1. `csdn-autonomous-ops-spec.md`
   - 顶层总规范

2. `csdn-autonomous-ops-roadmap.md`
   - 7 层路线图

3. `csdn-autonomous-ops-user-guide.md`
   - 系统使用手册：怎么参与决策、怎么下命令、怎么复盘

4. `topic-batch-schedule.md`
   - 选题批次自动运行方案：固定节奏、审阅回路、学习闭环

5. `topic-feedback-learning-loop.md`
   - 选题反馈落库与学习闭环规范：用户修改如何落库、修订、沉淀为长期规则

6. `topic-batch-format.md`
   - 选题批次文件格式规范：cron 必须产出统一 JSON/Markdown，供反馈闭环直接消费

7. `topic-input-layers.md`
   - 选题标准输入层：策略输出与专栏资产/空缺图

8. `strategy-change-briefs.md`
   - 策略变更简报与审批规则：先提案、后批准、再正式落地

9. `layers/layer-0-intel.md`
   - 经营输入与决策层

10. `layers/layer-0-intel-ops.md`
   - 经营输入与决策落地

11. `layers/layer-1-strategy.md`
   - 战略层

12. `layers/layer-2-business.md`
   - 业务层

13. `layers/layer-3-process.md`
   - 流程层

14. `layers/layer-4-rules.md`
   - 规则层

15. `layers/layer-5-state.md`
   - 数据与状态层

16. `layers/layer-6-exec.md`
   - 执行层

17. `boundary-phase-1.md`
   - 当前系统一期边界：纳入范围 / 暂不纳入范围 / 完成标准

18. `phase-1-operations-checklist.md`
   - 一期操作清单 / 验收清单：当前 artifacts、常用 CLI、验收标准

19. `phase-1-validation-conclusion.md`
   - 一期验证结论：当前已经验证的能力、可相信的结论、尚未验证的部分、是否可开始实际使用

20. `layers/layer-0-intel-template.md`
   - 经营输入日/周/月采集模板

## 当前状态

- 顶层总规范：已完成
- 7 层路线图：已完成
- 第 0 层经营输入与决策层：已完成
- 第 1 层战略层：已完成
- 第 2 层业务层：已完成
- 第 3 层流程层：已完成
- 第 4 层规则层：已完成
- 第 5 层数据与状态层：已完成
- 第 6 层执行层：已完成

## 后续落地建议

下一步可以把这些规范继续映射到 automation-system 的具体实现，包括：

- 经营输入采集与归档
- 自动生成周报/月报
- 选题池数据结构
- 草稿对象模型
- 审核包格式
- 反馈记录模型
- 新 CLI 命令（collect-intel / review-intel / log-feedback / log-competitor / log-sales / build-strategy-output / build-column-asset / propose-strategy-change / auto-propose-strategy-change / approve-strategy-change / plan-topic / review-business / save-topic-batch / apply-topic-feedback / mark-topic-used / topic-usage-report / plan-workflow / review-process / score-topic / check-draft / check-publish / review-rules / record-state / state-snapshot / set-column-lifecycle / write-daily-column-allocation / column-portfolio-review / execute-topic）
- 更清晰的状态流转
