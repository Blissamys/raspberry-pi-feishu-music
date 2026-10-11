from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import feishu_bot as bot
from commands import parse_command


@pytest.fixture
def flow(monkeypatch):
    queued = []

    class QueuedThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            queued.append(self.target)

    monkeypatch.setattr(bot.threading, 'Thread', QueuedThread)
    monkeypatch.setattr(bot, '_pending', {})
    monkeypatch.setattr(bot, '_last_search', {})
    monkeypatch.setattr(bot, '_import_pending', {})
    monkeypatch.setattr(bot, '_job', {'state': 'idle', 'detail': 'test'})
    monkeypatch.setenv('LLM_ENABLED', '0')
    choices = [{'title': '晴天', 'info': {'song_name': '晴天'}}]
    search = Mock(return_value=choices)
    download = Mock(return_value=('晴天', '/mock', 'mock details'))
    direct = Mock(return_value=('晴天', '/mock', 'mock details'))
    monkeypatch.setattr(bot, 'search_candidates', search)
    monkeypatch.setattr(bot, 'download_song_info', download)
    monkeypatch.setattr(bot, 'search_and_download', direct)
    monkeypatch.setattr(bot, 'reply_text', Mock())
    return SimpleNamespace(queued=queued, search=search, download=download, direct=direct)


def send(text):
    return bot.handle_command(*parse_command(text), open_id='test')


def test_search_is_busy_until_candidates_arrive(flow):
    send('帮我下载晴天')
    assert bot._job['state'] == 'running'
    assert '已有任务' in send('歌曲其它')
    assert len(flow.queued) == 1
    flow.queued.pop(0)()
    assert bot._job['state'] == 'idle'
    flow.download.assert_not_called()
    send('确认')
    flow.queued.pop(0)()
    flow.download.assert_called_once_with({'song_name': '晴天'}, bot.INBOX_DEFAULT)


def test_search_cannot_overwrite_active_download(flow):
    send('歌曲晴天')
    before = dict(bot._job)
    assert '已有任务' in send('帮我下载其它')
    assert bot._job == before
    assert len(flow.queued) == 1


def test_busy_confirmation_keeps_candidates(flow):
    send('帮我下载晴天')
    flow.queued.pop(0)()
    send('歌曲其它')
    assert '已有任务' in send('确认')
    assert bot._pending['test']['choices']
    flow.queued.pop(0)()
    send('确认')
    flow.queued.pop(0)()
    flow.download.assert_called_once()


def test_cancel_during_search_does_not_restore_candidates(flow):
    send('帮我下载晴天')
    send('取消')
    flow.queued.pop(0)()
    assert 'test' not in bot._pending
    assert bot._job['state'] == 'idle'
    assert '没有待确认' in send('确认')
    flow.download.assert_not_called()


def test_failed_search_clears_previous_candidates(flow):
    send('帮我下载晴天')
    flow.queued.pop(0)()
    flow.search.side_effect = RuntimeError('test failure')
    send('帮我下载其它')
    flow.queued.pop(0)()
    assert '没有待确认' in send('确认')
    assert bot._job['state'] == 'idle'


def test_fixed_prefix_downloads_without_confirmation(flow):
    send('歌曲晴天')
    assert 'test' not in bot._pending
    flow.queued.pop(0)()
    flow.direct.assert_called_once_with('晴天', bot.INBOX_DEFAULT)


def test_chatter_does_not_start_work(flow):
    assert '无法识别' in send('现在可以直接拔sd卡吗')
    assert not flow.queued


def test_unauthorized_sender_cannot_dispatch(flow, monkeypatch):
    monkeypatch.setenv('FEISHU_ALLOW_OPEN_IDS', 'authorized')
    handler = Mock()
    monkeypatch.setattr(bot, 'handle_command', handler)
    bot.on_message(SimpleNamespace(event=SimpleNamespace(
        sender=SimpleNamespace(sender_id=SimpleNamespace(open_id='outsider')),
        message=SimpleNamespace(message_id='mock-message'),
    )))
    handler.assert_not_called()


def test_system_status_available_while_download_running(flow, monkeypatch):
    monkeypatch.setattr(bot, 'format_system_status', lambda **kwargs: 'system report')
    send('歌曲晴天')
    before = dict(bot._job)
    assert send('系统状态') == 'system report'
    assert bot._job == before
    assert len(flow.queued) == 1


