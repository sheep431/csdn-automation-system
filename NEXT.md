# NEXT — 当前续做入口

当前项目
- 账号：技术小甜甜
- 主目录：`/mnt/e/个人项目/CSDN账号运营/automation-system`
- 当前主入口：topic-library dashboard
- 新边界：自建系统负责“经营中枢/决策控制台”，CSDN 官方 AI 数字营销平台负责平台内创作、分发、营销与官方数据能力

一、现在已经稳定的能力
- 基于 full capture 构建 per-column baseline assets
- 基于 full capture 构建 per-column topic libraries
- library-first 选题：优先消耗未使用库存，再补新候选
- candidate 状态流转：unused / approved / used / published / rejected / archived
- dashboard 显示：专栏状态、已发布数、待发布数、展开查看题目列表
- dashboard 已有“校准 baseline”按钮
- 校准 baseline 时保留已有 candidate status / notes

二、当前推荐打开顺序
1. 打开 dashboard：`http://127.0.0.1:8787/`
2. 看各专栏 published / pending 是否合理
3. 若当前发布事实与 baseline 偏差大：点击“校准 baseline”
4. 若 baseline 无偏差：继续沿用当前 baseline 做增量推进
5. 如果进入平台内写作/分发/营销动作，优先转去 CSDN 官方 AI 数字营销平台完成

三、现在最重要的下一步
优先级 1：先暂停继续扩 dashboard / 平台能力
- 当前不急着把系统继续做成完整操作台
- 先用人工方式走顺“日常发文流程”
- 目标：先形成稳定固定路线，再逐步半自动、全自动

优先级 2：把当前已有积累当作后台能力储备
- baseline / topic library / candidate 状态流转 先保留
- dashboard 暂时保留为观察入口，不继续重投入扩张
- 等日常流程稳定后，再决定哪些环节最值得自动化

优先级 3：探索“官方平台优势 + Hermes 生成优势”的组合打法
- 不直接照搬官方平台给出的有限大纲选项
- 用官方平台做平台内效率动作
- 用 Hermes 做差异化选题、角度、结构和内容生成

四、当前不要跑偏的点
- 现在先做 CSDN 项目本身，不要切去 Hermes 主仓库改 /project 内核
- 不再把当前项目目标定义为“再造一个完整内容营销平台”
- 当前目标是把这套系统做成 CSDN 官方平台之上的本地经营中枢

五、恢复时要记住的事实
- Dify 专栏历史存量很多，dashboard 的 published 不能只看 topic_usage_ledger
- published = existing_topics 历史基线 + 新同步到 ledger 的 published 条目（去重）
- 不校准时：沿用 baseline，继续走状态增量更新
- 校准时：按当前发布事实刷新 baseline，但保留 candidate 状态
- 官方平台上线后，自建优先保留经营逻辑，不再重做平台通用创作/分发/营销能力

六、如果要重新启动面板
```bash
cd '/mnt/e/个人项目/CSDN账号运营/automation-system'
PYTHONPATH=. .venv/bin/python -m app.main serve-topic-library-dashboard \
  --account 技术小甜甜 \
  --profile new-main \
  --host 127.0.0.1 \
  --port 8787
```

七、进入下一轮实现时的首选任务
“继续给 dashboard 增加题目级操作按钮，并把 approved / rejected / used / published 直接接到现有状态文件更新逻辑；不要再扩做完整创作/分发平台。”
