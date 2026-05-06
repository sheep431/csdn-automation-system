import json
from pathlib import Path

from app.business.ops import build_baseline_topic_libraries_from_full_capture
from app.intel.live_accounts import (
    _active_coupon_promotions,
    _assess_coupon_confirmation,
    _assess_coupon_occupied_state,
    _assess_coupon_slot_state,
    _build_coupon_operational_judgment,
    _coupon_usage_context,
    _extract_coupon_target_articles,
    _extract_current_coupon_promotions,
    _is_coupon_management_page,
    _is_coupon_target_selection_page,
    _pick_best_coupon_target_article,
    _record_coupon_usage,
    _strip_coupon_overlay_text,
    analyze_post_publish_coupon_and_pick_next,
    build_coupon_use_plan,
    detect_flow_coupon_signals,
    extract_coupon_management_entries,
)
from app.state.ops import set_column_lifecycle


def _make_library(tmp_path: Path, column: str, role: str, state: str, candidates: list[dict]) -> Path:
    capture = tmp_path / f'{column}.full.json'
    capture.write_text(json.dumps({'columns': [{'title': column, 'description': '测试', 'articles': []}]}, ensure_ascii=False), encoding='utf-8')
    result = build_baseline_topic_libraries_from_full_capture(
        date='2026-05-04',
        account='技术小甜甜',
        capture_path=capture,
        base_dir=tmp_path,
    )
    library_path = next(Path(item['json_path']) for item in result['libraries'] if Path(item['json_path']).name.endswith('.json'))
    payload = json.loads(library_path.read_text(encoding='utf-8'))
    payload['column'] = column
    payload['modules'] = [
        {
            'module': 'm1',
            'name': '模块1',
            'goal': '测试',
            'role': role,
            'status': 'partial',
            'keywords': ['测试'],
            'candidate_topics': candidates,
        }
    ]
    library_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    set_column_lifecycle(
        date='2026-05-04',
        account='技术小甜甜',
        column=column,
        lifecycle_state=state,
        role=role,
        base_dir=tmp_path,
        notes='test',
    )
    return library_path



