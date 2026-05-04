# CSDN 自主运营系统规范索引

> 建议按从上到下的顺序阅读和落地。

## 恢复当前项目时先看

1. 项目根目录 `README.md`
   - 当前项目用途、常用命令、dashboard 入口
2. 项目根目录 `NEXT.md`
   - 当前阶段、下一步优先级、不要跑偏的点
3. 项目根目录 `session-context.md`
   - 当前实现进度快照、当前正确业务语义、下一步收口方向

再继续阅读下面的系统规范。

## 阅读顺序

1. `csdn-autonomous-ops-spec.md`
   - 顶层总规范

2. `csdn-autonomous-ops-roadmap.md`
   - 7 层路线图

3. `csdn-autonomous-ops-user-guide.md`
   - 系统使用手册：怎么参与决策、怎么下命令、怎么复盘

4. `topic-publish-analysis-three-flow.md`
   - 三流程联动规范：把选题、发文、运营分析拆成 3 个独立但互相喂数的闭环

5. `topic-batch-schedule.md`
   - 选题批次自动运行方案：固定节奏、审阅回路、学习闭环

6. `topic-feedback-learning-loop.md`
   - 选题反馈落库与学习闭环规范：用户修改如何落库、修订、沉淀为长期规则

7. `topic-batch-format.md`
   - 选题批次文件格式规范：cron 必须产出统一 JSON/Markdown，供反馈闭环直接消费

8. `topic-input-layers.md`
   - 选题标准输入层：策略输出与专栏资产/空缺图

9. `strategy-change-briefs.md`
   - 策略变更简报与审批规则：先提案、后批准、再正式落地

10. `layers/layer-0-intel.md`
   - 经营输入与决策层

11. `layers/layer-0-intel-ops.md`
   - 经营输入与决策落地

12. `layers/layer-1-strategy.md`
   - 战略层

13. `layers/layer-2-business.md`
   - 业务层

14. `layers/layer-3-process.md`
   - 流程层

15. `layers/layer-4-rules.md`
   - 规则层

16. `layers/layer-5-state.md`
   - 数据与状态层

17. `layers/layer-6-exec.md`
   - 执行层

18. `boundary-phase-1.md`
   - 当前系统一期边界：纳入范围 / 暂不纳入范围 / 完成标准

19. `phase-1-operations-checklist.md`
   - 一期操作清单 / 验收清单：当前 artifacts、常用 CLI、验收标准

20. `phase-1-validation-conclusion.md`
   - 一期验证结论：当前已经验证的能力、可相信的结论、尚未验证的部分、是否可开始实际使用

21. `csdn-official-platform-role-split.md`
   - 接入 CSDN 官方 AI 数字营销平台后的新边界：哪些能力停止自建，哪些继续保留为经营中枢

22. `feishu-bitable-baseline-sync-design.md`
   - baseline / candidate / published facts 迁移到飞书 Bitable 的结构设计与迁移策略

23. `layers/layer-0-intel-template.md`
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
