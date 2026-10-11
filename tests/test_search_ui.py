import time
import pytest
import search_ui as ui


def results(n):
    return [{'title':f'歌{i} (Live) - 歌手','source':'QQMusicClient','info':{'song_name':f'歌{i} (Live)','ext':'flac','file_size':'10MB'}} for i in range(n)]


def test_page_numbers_match_current_choices():
    session={'query':'歌','results':results(5),'offset':0,'created':time.monotonic()}
    first=ui.render(session)
    assert 'QQ音乐' in first and '现场' in first and 'FLAC' in first
    assert '源站标注' in first
    ui.move(session,1)
    second=ui.render(session)
    assert session['choices'][0]['title'].startswith('歌3')
    assert '1.' in second and '第 2/2 页' in second
    with pytest.raises(ValueError,match='最后'):ui.move(session,1)


def test_expired_search_cannot_page():
    session={'query':'歌','results':results(3),'offset':0,'created':time.monotonic()-601}
    with pytest.raises(ValueError,match='过期'):ui.render(session)


def test_english_title_does_not_match_version_substrings():
    text=ui.describe({'title':'Alive - Artist','source':'QQMusicClient','info':{'song_name':'Alive'}})
    assert '版本未标注' in text
    assert '现场' not in text
