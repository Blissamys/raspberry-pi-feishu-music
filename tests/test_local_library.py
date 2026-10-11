from pathlib import Path

import pytest

from commands import parse_command
from nl_intent import route_natural_language
from export_to_player import delete_local_audio, list_audio_files


def test_list_and_delete_local(tmp_path: Path):
    song = tmp_path / "晴天.flac"
    lrc = tmp_path / "晴天.lrc"
    other = tmp_path / "其它.mp3"
    song.write_bytes(b"x")
    lrc.write_text("lrc")
    other.write_bytes(b"y")
    files = list_audio_files(tmp_path)
    assert song in files and other in files
    msg = delete_local_audio("晴天", inbox=tmp_path)
    assert "已从本地删除" in msg
    assert not song.exists()
    assert not lrc.exists()
    assert other.exists()


def test_delete_all(tmp_path: Path):
    (tmp_path / "a.mp3").write_bytes(b"a")
    (tmp_path / "b.flac").write_bytes(b"b")
    msg = delete_local_audio("全部", inbox=tmp_path)
    assert "已删除本地全部 2 首" in msg
    assert list_audio_files(tmp_path) == []


@pytest.mark.parametrize('text', [
    '删掉本地那首轻熟女',
    '删除本地这首 轻熟女',
    '删除本地那首 KugouMusicClient/session/轻熟女 27 - id.mp3 332.7 KB',
    '删除本地 · KugouMusicClient/session/轻熟女 27 - id.mp3  332.7 KB',
])
def test_delete_spoken_title_or_copied_listing(tmp_path, monkeypatch, text):
    monkeypatch.setenv('LLM_ENABLED', '0')
    song = tmp_path / 'KugouMusicClient/session/轻熟女 27 - id.mp3'
    song.parent.mkdir(parents=True)
    song.write_bytes(b'fixture')
    song.with_suffix('.lrc').write_text('fixture')
    other = tmp_path / 'other.mp3'
    other.write_bytes(b'keep')
    cmd, arg = parse_command(text)
    if cmd == 'unknown':
        cmd, arg = route_natural_language(arg)
    assert cmd == 'delete_local'
    result = delete_local_audio(arg, inbox=tmp_path)
    assert '已从本地删除 1 首' in result
    assert not song.exists()
    assert not song.with_suffix('.lrc').exists()
    assert other.exists()


@pytest.mark.parametrize('query', ['那首', '这首', '那首全部', '这首所有', '那首*'])
def test_spoken_prefix_cannot_become_empty_or_bulk_delete(tmp_path, query):
    song = tmp_path / 'keep.mp3'
    song.write_bytes(b'keep')
    assert '没有匹配' in delete_local_audio(query, inbox=tmp_path)
    assert song.exists()


def test_literal_title_with_spoken_prefix_is_preferred(tmp_path):
    literal = tmp_path / '那首轻熟女.mp3'
    other = tmp_path / '轻熟女.mp3'
    literal.write_bytes(b'fixture')
    other.write_bytes(b'keep')
    assert '已从本地删除 1 首' in delete_local_audio('那首轻熟女', inbox=tmp_path)
    assert not literal.exists()
    assert other.exists()


def test_copied_listing_targets_exact_relative_path(tmp_path):
    song = tmp_path / 'folder/song.mp3'
    other = tmp_path / 'other/folder/song.mp3'
    for path in (song, other):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture')
    assert '已从本地删除 1 首' in delete_local_audio('folder/song.mp3 1 KB', inbox=tmp_path)
    assert not song.exists()
    assert other.exists()
