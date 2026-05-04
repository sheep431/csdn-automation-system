# 飞书 Bitable 同步方案（baseline 不再以本地为主）

> 目标：把“账号文章发布 baseline / 题库状态 / 发布事实”从本地 JSON 主导，逐步切到飞书多维表格（Bitable）作为人机协作主操作面。

## 1. 为什么选 Bitable 而不是普通表格

普通表格更适合二维展示，不适合长期维护下面这些结构化状态：
- 专栏生命周期
- candidate 状态流转
- 历史发布事实
- baseline 校准结果

Bitable 更适合：
- 字段化
- 过滤、分组、视图
- 人工批注
- 后续半自动同步

所以后续默认目标是：
- 飞书 Bitable = 主协作面
- 本地文件 = 过渡期备份 / 缓冲层

---

## 2. 当前已接通的技术底座

当前 Hermes 已接入官方 Feishu/Lark MCP：
- MCP 包：`@larksuiteoapi/lark-mcp`
- 配置位置：`~/.hermes/config.yaml`
- MCP server 名：`lark_bitable`

当前已验证可发现的 Bitable 相关 MCP 工具：
- `mcp_lark_bitable_bitable_v1_app_create`
- `mcp_lark_bitable_bitable_v1_appTable_create`
- `mcp_lark_bitable_bitable_v1_appTableField_list`
- `mcp_lark_bitable_bitable_v1_appTable_list`
- `mcp_lark_bitable_bitable_v1_appTableRecord_create`
- `mcp_lark_bitable_bitable_v1_appTableRecord_search`
- `mcp_lark_bitable_bitable_v1_appTableRecord_update`

当前使用 token 模式：
- `tenant_access_token`

说明：
- 这足够先做“应用 / 表 / 记录”的创建、查询、更新
- 后续如果需要以用户身份访问特定文档空间，再考虑切到 OAuth / user_access_token

---

## 3. 第一版结构：1 张主表 + 多视图

当前不再采用 3 张表拆分方案。

原因：
- 当前第一目标不是数据库规范化，而是方便用户与 Hermes 一起推进日常发文
- 需要先做到直观、顺手、容易人工操作
- 后续再根据真实使用频率决定是否拆表

所以第一版建议：
- 只建 1 张主表
- 用多视图解决“按专栏看”“只看已发布”“只看待发布”的问题

建议先建一个 Base App：
- 名称：`CSDN账号运营-Baseline中枢`

建议主表：
- 表名：`baseline_control`

### 3.1 主表语义

主表中每一行代表 1 条题目/文章记录。

它既可以表示：
- 已发布历史文章
- 当前候选题
- 已批准 / 已使用 / 已归档题

这样可以把：
- baseline
- candidate 状态机
- 发布事实
先统一收进 1 张表里。

---

## 4. 建议字段

### 必要字段
- `column_name`：文本
  - 专栏名
- `module_name`：文本
  - 属于哪个模块/板块
- `title`：长文本
  - 题目/文章标题
- `status`：单选
  - published
  - unused
  - approved
  - used
  - rejected
  - archived
- `role`：单选
  - 引流题
  - 信任题
  - 转化题
  - 其他
- `source`：单选
  - baseline_library
  - live_expansion
  - manual
  - full_capture
  - live_sync
- `candidate_id`：文本
  - 候选题唯一键；历史发布文章可为空
- `updated_at`：日期时间
- `notes`：长文本

### 推荐补充字段
- `account`：文本
  - 当前默认还是 `技术小甜甜`
- `title_key`：文本
  - 去重键，方便后续同步
- `published_date`：日期
  - 已发布文章可填，候选题可空
- `priority`：单选
  - 主推
  - 次推
  - 备用
- `lifecycle`：单选
  - active_revenue
  - active_traffic
  - incubating
  - paused
  - deprecated
  - 这个字段冗余但实用，便于在单表里直接过滤

---

## 5. 推荐视图

重点不是继续加表，而是把视图设计好。

### 视图 A：按专栏分组总览
- 按 `column_name` 分组
- 默认折叠/展开专栏
- 最接近日常“看每个专栏库存”的体验

### 视图 B：已发布 baseline
- 过滤：`status = published`
- 高亮已发布
- 按 `column_name` 分组
- 这就是历史 baseline 主视图

### 视图 C：待发布库存
- 过滤：`status in (unused, approved, used)`
- 按 `column_name` 分组
- 按 `priority` 或 `updated_at` 排序

### 视图 D：待人工判断
- 过滤：`status in (unused, approved)`
- 用于日常推进

### 视图 E：按模块看覆盖情况
- 按 `module_name` 分组
- 看哪些模块题太密、哪些模块题太薄

---

## 6. 为什么不建议“真的每个专栏一列”

虽然“每个专栏一列”视觉上直观，但第一版不建议真的做成纯横向排布表。

原因：
1. 专栏一多就会横向爆炸
2. 状态、模块、角色、更新时间等结构化信息很难优雅表达
3. 程序同步更适合“每行一条记录”，不适合往不同列里找格子插内容
4. 后续半自动化会更难做

所以更好的折中方案是：
- 逻辑上：1 张表，每行 1 条记录
- 展示上：通过分组视图，让它看起来像“每个专栏一块”

---

## 7. 本地到飞书的迁移策略

不要一步把本地文件全废掉，建议分 3 步。

### 阶段 A：飞书为主协作面，本地仍保留备份
先做：
- baseline / candidate / published facts 同步到这 1 张主表
- 人工开始优先在飞书看和改
- 本地 JSON 暂时继续保留，防止切换初期断档

### 阶段 B：状态更新优先写飞书，再回写本地
再做：
- candidate 状态动作优先打到 Bitable
- 本地改为镜像缓存 / 回写副本

### 阶段 C：baseline 以飞书为主，本地仅保留导出能力
最后才考虑：
- 本地不再作为 baseline 主存储
- 仅保留导出、备份、离线调试用途

---

## 8. 当前最推荐的下一步动作

### 第一步：先创建 Base App 和 1 张主表
- Base 名：`CSDN账号运营-Baseline中枢`
- 表名：`baseline_control`

### 第二步：先创建 4~5 个视图
让它先变得好看、直观、能人工推进。

### 第三步：只同步一小批数据验证
建议先同步：
- `AI实践-Dify专栏`
- `技术前沿每日速读`
- 少量 published
- 少量 pending

验证：
- 你自己看/改是否舒服
- 我和你协作是否更顺手
- 后续状态更新是否容易

---

## 9. 风险与注意点

### 9.1 当前 tenant_access_token 可能受应用权限限制
虽然 MCP 已接通，但真正写 Bitable 还取决于：
- 飞书应用是否开了对应 Bitable 权限
- 应用是否有权限访问目标空间 / 文档位置

### 9.2 当前更适合先建新的专用 Base
比起直接写进已有杂乱空间，更建议：
- 新建一个专用 Base
- 专门给 CSDN baseline / candidate / published facts 使用

### 9.3 先别急着全量历史迁移
先验证结构和操作体验，再迁全量历史。

---

## 10. 一句话结论

当前推荐方向不是：
- 继续把 baseline 只存本地 JSON
- 也不是一上来就拆 3 张表

而是：
- 先用 1 张 Bitable 主表 + 多视图
- 让飞书先变成最顺手的协作面
- 让本地系统逐步退到“同步、备份、生成、校准”的后台角色
