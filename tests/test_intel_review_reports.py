from pathlib import Path

from app.intel import review_intel


def test_review_intel_week_report_includes_actionable_sections(tmp_path: Path):
    accounts_dir = tmp_path / "data" / "intel" / "accounts"
    feedback_dir = tmp_path / "data" / "intel" / "feedback"
    competitors_dir = tmp_path / "data" / "intel" / "competitors"
    sales_dir = tmp_path / "data" / "intel" / "sales"
    accounts_dir.mkdir(parents=True)
    feedback_dir.mkdir(parents=True)
    competitors_dir.mkdir(parents=True)
    sales_dir.mkdir(parents=True)

    (accounts_dir / "2026-04-19.md").write_text("# 账号表现快照\n\n- 账号: new-main\n- 摘要: 阅读 120，收藏 18\n", encoding="utf-8")
    (feedback_dir / "2026-04-19.md").write_text("# 用户反馈记录\n\n- 来源: review\n- 内容: 标题需要更聚焦\n", encoding="utf-8")
    (competitors_dir / "2026-04-19.md").write_text("# 对标账号与优秀案例\n\n- 链接: https://example.com/a\n- 观察: CTA 位置很自然\n", encoding="utf-8")
    (sales_dir / "2026-04-19.md").write_text("# 专栏与转化记录\n\n- 专栏: CSDN 选题方法\n- 数值: 3 次点击\n", encoding="utf-8")

    path = review_intel(period="week", date="2026-04-19", base_dir=tmp_path, account="new-main")
    content = path.read_text(encoding="utf-8")

    assert "# 本周经营输入复盘" in content
    assert "## 数据概览" in content
    assert "## 用户反馈" in content
    assert "## 对标与外部参考" in content
    assert "## 专栏与转化信号" in content
    assert "## 经营判断" in content
    assert "## 下周动作" in content
    assert "new-main" in content



def test_review_intel_month_report_uses_correct_chinese_label(tmp_path: Path):
    accounts_dir = tmp_path / "data" / "intel" / "accounts"
    accounts_dir.mkdir(parents=True)
    (accounts_dir / "2026-04-19.md").write_text("# 账号表现快照\n\n- 账号: old-traffic\n- 摘要: 阅读 80\n", encoding="utf-8")

    path = review_intel(period="month", date="2026-04-30", base_dir=tmp_path)
    content = path.read_text(encoding="utf-8")

    assert "# 4 月经营输入月报" in content
    assert "## 本月结论" in content
    assert "## 下月实验计划" in content
