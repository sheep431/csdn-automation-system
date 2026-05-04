# CSDN automation-system

当前这是“技术小甜甜”账号的一期实战运营系统工程目录。

目标不是做一个抽象平台，而是先把下面 3 个闭环跑顺：
- 选题闭环
- 发文闭环
- 运营分析闭环

当前默认工作重点
- 用历史基线 + 实时发布事实维护专栏 baseline
- 用题库状态推进 daily topic workflow
- 用 dashboard 作为人工操作入口

快速入口
1. 先看项目当前状态：`NEXT.md`
2. 再看系统规范入口：`docs/specs/README.md`
3. 如果要直接看运营面板：`http://127.0.0.1:8787/`

当前最常用命令
```bash
cd '/mnt/e/个人项目/CSDN账号运营/automation-system'

# 启动 dashboard（当前推荐入口）
PYTHONPATH=. .venv/bin/python -m app.main serve-topic-library-dashboard \
  --account 技术小甜甜 \
  --profile new-main \
  --host 127.0.0.1 \
  --port 8787

# 仅生成静态 dashboard
PYTHONPATH=. .venv/bin/python -m app.main build-topic-library-dashboard --account 技术小甜甜

# 重抓完整账号并重建 baseline（dashboard 校准按钮背后做的核心事）
PYTHONPATH=. .venv/bin/python -m app.main capture-csdn-full-account \
  --date YYYY-MM-DD \
  --account 技术小甜甜 \
  --profile new-main

PYTHONPATH=. .venv/bin/python -m app.main build-column-baseline-from-full \
  --date YYYY-MM-DD \
  --account 技术小甜甜 \
  --capture-path data/intel/accounts/YYYY-MM-DD_技术小甜甜_full.json

PYTHONPATH=. .venv/bin/python -m app.main build-topic-library-baseline-from-full \
  --date YYYY-MM-DD \
  --account 技术小甜甜 \
  --capture-path data/intel/accounts/YYYY-MM-DD_技术小甜甜_full.json
```

当前关键约定
- old markdown drafts 只算背景，不算生产基线
- 所有非 deprecated 专栏都保留 topic library
- 不校准时，沿用现有 baseline，并按 published/used/approved 等状态增量推进
- 点击“校准 baseline”时，才按当前发布事实刷新 baseline
- 刷新 baseline 时必须保留已有 candidate 状态，不能把人工推进结果刷回 unused
