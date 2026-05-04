import json
from pathlib import Path

from app.business.ops import build_baseline_topic_libraries_from_full_capture, mark_topic_used
from app.runner.execution_runner import ExecutionRunner
from app.schemas.article_task import ArticleTask
from app.schemas.enums import ExecutionStage, PublishMode, TaskStatus
from app.schemas.execution_result import ExecutionResult
from app.store.task_store import TaskStore


def _batch_with_topics(tmp_path: Path) -> Path:
    batch_dir = tmp_path / 'data' / 'business' / 'topic_batches'
    batch_dir.mkdir(parents=True, exist_ok=True)
    batch_path = batch_dir / 'topic-batch_20260504090000.json'
    payload = {
        'account': '技术小甜甜',
        'generated_at': '2026-05-04T09:00:00Z',
        'batch_strategy': '测试批次',
        'writing_order': ['选题 A', '选题 B'],
        'topics': [
            {
                'number': 1,
                'title': '选题 A',
                'audience': 'Dify 读者',
                'account': '技术小甜甜',
                'column': 'AI实践-Dify专栏',
                'candidate_id': '技术小甜甜::ai实践-dify专栏::growth::01',
                'reason': '理由 1',
                'expected_value': '价值 1',
                'why_now': '现在 1',
                'cta': 'CTA 1',
                'role': '信任题',
                'risk': '风险 1',
                'priority': '主推',
            },
            {
                'number': 2,
                'title': '选题 B',
                'audience': 'Dify 读者',
                'account': '技术小甜甜',
                'column': 'AI实践-Dify专栏',
                'candidate_id': '技术小甜甜::ai实践-dify专栏::growth::02',
                'reason': '理由 2',
                'expected_value': '价值 2',
                'why_now': '现在 2',
                'cta': 'CTA 2',
                'role': '信任题',
                'risk': '风险 2',
                'priority': '主推',
            },
        ],
    }
    batch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return batch_path


def _build_library(tmp_path: Path) -> Path:
    capture = tmp_path / 'full.json'
    capture.write_text(
        json.dumps(
            {
                'columns': [
                    {
                        'title': 'AI实践-Dify专栏',
                        'description': '测试专栏',
                        'articles': [{'title': '旧文 1'}],
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    result = build_baseline_topic_libraries_from_full_capture(
        date='2026-05-04',
        account='技术小甜甜',
        capture_path=capture,
        base_dir=tmp_path,
    )
    library_path = Path(result['libraries'][0]['json_path'])
    payload = json.loads(library_path.read_text(encoding='utf-8'))
    payload['modules'] = [
        {
            'module': 'growth',
            'name': '增长模块',
            'goal': '测试',
            'role': '信任题',
            'status': 'partial',
            'keywords': ['Dify'],
            'candidate_topics': [
                {'candidate_id': '技术小甜甜::ai实践-dify专栏::growth::01', 'title': '选题 A', 'status': 'unused', 'source': 'baseline_library', 'role': '信任题', 'module': 'growth'},
                {'candidate_id': '技术小甜甜::ai实践-dify专栏::growth::02', 'title': '选题 B', 'status': 'unused', 'source': 'baseline_library', 'role': '信任题', 'module': 'growth'},
            ],
        }
    ]
    library_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return library_path


def test_execution_runner_persist_success_auto_syncs_published_topic_state(tmp_path: Path):
    batch_path = _batch_with_topics(tmp_path)
    library_path = _build_library(tmp_path)
    mark_topic_used(
        date='2026-05-04',
        batch_path=batch_path,
        topic_number=2,
        status='used',
        base_dir=tmp_path,
        notes='已保存为草稿',
    )

    db_path = tmp_path / 'tasks.db'
    store = TaskStore(db_path)
    store.init_db()

    task = ArticleTask(
        task_id='task_test_publish_sync',
        article_id='new-main-2026-05-04-new-main-2_dify-_draft',
        title='选题 B',
        body_markdown='# 选题 B\n\n正文',
        tags=['Dify', 'RAG'],
        category='AI实践-Dify专栏',
        publish_mode=PublishMode.PUBLISH,
        metadata={'account_profile': 'new-main'},
    )
    store.create_task(task)

    result = ExecutionResult.started(task_id=task.task_id, article_id=task.article_id, publish_mode=PublishMode.PUBLISH)
    result.finish(
        status=TaskStatus.SUCCESS,
        final_stage=ExecutionStage.DONE,
        article_url='https://mp.csdn.net/mp_blog/creation/success/160770016',
    )

    runner = ExecutionRunner(store, profile_name='new-main', base_dir=tmp_path)
    runner._persist_success(task, result)

    ledger = json.loads((tmp_path / 'data' / 'business' / 'topic_usage' / 'topic_usage_ledger.json').read_text(encoding='utf-8'))
    entry = next(item for item in ledger['entries'] if item['title'] == '选题 B')
    assert entry['status'] == 'published'
    assert '160770016' in (entry.get('notes') or '')

    library_payload = json.loads(library_path.read_text(encoding='utf-8'))
    candidate = library_payload['modules'][0]['candidate_topics'][1]
    assert candidate['status'] == 'published'
