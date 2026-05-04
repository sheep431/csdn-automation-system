# session-context — CSDN 项目当前进度快照

更新时间
- 以当前工作区真实文件状态为准；本文件用于“快速恢复脑内上下文”

当前阶段
- 一期系统已可试用
- 当前重点不是继续抽象架构，也不是继续重做平台侧创作/营销能力
- 当前也先不继续重投入扩 dashboard 操作台
- 当前重点改为：先和用户一起走顺日常发文流程，沉淀固定路线，再逐步半自动、全自动
- 同时探索“官方平台优势 + Hermes 生成优势”的差异化组合打法

当前已经完成的产品化收口
1. 历史基线 -> 专栏资产 -> topic library -> library-first 选题，主链路已跑通
2. candidate_id 与状态流转已接通
3. dashboard 已改成简化版：
   - 看所有专栏
   - 看专栏状态
   - 看已发布数量
   - 看待发布数量
   - 展开看 published / pending 题目
4. published 统计口径已修正
   - 不再只依赖 topic_usage_ledger
   - 改为 existing_topics + published ledger merge 去重
5. dashboard 已接入“校准 baseline”按钮
   - 可基于当前完整账号事实重建 baseline
   - 并保留已有 candidate 状态与 notes
6. 项目边界已更新
   - 自建系统 = 经营中枢 / 决策控制台
   - 官方平台 = 平台内创作、分发、营销、官方数据能力

当前系统入口
- 页面：`http://127.0.0.1:8787/`
- 健康检查：`http://127.0.0.1:8787/health`
- 静态文件：`docs/specs/topic-library-dashboard.html`
- 新边界文档：`docs/specs/csdn-official-platform-role-split.md`

当前最重要的数据理解
- `data/intel/accounts/*_full.json`：当前完整账号发布事实
- `data/business/topic_libraries/*.json`：每个专栏的 baseline + candidate 状态
- `data/business/topic_usage/topic_usage_ledger.json`：新流程追踪到的增量使用/发布状态

当前正确的业务语义
- 不点校准：继续沿用现有 baseline，并通过 publish/sync 动作更新 candidate 状态
- 点校准：以当前发布事实刷新 baseline，但不丢失人工已推进的 candidate 状态
- 平台内通用创作/分发/营销能力，优先交给 CSDN 官方平台，不再作为当前自建主方向

下一步最值得做的事情
- 先和用户一起走顺一轮轮真实日常发文流程
- 把流程里稳定、重复、低风险的环节找出来
- 再决定哪些步骤最值得半自动化
- 保留 dashboard / baseline / topic library 作为后台能力储备
- 用 Hermes 负责差异化选题、结构、内容生成，用官方平台负责平台内效率动作
- 飞书 Bitable 当前改为优先采用“1 张主表 + 多视图”的方式承接 baseline / candidate / published 协作面

不要混淆
- 当前是在做 CSDN账号运营/automation-system 项目
- 不是在做 Hermes 主仓库的 /project 命令内核改造
- 也不是在重做一个完整 CSDN 内容营销平台
