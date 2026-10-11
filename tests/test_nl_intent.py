from commands import parse_command
from nl_intent import heuristic_intent, llm_to_command


def test_confirm_cancel():
    assert parse_command("确认") == ("confirm", "1")
    assert parse_command("2") == ("confirm", "2")
    assert parse_command("取消") == ("cancel", "")


def test_heuristic_download_and_delete():
    assert heuristic_intent("帮我下载晴天") == ("nl_download", "晴天")
    assert heuristic_intent("删掉本地情歌")[0] == "delete_local"
    assert heuristic_intent("现在可以直接拔sd卡吗") is None


def test_llm_json_mapping():
    assert llm_to_command({"intent": "download", "query": "晴天", "index": 0}) == ("nl_download", "晴天")
    assert llm_to_command({"intent": "confirm", "query": "", "index": 2}) == ("confirm", "2")
    assert llm_to_command({"intent": "chat", "query": "", "index": 0}) is None


def test_chatter_and_negation_do_not_execute_actions(monkeypatch):
    from nl_intent import route_natural_language
    monkeypatch.setenv('LLM_ENABLED', '0')
    for text in ('不要删除本地全部', '怎么导入', '我刚才说了删除本地全部',
                 '我听说下载晴天很快', '请不要导入'):
        assert route_natural_language(text) == ('unknown', text)


def test_help_export_example_works_without_model():
    assert heuristic_intent('把歌拷到SD') == ('export', '')
