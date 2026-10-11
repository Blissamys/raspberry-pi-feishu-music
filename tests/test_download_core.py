from dataclasses import dataclass
from unittest.mock import Mock

import download_core as core


@dataclass
class SongInfoLike:
    """Relevant protocol of musicdl 2.14 SongInfo, deliberately not a dict."""
    song_name: str
    singers: str
    source: str

    def get(self, key, default=None):
        return getattr(self, key, default)


def test_search_keeps_songinfo_objects_from_multiple_sources(tmp_path, monkeypatch):
    netease = SongInfoLike('晴天', '周杰伦', 'NeteaseMusicClient')
    qq = SongInfoLike('稻香', '周杰伦', 'QQMusicClient')
    kugou = SongInfoLike('七里香', '周杰伦', 'KugouMusicClient')
    client = Mock()
    client.search.return_value = {
        'NeteaseMusicClient': [netease],
        'QQMusicClient': [qq],
        'KuwoMusicClient': [],
        'KugouMusicClient': [kugou],
    }
    monkeypatch.setattr(core, '_init_client', lambda *args: client)
    candidates = core.search_candidates('周杰伦', work_dir=tmp_path)
    assert [x['title'] for x in candidates] == ['晴天 - 周杰伦', '稻香 - 周杰伦', '七里香 - 周杰伦']
    assert candidates[0]['info'] is netease
    assert candidates[1]['info'] is qq
    assert candidates[2]['info'] is kugou


def test_fixed_download_passes_original_songinfo_to_downloader(tmp_path, monkeypatch):
    song = SongInfoLike('晴天', '周杰伦', 'QQMusicClient')
    client = Mock()
    client.search.return_value = {'QQMusicClient': [song]}
    monkeypatch.setattr(core, '_init_client', lambda *args: client)
    download = Mock(return_value=('晴天', tmp_path, 'test'))
    monkeypatch.setattr(core, 'download_song_info', download)
    core.search_and_download('晴天', tmp_path)
    download.assert_called_once_with(song, tmp_path)


def test_dictionary_results_remain_supported(tmp_path, monkeypatch):
    client = Mock()
    client.search.return_value = {'source': [None, 'invalid', {'song_name': '晴天', 'singers': ['周杰伦']}]}
    monkeypatch.setattr(core, '_init_client', lambda *args: client)
    assert core.search_candidates('晴天', work_dir=tmp_path)[0]['title'] == '晴天 - 周杰伦'


def test_lost_usb_after_search_blocks_download_mkdir(tmp_path, monkeypatch):
    state={'mounted':True}
    song=SongInfoLike('song','artist','QQMusicClient')
    def search(**kw):
        state['mounted']=False
        return {'QQMusicClient':[song]}
    client=Mock()
    client.search.side_effect=search
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    def validate():
        if not state['mounted']:raise ValueError('下载 U 盘已移除')
    import pytest
    with pytest.raises(ValueError,match='已移除'):
        core.search_and_download('song',tmp_path,validate=validate)
    client.download.assert_not_called()


def test_diverse_search_preserves_same_song_across_sources(tmp_path,monkeypatch):
    client=Mock()
    client.search.return_value={
        'NeteaseMusicClient':[{'song_name':'晴天','singers':'周杰伦','identifier':'1'},{'song_name':'夜曲','singers':'周杰伦','identifier':'2'}],
        'QQMusicClient':[{'song_name':'晴天','singers':'周杰伦','identifier':'3'}],
    }
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    found=core.search_candidates('周杰伦',limit=20,work_dir=tmp_path,diverse=True)
    assert [item['source'] for item in found[:2]]==['NeteaseMusicClient','QQMusicClient']
    assert len(found)==3


def test_selected_source_is_passed_to_client(tmp_path,monkeypatch):
    client=Mock();client.search.return_value={}
    init=Mock(return_value=client)
    monkeypatch.setattr(core,'_init_client',init)
    core.search_candidates('晴天',work_dir=tmp_path,sources=['QQMusicClient'])
    assert init.call_args.args[1]==['QQMusicClient']


