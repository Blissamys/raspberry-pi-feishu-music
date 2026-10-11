"""Pure text presentation for bounded, per-user search sessions."""
import math
import re
import time

PAGE_SIZE = 3
TTL = 600
SOURCES = {
    'NeteaseMusicClient': '网易云', 'QQMusicClient': 'QQ音乐',
    'KuwoMusicClient': '酷我', 'KugouMusicClient': '酷狗',
}
ALIASES = {'网易云音乐':'NeteaseMusicClient','网易云':'NeteaseMusicClient',
           'QQ音乐':'QQMusicClient','QQ':'QQMusicClient',
           '酷我音乐':'KuwoMusicClient','酷我':'KuwoMusicClient',
           '酷狗音乐':'KugouMusicClient','酷狗':'KugouMusicClient'}


def source_query(text):
    for name in sorted(ALIASES, key=len, reverse=True):
        if text.casefold().startswith(name.casefold()):
            return ALIASES[name], text[len(name):].strip()
    raise ValueError('支持：只搜QQ、只搜网易云、只搜酷我、只搜酷狗；后面可加歌名。')


def ensure_fresh(session):
    if time.monotonic() - session.get('created', 0) > TTL:
        raise ValueError('搜索候选已过期，请发「重新搜索」或重新输入歌名。')


def move(session, direction):
    ensure_fresh(session)
    offset = session.get('offset', 0) + direction * PAGE_SIZE
    if offset >= len(session['results']):
        raise ValueError('已到最后一批，可发「上一批」、换源或「重新搜索」。')
    if offset < 0:
        raise ValueError('已是第一批。')
    session['offset'] = offset


def _text(value):
    return ' '.join(str(value or '').split())[:160]


def describe(item):
    info = item['info']
    name = str(info.get('song_name') or item['title'])
    versions = []
    for pattern, label in [(r'(?<![a-z])live(?![a-z])|现场', '现场'), (r'伴奏|(?<![a-z])(?:instrumental|karaoke)(?![a-z])', '伴奏'),
                           (r'(?<![a-z])remix(?![a-z])|混音', '混音'), (r'翻唱|(?<![a-z])cover(?![a-z])', '翻唱')]:
        if re.search(pattern, name, re.I): versions.append(label)
    version = '标题提示：' + ' / '.join(versions) if versions else '版本未标注'
    source = SOURCES.get(item.get('source') or info.get('source'), '来源未标注')
    labels = []
    if info.get('ext'): labels.append(str(info.get('ext')).lstrip('.').upper())
    if info.get('file_size'): labels.append(str(info.get('file_size')))
    if info.get('bitrate'): labels.append('码率 ' + str(info.get('bitrate')))
    suffix = '；源站标注：' + _text(' / '.join(labels)) if labels else ''
    return f"{_text(item['title'])}\n   {source} · {version}{suffix}"


def render(session):
    ensure_fresh(session)
    results = session['results']
    offset = session.get('offset', 0)
    session['choices'] = results[offset:offset + PAGE_SIZE]
    lines = [f"「{_text(session['query'])}」候选，第 {offset // PAGE_SIZE + 1}/{max(1, math.ceil(len(results) / PAGE_SIZE))} 页，共 {len(results)} 条。"]
    lines.extend(f'{i}. {describe(item)}' for i, item in enumerate(session['choices'], 1))
    lines.append('回复 1/2/3 选择本页候选；「确认」选本页第1条。')
    lines.append('换一批 / 上一批 / 只搜QQ / 重新搜索 / 取消。来源参数不代表实际音质保证。')
    return '\n'.join(lines)
