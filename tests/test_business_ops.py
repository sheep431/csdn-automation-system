from pathlib import Path

from typer.testing import CliRunner

from app.main import app
from app.business.ops import create_topic_brief, review_business

runner = CliRunner()


def test_create_topic_brief_writes_decision_note(tmp_path: Path):
    path = create_topic_brief(
        date="2026-04-19",
        account="技术小甜甜",
        title="Python 字典去重的 3 种常见写法",
        audience="刚学 Python 的新手",
        column="Python 入门系列",
        angle="从错误示例到可直接复制的正确写法",
        value="能直接解决新手常见去重问题，容易形成系列化内容",
        cta="在专栏页继续看集合、列表推导式和字典的实战组合",
        source_inputs=["用户常问", "评论区高频问题", "第 0 层周报建议"],
        why_now="这个题覆盖面广，适合新号先打基础流量",
        base_dir=tmp_path,
    )

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "业务层选题决策" in content
    assert "技术小甜甜" in content
    assert "Python 入门系列" in content
    assert "为什么现在发" in content
    assert "第 0 层周报建议" in content


def test_review_business_builds_playbook_from_topic_briefs(tmp_path: Path):
    topic_dir = tmp_path / "data" / "business" / "topic_briefs"
    topic_dir.mkdir(parents=True)
    (topic_dir / "2026-04-19_python.md").write_text(
        "# 业务层选题决策：Python 字典去重\n\n- 账号: 技术小甜甜\n- 目标读者: 新手\n- 价值判断: 适合做引流题\n",
        encoding="utf-8",
    )

    path = review_business(date="2026-04-19", base_dir=tmp_path, account="技术小甜甜")

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "业务层复盘" in content
    assert "## 选题决策" in content
    assert "Python 字典去重" in content
    assert "## 业务层结论" in content


def test_plan_topic_cli_creates_business_brief(tmp_path: Path):
    result = runner.invoke(
        app,
        [
            "plan-topic",
            "--date",
            "2026-04-19",
            "--account",
            "技术小甜甜",
            "--title",
            "如何给 CSDN 文章配图不踩坑",
            "--audience",
            "想快速上手发文的新手博主",
            "--column",
            "CSDN 实战系列",
            "--angle",
            "直接给出可复制的步骤和检查清单",
            "--value",
            "这类内容可以直接转成教程型流量题",
            "--cta",
            "引导读者继续看专栏里的完整发文流程",
            "--why-now",
            "当前正在搭建自动化发文闭环，需要补齐实操步骤",
            "--source-input",
            "第 0 层经营输入",
            "--source-input",
            "用户明确要求先做最小闭环",
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    output_dir = tmp_path / "data" / "business" / "topic_briefs"
    files = list(output_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "如何给 CSDN 文章配图不踩坑" in content
    assert "想快速上手发文的新手博主" in content
    assert "当前正在搭建自动化发文闭环" in content


def test_plan_topic_cli_can_attach_strategy_and_column_assets(tmp_path: Path):
    strategy_path = tmp_path / "strategy.md"
    strategy_path.write_text("# 策略输出\n", encoding="utf-8")
    column_asset_path = tmp_path / "column.md"
    column_asset_path.write_text("# 专栏资产\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "plan-topic",
            "--date",
            "2026-04-20",
            "--account",
            "技术小甜甜",
            "--title",
            "免费文如何自然引导用户进入专栏",
            "--audience",
            "想提高专栏转化的作者",
            "--column",
            "CSDN专栏增长",
            "--angle",
            "从免费文承接到专栏页设计",
            "--value",
            "补齐转化桥接空缺",
            "--cta",
            "引导进入专栏看完整设计",
            "--why-now",
            "当前正补齐专栏转化链",
            "--strategy-path",
            str(strategy_path),
            "--column-asset-path",
            str(column_asset_path),
            "--base-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    files = list((tmp_path / "data" / "business" / "topic_briefs").glob("*.md"))
    content = sorted(files)[-1].read_text(encoding="utf-8")
    assert "策略输出" in content
    assert "专栏资产" in content