def test_download_without_actual_file_is_failure(tmp_path,monkeypatch):
    client=Mock();client.download.return_value=[]
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    import pytest
    with pytest.raises(RuntimeError,match='文件'):
        core.download_song_info({'song_name':'晴天'},tmp_path)


def test_failed_download_cannot_reuse_recent_existing_file(tmp_path,monkeypatch):
    (tmp_path/'old.flac').write_bytes(b'old')
    temp=tmp_path/'.musicdl_temp';temp.mkdir();(temp/'cached.flac').write_bytes(b'cached')
    client=Mock();client.download.return_value=[]
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    import pytest
    with pytest.raises(RuntimeError,match='文件'):core.download_song_info({'song_name':'new'},tmp_path)
    assert (tmp_path/'old.flac').read_bytes()==b'old'


def test_returned_unchanged_cache_is_not_moved_or_reported_new(tmp_path,monkeypatch):
    import pytest
    temp=tmp_path/'.musicdl_temp';temp.mkdir()
    old=temp/'old.flac';old.write_bytes(b'old')
    client=Mock();client.download.return_value=[{'save_path':str(old),'song_name':'new','singers':'artist'}]
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    with pytest.raises(RuntimeError,match='文件'):
        core.download_song_info({'song_name':'new'},tmp_path)
    assert old.read_bytes()==b'old'
    assert not (tmp_path/'new-artist.flac').exists()


def test_fresh_returned_audio_still_downloads(tmp_path,monkeypatch):
    temp=tmp_path/'.musicdl_temp'
    client=Mock()
    def download(**kwargs):
        path=temp/'fresh.flac';path.write_bytes(b'new audio')
        return [{'save_path':str(path),'song_name':'new','singers':'artist'}]
    client.download.side_effect=download
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    monkeypatch.setattr(core,'inspect_audio',lambda *args:'details')
    assert core.download_song_info({'song_name':'new','singers':'artist'},tmp_path)[0]=='new - artist'
    assert (tmp_path/'new-artist.flac').read_bytes()==b'new audio'


def test_returned_cache_alias_cannot_bypass_snapshot(tmp_path,monkeypatch):
    import pytest
    temp=tmp_path/'.musicdl_temp';temp.mkdir();old=temp/'old.flac';old.write_bytes(b'old')
    client=Mock();client.download.return_value=[{'save_path':str(temp/'..'/'.musicdl_temp'/'old.flac'),'song_name':'new','singers':'artist'}]
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    with pytest.raises(RuntimeError,match='文件'):core.download_song_info({'song_name':'new'},tmp_path)
    assert old.read_bytes()==b'old'


def test_non_audio_download_result_is_not_reported_success(tmp_path,monkeypatch):
    import pytest
    temp=tmp_path/'.musicdl_temp';client=Mock()
    def download(**kwargs):
        cache=temp/'cache.pkl';cache.write_bytes(b'cache')
        return [{'save_path':str(cache),'song_name':'new','singers':'artist'}]
    client.download.side_effect=download
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    with pytest.raises(RuntimeError,match='文件'):core.download_song_info({'song_name':'new'},tmp_path)
    assert not (tmp_path/'new-artist.pkl').exists()


def test_fallback_cannot_follow_symlink_outside_attempt(tmp_path,monkeypatch):
    import pytest
    temp=tmp_path/'.musicdl_temp';outside=tmp_path/'outside.flac';outside.write_bytes(b'outside')
    client=Mock()
    def download(**kwargs):
        (temp/'linked.flac').symlink_to(outside)
        return []
    client.download.side_effect=download
    monkeypatch.setattr(core,'_init_client',lambda *args:client)
    with pytest.raises(RuntimeError,match='文件'):core.download_song_info({'song_name':'new'},tmp_path)
    assert outside.read_bytes()==b'outside'
