from commands import allowed_open_id, parse_command


def test_parse_download_prefix():
    assert parse_command("歌曲晴天") == ("download", "晴天")
    assert parse_command("歌曲 晴天 周杰伦") == ("download", "晴天 周杰伦")
    assert parse_command("歌曲") == ("download", "")


def test_parse_does_not_download_chatter():
    assert parse_command("现在可以直接拔sd卡吗")[0] == "unknown"


def test_parse_disk_export_status():
    assert parse_command("盘") == ("disks", "")
    assert parse_command("导入") == ("export", "")
    assert parse_command("进度") == ("status", "")


def test_parse_delete_local():
    assert parse_command("删除本地 晴天") == ("delete_local", "晴天")
    assert parse_command("删除本地全部") == ("delete_local", "全部")
    assert parse_command("清空本地") == ("delete_local", "全部")


def test_allowlist(monkeypatch):
    monkeypatch.setenv("FEISHU_ALLOW_OPEN_IDS", "ou_a, ou_b")
    assert allowed_open_id("ou_a") is True
    assert allowed_open_id("ou_c") is False
    monkeypatch.setenv("FEISHU_ALLOW_OPEN_IDS", "")
    assert allowed_open_id("ou_a") is False


def test_storage_commands():
    assert parse_command('存储') == ('storage', '')
    assert parse_command('导入预览') == ('import_preview', '')
    assert parse_command('确认导入') == ('import_confirm', '')
    assert parse_command('弹出SD') == ('eject_sd', '')


def test_search_and_conflict_commands():
    expected={'换一批':('search_next',''),'上一批':('search_previous',''),
              '重新搜索':('search_retry',''),'只搜QQ 晴天':('search_source','QQ 晴天'),
              '待处理 2':('import_issues','2'),'冲突详情 3':('import_issue_detail','3'),
              '标记同曲 3':('import_same','3'),'跳过冲突 3':('import_skip','3'),
              '确认新增 3':('import_add','3')}
    for text,command in expected.items():assert parse_command(text)==command