def test_dual_disk_export_becomes_preview_without_copy(flow, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(bot.storage_roles, 'configured', lambda: True)
    monkeypatch.setattr(bot.storage_roles, 'prepare_import', lambda: ('cfg', '/usb', '/sd'))
    monkeypatch.setattr(bot.storage_roles, 'verify_import', lambda cfg: None)
    monkeypatch.setattr(bot.storage_roles, 'import_session', lambda cfg: nullcontext(lambda: None))
    monkeypatch.setattr(bot.library_sync, 'preview', lambda *args, **kw: SimpleNamespace(copies=[]))
    monkeypatch.setattr(bot.library_sync, 'format_preview', lambda plan: 'preview')
    execute = Mock()
    monkeypatch.setattr(bot.library_sync, 'execute', execute)
    send('导入')
    assert len(flow.queued) == 1
    flow.queued.pop(0)()
    execute.assert_not_called()
    assert 'test' in bot._import_pending
    send('取消')
    assert 'test' not in bot._import_pending
    assert '没有待确认' in send('确认导入')


def test_missing_download_usb_does_not_start_real_download(flow, monkeypatch):
    def absent(*args, **kwargs): raise ValueError('未找到绑定分区')
    monkeypatch.setattr(bot.storage_roles, 'source_directory', absent)
    send('歌曲晴天')
    flow.queued.pop(0)()
    flow.direct.assert_not_called()
    assert '未找到绑定分区' in bot._get_job()


def test_import_confirmation_is_user_scoped(flow):
    bot._import_pending['somebody_else']={'plan':'private','config':'private'}
    assert '没有待确认' in send('确认导入')
    assert not flow.queued


def test_failed_eject_does_not_claim_copy_safe(flow,monkeypatch):
    from types import SimpleNamespace
    bot._import_pending['test']={'config':'cfg','plan':SimpleNamespace(duplicates=[],conflicts=[])}
    monkeypatch.setattr(bot.library_sync,'execute',lambda *args,**kw:1)
    monkeypatch.setattr(bot.storage_roles,'import_session',lambda cfg:nullcontext(lambda:None))
    def fail():raise ValueError('卸载失败')
    monkeypatch.setattr(bot.storage_roles,'eject_target',fail)
    send('确认导入');flow.queued.pop(0)()
    assert '请勿拔卡' in bot._get_job()
    assert '已安全卸载' not in bot._get_job()


def test_next_page_confirmation_downloads_visible_choice(flow):
    flow.search.return_value=[{'title':f'song{i}','source':'QQMusicClient','info':{'song_name':f'song{i}'}} for i in range(5)]
    send('帮我下载歌');flow.queued.pop(0)()
    assert '第 2/2 页' in send('换一批')
    send('1');flow.queued.pop(0)()
    flow.download.assert_called_once_with({'song_name':'song3'},bot.INBOX_DEFAULT)


def test_source_filter_reuses_own_query(flow):
    send('帮我下载晴天');flow.queued.pop(0)()
    send('只搜QQ');flow.queued.pop(0)()
    assert flow.search.call_args.kwargs['sources']==['QQMusicClient']
    assert flow.search.call_args.args[0]=='晴天'
    assert '歌名' in bot.handle_command(*parse_command('只搜QQ'),open_id='other')


def test_import_conflict_detail_and_decision_are_user_scoped(flow,tmp_path,monkeypatch):
    source,target=tmp_path/'usb',tmp_path/'sd';source.mkdir();target.mkdir()
    (source/'new.mp3').write_bytes(b'fixture')
    plan=bot.library_sync.preview(source,target,tag_reader=lambda p:None)
    bot._import_pending['test']={'plan':plan,'config':'cfg'}
    monkeypatch.setattr(bot.storage_roles,'verify_import',lambda cfg:None)
    assert '缺少' in send('冲突详情 1')
    assert '没有' in bot.handle_command(*parse_command('确认新增 1'),open_id='other')
    response=send('确认新增 1')
    assert '新增 1 首' in response
    assert not list(target.iterdir())
    assert len(bot._import_pending['test']['plan'].copies)==1


def test_finished_job_does_not_leak_elapsed_time_to_next_job(flow):
    bot._job['started']=0
    bot._set_job('idle','finished')
    assert 'started' not in bot._job


def test_conflict_argument_error_is_actionable(flow):
    bot._import_pending['test']={'plan':'unused','config':'unused'}
    assert '正整数' in send('冲突详情 abc')
