# 2026-04-21 选题修正依据

## 为什么重做
上一版 4 篇题目没有充分使用当前项目里已经存在的专栏、文章、题库和历史计划数据，确实不满足“延续性 / 经营性 / 去重复”的要求。

## 本次实际参考的数据

### 老号侧
1. `content-ops/csdn_today_plan_latest.md`
- 明确要求：
  - 选题必须与历史题目有延续或补充关系
  - 引流位优先使用《技术前沿每日速读》承接热点
  - 深度位围绕 Dify / AI 落地主线继续扩展

2. `content-ops/csdn_topic_planner_latest.xlsx`
- `SUMMARY` / `ANALYSIS` 显示：
  - 《技术前沿每日速读》 = free_lead，最近 30 天 0 篇，距上次更新 999 天
  - 《AI实践-Dify专栏》 = paid / flagship，最近 30 天 6 篇
  - 《生成式AI实战笔记》高频关键词包含 `ollama / openwebui / agent`

3. `content-ops/老号/AI前沿工坊｜从理论到实战的智能时代手册/new_ai_column_topics.txt`
- 已维护后续 AI 深度题库，说明老号深度线应继续沿“本地部署 / RAG / 推理 / Agent”主线推进，而不是跳到无关 CSDN 运营泛题。

### 新号侧
1. `content-ops/新号/长期单项分表.xlsx`
- `CSDN主战场` 页明确列出：
  - 引流免费：`技术前沿每日速读`
  - 旗舰：`AI实践-Dify专栏`
  - 次席：`生成式AI实战笔记`
- 同页已经写了 Dify 后续待做题：
  - `[Dify实战] 多轮对话状态管理：上下文保持与槽位填充`
  - `[Dify实战]长文档智能摘要：多层级提炼与关键信息抽取`
  - `[RAG实战] Dify 多日期提问召回不全？一次彻底解决“检索被稀释”的工程方案（含完整实现思路）`

2. `content-ops/新号/dify专栏续/post/dify_titles.txt`
3. `content-ops/新号/dify专栏续/project/dify_shizhan_no_resource.csv`
- 已用来排除已发 Dify 标题，避免直接重复。
- 最近已发内容主要是业务案例流：
  - 发布自动化
  - 会议纪要
  - 数据报警
  - A/B 结论
  - 技术方案评审
  - 产品手册
  - 品牌舆情
  - OKR / 法务 / OA / 采购 / 招聘等
- 所以下一批更合理的是“机制层 / RAG 工程层 / 多轮状态层”的延续题，而不是跳回泛化的 CSDN 写作题。

## 修正后的 4 篇

### 老号 踏雪无痕老爷子
1. `[AI速读] 这周最值得拆的 3 个 Dify 场景：发布自动化、会议纪要、数据报警`
- 作用：恢复 `技术前沿每日速读` 这个 free_lead 入口位
- 来源：`csdn_today_plan_latest.md` 明确建议用引流位承接 Dify 热点并导流到旗舰专栏

2. `【AI】vLLM + OpenWebUI 组合部署：高吞吐推理与界面一体化实战`
- 作用：承接老号 AI 深度线，从已有 `ollama/openwebui` 内容往更工程化部署升级
- 来源：`new_ai_column_topics.txt` + `csdn_topic_planner_latest.xlsx`

### 新号 技术小甜甜
3. `[Dify实战] 多轮对话状态管理：上下文保持与槽位填充`
- 作用：承接 Dify 主专栏，补当前内容里相对缺失的“状态设计”深度题
- 来源：`长期单项分表.xlsx -> CSDN主战场`

4. `[RAG实战] Dify 多日期提问召回不全？一次彻底解决“检索被稀释”的工程方案（含完整实现思路）`
- 作用：承接 Dify 专栏最近的 RAG / Agent 关键词，做高价值实操进阶题
- 来源：`长期单项分表.xlsx -> CSDN主战场`，并已与 `dify_titles.txt` / `dify_shizhan_no_resource.csv` 做标题避重

## 已同步更新的位置
- `automation-system/data/daily_publish_inputs/2026-04-21_publish-plan.json`

下一步应直接基于这个修正版重新生成当日发文包，再写正文。
