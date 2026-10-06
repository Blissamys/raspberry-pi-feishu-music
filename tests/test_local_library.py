from pathlib import Path

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