def _write_coupon_usage_history(tmp_path: Path, entries: list[dict]) -> Path:
    ledger_dir = tmp_path / 'data' / 'business' / 'coupon_usage'
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_dir / 'coupon_usage_ledger.json'
    ledger_path.write_text(json.dumps({'entries': entries, 'updated_at': '2026-05-05T00:00:00Z'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return ledger_path



def test_detect_flow_coupon_signals_ignores_sidebar_but_detects_real_award():
    page_texts = [
        '创作中心\n流量券管理\n内容管理',
        '恭喜你获得 1 张流量券，可用于本次作品推广',
    ]
    result = detect_flow_coupon_signals(page_texts)
    assert result['has_coupon'] is True
    assert any('获得 1 张流量券' in item for item in result['matches'])

    coupon_page = detect_flow_coupon_signals([
        '流量券\n+ 1500\n曝光\n每日任务流量券\n每日完成创作打卡2篇奖励\n有效期：05.04 17:39-05.06 00:00\n去使用'
    ])
    assert coupon_page['has_coupon'] is True
    assert any('每日任务流量券' in item or '+ 1500' in item for item in coupon_page['matches'])

    negative = detect_flow_coupon_signals(['创作中心\n流量券管理\n内容管理'])
    assert negative['has_coupon'] is False


def test_coupon_page_helpers_distinguish_article_page_from_real_coupon_page():
    article_text = _strip_coupon_overlay_text(
        '内容管理\n文章\n同步多平台\n推广\n请切到“流量券管理”页面；若已看到可用券，保持页面不动，系统将在倒计时后读取并生成使用建议。'
    )
    assert _is_coupon_management_page(url='https://mp.csdn.net/mp_blog/manage/article', body_text=article_text) is False

    coupon_text = _strip_coupon_overlay_text(
        '推广管理\n流量券管理\n流量券\n+ 1500\n曝光\n每日任务流量券\n有效期：05.04 17:39-05.06 00:00\n去使用'
    )
    assert _is_coupon_management_page(url='https://mp.csdn.net/mp_blog/manage/flowCoupon', body_text=coupon_text) is True


def test_coupon_target_selection_page_helper_detects_landing_page():
    landing_text = _strip_coupon_overlay_text(
        '流量券投放\n选择推广文章\n我的推广\n推广文章\n确认推广\n取消\n每日任务流量券'
    )
    assert _is_coupon_target_selection_page(
        url='https://mp.csdn.net/mp_blog/manage/traffic/selectArticle',
        body_text=landing_text,
    ) is True


def test_extract_coupon_target_articles_from_dialog_text():
    dialog_text = (
        '可推广文章\n审核中文章不可被推广，流量券可用于本周期内创作文章流量券使用规则\n\n'
        '[AI] 大家都在聊工作流自动化，真正值得普通团队先学的到底是哪一步？\n\n'
        '工作流自动化很火，但普通团队真正该先学的不是把流程做大，而是先做通一个输入清晰、输出稳定、可检查可回退的单一闭环流程。\n\n'
        '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？\n\n'
        '很多 Dify 知识库问答项目前期 Demo 看起来能用，但一上线就暴露召回不稳、依据不准、换个问法就命中失败的问题。\n\n'
        '共 2 个作品\n\n确定\n\n取消'
    )
    titles = _extract_coupon_target_articles(dialog_text)
    assert titles == [
        '[AI] 大家都在聊工作流自动化，真正值得普通团队先学的到底是哪一步？',
        '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
    ]



def test_extract_current_coupon_promotions_from_management_text():
    promotions = _extract_current_coupon_promotions(
        '流量券管理\n我的推广\n'
        '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？\n'
        '很多 Dify 知识库问答项目前期 Demo 看起来能用。\n'
        '推广中\n'
        '[系统运维] Windows开机卡在欢迎界面？3步定位并恢复系统启动\n'
        '摘要内容\n'
        '推广完成\n推广明细'
    )
    assert promotions == [
        {
            'title': '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
            'status': '推广中',
        },
        {
            'title': '[系统运维] Windows开机卡在欢迎界面？3步定位并恢复系统启动',
            'status': '推广完成',
        },
    ]



def test_active_coupon_promotions_filters_only_live_entries():
    active = _active_coupon_promotions(
        [
            {'title': 'A', 'status': '推广中'},
            {'title': 'B', 'status': '推广完成'},
            {'title': 'C', 'status': '投放中'},
        ]
    )
    assert active == [
        {'title': 'A', 'status': '推广中'},
        {'title': 'C', 'status': '投放中'},
    ]



def test_record_coupon_usage_persists_history_for_future_scoring(tmp_path: Path):
    path = _record_coupon_usage(
        date='2026-05-05',
        account='技术小甜甜',
        column='AI实践-Dify专栏',
        title='挂券文章 A',
        candidate_id='技术小甜甜::ai实践-dify专栏::m1::01',
        base_dir=tmp_path,
    )
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert payload['entries'][0]['column'] == 'AI实践-Dify专栏'
    assert payload['entries'][0]['title'] == '挂券文章 A'
    assert payload['entries'][0]['status'] == 'confirmed'



def test_coupon_usage_context_summarizes_counts_and_recent_columns(tmp_path: Path):
    _record_coupon_usage(
        date='2026-05-01',
        account='技术小甜甜',
        column='AI实践-Dify专栏',
        title='A1',
        candidate_id='c1',
        base_dir=tmp_path,
    )
    _record_coupon_usage(
        date='2026-05-02',
        account='技术小甜甜',
        column='AI实践-Dify专栏',
        title='A2',
        candidate_id='c2',
        base_dir=tmp_path,
    )
    _record_coupon_usage(
        date='2026-05-03',
        account='技术小甜甜',
        column='技术前沿每日速读',
        title='B1',
        candidate_id='c3',
        base_dir=tmp_path,
    )
    context = _coupon_usage_context(
        account='技术小甜甜',
        columns={'AI实践-Dify专栏', '技术前沿每日速读'},
        base_dir=tmp_path,
    )
    assert context['counts']['AI实践-Dify专栏'] == 2
    assert context['counts']['技术前沿每日速读'] == 1
    assert context['recent_columns'][0] == '技术前沿每日速读'



def test_assess_coupon_occupied_state_detects_existing_active_promotion():
    result = _assess_coupon_occupied_state(
        clicked_use=False,
        coupon_success_confirmed=False,
        current_promotions=[
            {'title': 'A', 'status': '推广中'},
            {'title': 'B', 'status': '推广完成'},
        ],
    )
    assert result['occupied'] is True
    assert result['reason'] == 'existing_active_promotion'
    assert result['active_promotions'] == [{'title': 'A', 'status': '推广中'}]



def test_assess_coupon_occupied_state_detects_confirmed_spend_in_this_run():
    result = _assess_coupon_occupied_state(
        clicked_use=True,
        coupon_success_confirmed=True,
        current_promotions=[{'title': 'A', 'status': '推广中'}],
    )
    assert result['occupied'] is True
    assert result['reason'] == 'confirmed_in_this_run'



def test_assess_coupon_occupied_state_returns_not_occupied_without_active_promotion():
    result = _assess_coupon_occupied_state(
        clicked_use=False,
        coupon_success_confirmed=False,
        current_promotions=[{'title': 'B', 'status': '推广完成'}],
    )
    assert result['occupied'] is False
    assert result['reason'] == 'no_active_promotion'



def test_assess_coupon_slot_state_prefers_first_coupon_action_text():
    state = _assess_coupon_slot_state([
        {'name': '每日任务流量券', 'available': False, 'action_text': '已完成'},
        {'name': '第二张券', 'available': True, 'action_text': '去使用'},
    ])
    assert state['has_coupon'] is True
    assert state['can_use_now'] is False
    assert state['reason'] == 'first_coupon_completed'
    assert state['first_coupon']['name'] == '每日任务流量券'



def test_assess_coupon_slot_state_marks_first_coupon_usable_when_action_is_use():
    state = _assess_coupon_slot_state([
        {'name': '每日任务流量券', 'available': True, 'action_text': '去使用'},
    ])
    assert state['has_coupon'] is True
    assert state['can_use_now'] is True
    assert state['reason'] == 'first_coupon_usable'



def test_build_coupon_operational_judgment_prefers_confirmed_success():
    judgment = _build_coupon_operational_judgment(
        clicked_use=True,
        coupon_success_confirmed=True,
        coupon_occupied=True,
        active_current_promotions=[{'title': 'A', 'status': '推广中'}],
        coupon_slot_state={'has_coupon': True, 'can_use_now': False, 'reason': 'first_coupon_completed'},
    )
    assert judgment == '本次已确认挂券成功。'



def test_build_coupon_operational_judgment_warns_when_coupon_still_occupied():
    judgment = _build_coupon_operational_judgment(
        clicked_use=False,
        coupon_success_confirmed=False,
        coupon_occupied=True,
        active_current_promotions=[{'title': 'A', 'status': '推广中'}],
        coupon_slot_state={'has_coupon': True, 'can_use_now': False, 'reason': 'first_coupon_completed'},
    )
    assert judgment == '当前首张流量券显示已完成，暂无可挂券。'



def test_build_coupon_operational_judgment_allows_retry_when_not_occupied():
    judgment = _build_coupon_operational_judgment(
        clicked_use=False,
        coupon_success_confirmed=False,
        coupon_occupied=False,
        active_current_promotions=[],
        coupon_slot_state={'has_coupon': True, 'can_use_now': True, 'reason': 'first_coupon_usable'},
    )
    assert judgment == '当前首张流量券可直接去使用，可以挂券。'



def test_build_coupon_operational_judgment_handles_no_coupon_seen():
    judgment = _build_coupon_operational_judgment(
        clicked_use=False,
        coupon_success_confirmed=False,
        coupon_occupied=False,
        active_current_promotions=[],
        coupon_slot_state={'has_coupon': False, 'can_use_now': False, 'reason': 'no_coupon_found'},
    )
    assert judgment == '当前未见可挂流量券。'



def test_pick_best_coupon_target_article_prefers_recommendation_title_overlap():
    target = _pick_best_coupon_target_article(
        recommendation_title='[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
        candidate_titles=[
            '[AI] 大家都在聊工作流自动化，真正值得普通团队先学的到底是哪一步？',
            '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
        ],
    )
    assert target == '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？'


def test_assess_coupon_confirmation_detects_success_after_confirm():
    result = _assess_coupon_confirmation(
        url='https://mp.csdn.net/mp_blog/manage/traffic?spm=1011.2415.3001.10055',
        body_text=(
            '流量券管理\n我的推广\n推广成功\n'
            '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？\n'
            '每日任务流量券\n已使用'
        ),
        selected_title='[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
    )
    assert result['success_confirmed'] is True
    assert result['reason'] == 'success_signal'
    assert '推广成功' in result['signals']



def test_assess_coupon_confirmation_treats_open_selection_dialog_as_unconfirmed():
    result = _assess_coupon_confirmation(
        url='https://mp.csdn.net/mp_blog/manage/traffic?spm=1011.2415.3001.10055',
        body_text=(
            '流量券管理\n可推广文章\n'
            '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？\n'
            '共 2 个作品\n确定\n取消'
        ),
        selected_title='[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
    )
    assert result['success_confirmed'] is False
    assert result['reason'] == 'selection_dialog_still_open'



def test_assess_coupon_confirmation_accepts_my_promotion_listing_without_dialog():
    result = _assess_coupon_confirmation(
        url='https://mp.csdn.net/mp_blog/manage/traffic?spm=1011.2415.3001.10055',
        body_text=(
            '流量券管理\n我的推广\n推广文章\n'
            '[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？\n'
            '每日任务流量券\n投放中'
        ),
        selected_title='[Dify实战] 知识库问答为什么总是“看起来能用”，一上线就暴露召回问题？',
    )
    assert result['success_confirmed'] is True
    assert result['reason'] == 'my_promotion_listing'



def test_analyze_post_publish_coupon_and_pick_next_prefers_flagship_revenue_candidate(tmp_path: Path):
    _make_library(
        tmp_path,
        'AI实践-Dify专栏',
        'flagship_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::ai实践-dify专栏::m1::01',
                'title': '候选 A',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )
    _make_library(
        tmp_path,
        '技术前沿每日速读',
        'traffic_support',
        'active_traffic',
        [
            {
                'candidate_id': '技术小甜甜::技术前沿每日速读::m1::01',
                'title': '候选 B',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '引流题',
                'module': 'm1',
            }
        ],
    )

    result = analyze_post_publish_coupon_and_pick_next(
        date='2026-05-04',
        account='技术小甜甜',
        page_texts=['恭喜你获得 1 张流量券，可用于本次作品推广'],
        base_dir=tmp_path,
        published_title='刚发布的文章',
    )
    assert result['coupon']['has_coupon'] is True
    assert result['recommendation']['title'] == '候选 A'
    assert result['recommendation']['column'] == 'AI实践-Dify专栏'
    assert result['report_path'].exists()



def test_analyze_post_publish_coupon_and_pick_next_balances_coupon_column_spread(tmp_path: Path):
    _make_library(
        tmp_path,
        'AI实践-Dify专栏',
        'flagship_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::ai实践-dify专栏::m1::01',
                'title': '收益专栏候选',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )
    _make_library(
        tmp_path,
        '企业AI落地实践',
        'secondary_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::企业ai落地实践::m1::01',
                'title': '轮转专栏候选',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )
    _write_coupon_usage_history(
        tmp_path,
        [
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券1', 'status': 'confirmed', 'used_at': '2026-05-01T00:00:00Z'},
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券2', 'status': 'confirmed', 'used_at': '2026-05-02T00:00:00Z'},
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券3', 'status': 'confirmed', 'used_at': '2026-05-03T00:00:00Z'},
        ],
    )

    result = analyze_post_publish_coupon_and_pick_next(
        date='2026-05-05',
        account='技术小甜甜',
        page_texts=['恭喜你获得 1 张流量券，可用于本次作品推广'],
        base_dir=tmp_path,
        published_title='刚发布的文章',
    )
    assert result['recommendation']['title'] == '轮转专栏候选'
    assert any('coupon_spread_bonus' in item for item in result['recommendation']['reasons'])



def test_analyze_post_publish_coupon_and_pick_next_still_prioritizes_revenue_strength_when_gap_is_large(tmp_path: Path):
    _make_library(
        tmp_path,
        'AI实践-Dify专栏',
        'flagship_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::ai实践-dify专栏::m1::01',
                'title': '强收益候选',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )
    _make_library(
        tmp_path,
        '技术前沿每日速读',
        'traffic_support',
        'active_traffic',
        [
            {
                'candidate_id': '技术小甜甜::技术前沿每日速读::m1::01',
                'title': '弱收益候选',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '引流题',
                'module': 'm1',
            }
        ],
    )
    _write_coupon_usage_history(
        tmp_path,
        [
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券1', 'status': 'confirmed', 'used_at': '2026-05-01T00:00:00Z'},
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券2', 'status': 'confirmed', 'used_at': '2026-05-02T00:00:00Z'},
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券3', 'status': 'confirmed', 'used_at': '2026-05-03T00:00:00Z'},
        ],
    )

    result = analyze_post_publish_coupon_and_pick_next(
        date='2026-05-05',
        account='技术小甜甜',
        page_texts=['恭喜你获得 1 张流量券，可用于本次作品推广'],
        base_dir=tmp_path,
        published_title='刚发布的文章',
    )
    assert result['recommendation']['title'] == '强收益候选'
    assert 'flagship_revenue' in result['recommendation']['reasons']



def test_extract_coupon_management_entries_parses_available_coupon_block():
    entries = extract_coupon_management_entries([
        '流量券\n+ 1500\n曝光\n每日任务流量券\n每日完成创作打卡2篇奖励\n有效期：05.04 17:39-05.06 00:00\n去使用'
    ])
    assert len(entries) == 1
    entry = entries[0]
    assert entry['name'] == '每日任务流量券'
    assert entry['exposure'] == '+ 1500曝光'
    assert entry['validity'] == '05.04 17:39-05.06 00:00'
    assert entry['available'] is True
    assert entry['action_text'] == '去使用'


def test_extract_coupon_management_entries_prefers_real_coupon_name_over_rules_heading():
    entries = extract_coupon_management_entries([
        '流量券\n流量券使用规则\n+ 1500\n曝光\n每日任务流量券\n有效期：05.04 17:39-05.06 00:00\n去使用'
    ])
    assert entries[0]['name'] == '每日任务流量券'



def test_extract_coupon_management_entries_recognizes_completed_coupon_state():
    entries = extract_coupon_management_entries([
        '流量券\n+ 1500\n曝光\n每日任务流量券\n有效期：05.04 17:39-05.06 00:00\n已完成'
    ])
    assert entries[0]['action_text'] == '已完成'
    assert entries[0]['available'] is False



def test_extract_coupon_management_entries_does_not_treat_go_get_or_no_available_as_usable():
    entries = extract_coupon_management_entries([
        '流量券\n创作得流量券\n您当前无可用流量券，完成创作任务即可获得\n有效期：05.06 00:00-05.07 00:00\n去获取'
    ])
    assert entries[0]['action_text'] == '去获取'
    assert entries[0]['available'] is False



def test_build_coupon_use_plan_includes_coupon_entry_and_recommendation(tmp_path: Path):
    _make_library(
        tmp_path,
        'AI实践-Dify专栏',
        'flagship_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::ai实践-dify专栏::m1::01',
                'title': '候选 A',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )

    result = build_coupon_use_plan(
        date='2026-05-04',
        account='技术小甜甜',
        page_texts=[
            '流量券\n+ 1500\n曝光\n每日任务流量券\n每日完成创作打卡2篇奖励\n有效期：05.04 17:39-05.06 00:00\n去使用'
        ],
        base_dir=tmp_path,
        published_title='刚发布的文章',
    )
    assert result['coupon']['has_coupon'] is True
    assert result['recommendation']['title'] == '候选 A'
    assert result['coupon_entries'][0]['name'] == '每日任务流量券'
    assert result['usage_candidate']['title'] == '候选 A'
    assert result['usage_candidate']['coupon_name'] == '每日任务流量券'
    assert result['report_path'].exists()
    assert 'score_breakdown' in result['recommendation']
    assert 'usage_context' in result



def test_build_coupon_use_plan_emits_strategy_suggestion_for_spread_vs_revenue_balance(tmp_path: Path):
    _make_library(
        tmp_path,
        'AI实践-Dify专栏',
        'flagship_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::ai实践-dify专栏::m1::01',
                'title': '收益专栏候选',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )
    _make_library(
        tmp_path,
        '企业AI落地实践',
        'secondary_revenue',
        'active_revenue',
        [
            {
                'candidate_id': '技术小甜甜::企业ai落地实践::m1::01',
                'title': '轮转专栏候选',
                'status': 'unused',
                'source': 'baseline_library',
                'role': '转化题',
                'module': 'm1',
            }
        ],
    )
    _write_coupon_usage_history(
        tmp_path,
        [
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券1', 'status': 'confirmed', 'used_at': '2026-05-01T00:00:00Z'},
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券2', 'status': 'confirmed', 'used_at': '2026-05-02T00:00:00Z'},
            {'account': '技术小甜甜', 'column': 'AI实践-Dify专栏', 'title': '旧挂券3', 'status': 'confirmed', 'used_at': '2026-05-03T00:00:00Z'},
        ],
    )
    result = build_coupon_use_plan(
        date='2026-05-05',
        account='技术小甜甜',
        page_texts=[
            '流量券\n+ 1500\n曝光\n每日任务流量券\n有效期：05.05 00:00-05.06 00:00\n去使用'
        ],
        base_dir=tmp_path,
        published_title='刚发布的文章',
    )
    assert result['usage_candidate']['title'] == '轮转专栏候选'
    assert '收益专栏继续优先挂券' in str(result.get('strategy_suggestion') or '')
