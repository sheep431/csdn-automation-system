# CSDN 自主运营系统 - 第 6 层：执行层规范

> 这一层只回答：系统具体如何落到 automation-system 里的命令、文件、脚本和数据目录。

## 1. 这一层的职责

执行层把前五层的设计映射成真实可运行的代码和命令。

这一层不重新定义战略、业务或流程，只负责把上层约束落到工程实现。

## 2. 现有执行入口

当前 automation-system 已有的主要入口包括：

- `app/main.py`
- `app/config.py`
- `app/ops/daily_board.py`
- `app/task_queue/review_gate.py`
- `app/mvp/review_flow.py`
- `app/runner/execution_runner.py`
- `app/store/task_store.py`
- `app/publishers/csdn_publisher.py`
- `app/browser/session_manager.py`
- `app/business/ops.py`
- `app/process/ops.py`
- `app/rules/ops.py`
- `app/state/ops.py`
- `app/execution/ops.py`

## 3. 当前命令层

现有 CLI 已覆盖以下执行动作：

- `init`
- `run`
- `run-batch`
- `enqueue-markdown`
- `plan-day`
- `prepare-sample-review`
- `status`
- `switch-account`
- `plan-topic`
- `review-business`
- `plan-workflow`
- `review-process`
- `score-topic`
- `check-draft`
- `check-publish`
- `review-rules`
- `record-state`
- `state-snapshot`
- `execute-topic`

## 4. 命令与层级映射

### 4.1 战略层映射

战略层主要落到：
- 项目说明文档
- 账号角色配置
- 目录约定

### 4.2 业务层映射

业务层主要落到：
- 选题池文件
- 专栏策略文件
- 账号适配规则
- 草稿生成参数

### 4.3 流程层映射

流程层主要落到：
- 任务创建
- 审核包导出
- 审核状态流转
- 发布任务执行

### 4.4 规则层映射

规则层主要落到：
- 选题打分函数
- 审核门禁
- 发布前检查
- 异常分流

### 4.5 数据层映射

数据层主要落到：
- 数据模型
- 状态枚举
- 任务存储
- 审核包存储
- 运行结果记录
- 状态 ledger / history / snapshot

## 5. 目录建议

执行层继续沿用并细分以下目录：

- `automation-system/app/`：代码
- `automation-system/tests/`：测试
- `automation-system/data/`：运行数据
- `automation-system/docs/`：规范和说明

其中：
- `data/tasks/` 用于任务文件
- `data/review_packages/` 用于审核包
- `data/daily_plans/` 用于每日发文板
- `data/logs/` 用于日志
- `data/business/` 用于业务决策
- `data/process/` 用于流程执行
- `data/rules/` 用于规则判断
- `data/state/` 用于状态记录

## 6. 执行层的实现顺序

建议按以下顺序落地：

1. 先补齐层级文档与规则文档
2. 再把核心数据模型整理完整
3. 再把选题池、流程和状态接入 CLI
4. 再把审核包和反馈流转完善
5. 最后再优化发布和统计

## 7. 与现有代码的衔接点

### 7.1 `app/config.py`

负责：
- 数据目录
- 浏览器目录
- 默认路径
- 全局常量

### 7.2 `app/main.py`

负责：
- CLI 命令入口
- 任务触发
- 各流程命令编排

### 7.3 `app/store/task_store.py`

负责：
- 任务记录
- idempotency
- 最新结果查询

### 7.4 `app/runner/execution_runner.py`

负责：
- 任务执行
- 流程推进
- 结果回写

### 7.5 `app/publishers/csdn_publisher.py`

负责：
- CSDN 编辑器操作
- 草稿/发布动作

### 7.6 `app/browser/session_manager.py`

负责：
- 浏览器 profile
- 登录上下文
- 会话保存

### 7.7 `app/execution/ops.py`

负责：
- 把业务、流程、状态串成一条执行链
- 输出执行层统一结果
- 生成最终状态快照

## 8. 当前新增执行层接口

### 8.1 `execute-topic`

这是当前最完整的执行层入口。

它把以下动作串起来：
- 生成业务层选题决策
- 生成流程层执行单
- 生成待审任务
- 写入 topic / draft / review_package 状态
- 输出统一状态快照

它的意义是把“我想写一篇文章”变成“一套可追踪、可回放、可继续自动化的执行产物”。

## 9. 后续可新增命令方向

如果后面继续增强执行层，可能会新增：

- 选题池管理命令
- 草稿生成命令
- 审核包发送命令
- 反馈录入命令
- 复盘统计命令

## 10. 执行层输出

这一层完成后，必须形成：

- 命令与功能映射表
- 数据目录约定
- 代码模块职责图
- 后续新增命令清单

## 11. 最终落地状态

当六层都完成后，整个系统应该满足：

- 能解释为什么写
- 能解释写给谁看
- 能解释怎么流转
- 能解释什么算通过
- 能记录全部状态
- 能通过命令稳定执行

这时它才算真正从“想法”变成“自主运营系统”。
