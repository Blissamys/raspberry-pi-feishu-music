"""Preview and additive, verified music import. Never deletes existing music."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, replace
import hashlib
import os
import re
from pathlib import Path
import shutil
import sys
import time
import unicodedata
import uuid

AUDIO_EXTS = {'.mp3', '.flac', '.m4a', '.wav', '.aac', '.ogg', '.opus'}
PLAN_TTL = 600


def _digest(path, progress=None):
    h = hashlib.sha256()
    done, total = 0, path.stat().st_size
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
            done += len(block)
            if progress: progress(done, total)
    return h.hexdigest()


def song_key(path):
    from tinytag import TinyTag
    try:
        tag = TinyTag.get(str(path))
    except Exception:
        return None
    if not tag.title or not tag.artist:
        return None
    return tag.title, tag.artist


def _normalize(key):
    if not key or len(key) != 2 or not all(isinstance(x, str) and x.strip() for x in key):
        return None
    title, artist = (' '.join(unicodedata.normalize('NFKC', x).casefold().split()) for x in key)
    artists = tuple(sorted({x.strip() for x in re.split(r'[,、;；]', artist) if x.strip()}))
    return title, artists


def _snapshot(root, progress=lambda text: None, label="曲库"):
    if not root.exists():
        return ()
    rows = []
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d != '.musicdl_temp')
        for name in dirs + files:
            p = Path(folder) / name
            if p.is_symlink():
                raise ValueError('曲库含符号链接，拒绝越界扫描：' + str(p.relative_to(root)))
        for name in sorted(files):
            p = Path(folder) / name
            if p.suffix.lower() not in AUDIO_EXTS | {'.lrc'}:
                continue
            progress(f"扫描中：{label}，已扫描 {len(rows)} 个文件，当前 {p.name}")
            before = p.stat()
            digest = _digest(p)
            after = p.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError('扫描中文件发生变化，请重新预览')
            rows.append((str(p.relative_to(root)), after.st_size, after.st_mtime_ns, digest))
    return tuple(sorted(rows))


@dataclass(frozen=True)
class Copy:
    source: str
    destination: str
    size: int
    digest: str
    lyric: tuple | None = None
    key: tuple | None = None


@dataclass(frozen=True)
class Conflict:
    item: Copy
    reason: str
    can_add: bool
    tags: str


@dataclass(frozen=True)
class Plan:
    source: Path
    target: Path
    source_snapshot: tuple
    target_snapshot: tuple
    copies: tuple[Copy, ...]
    duplicates: tuple[str, ...]
    conflicts: tuple[str, ...]
    existing_duplicates: int
    created: float
    unknown_target: tuple[str, ...] = ()
    lyrics: tuple[Copy, ...] = ()
    issues: tuple[Conflict, ...] = ()
    decisions: tuple[tuple[int, str], ...] = ()
    skipped: tuple[str, ...] = ()

    @property
    def bytes_required(self):
        return sum(c.size + (c.lyric[2] if c.lyric else 0) for c in self.copies) + sum(c.size for c in self.lyrics)


def _capacity(target, required):
    parent = target
    while not parent.exists():
        parent = parent.parent
    if required and shutil.disk_usage(parent).free < required + 1024 * 1024:
        raise ValueError('SD 空间不足（另保留 1 MiB 余量）')


def _target_entries(target):
    return {str(p.relative_to(target)).casefold(): p.is_dir() for p in target.rglob('*')} if target.exists() else {}


def _path_conflict(path, entries, planned):
    name = path.casefold()
    if name in entries or name in planned:
        return True
    parents = [str(parent).casefold() for parent in Path(path).parents if str(parent) != '.']
    if any(entries.get(parent) is False or parent in planned for parent in parents):
        return True
    return any(other.startswith(name + '/') for other in planned)


def _copy_paths(item):
    return [item.destination] + ([item.lyric[1]] if item.lyric else [])


def _validate_copy_paths(plan):
    entries, planned = _target_entries(plan.target), set()
    for item in plan.copies + plan.lyrics:
        for path in _copy_paths(item):
            if _path_conflict(path, entries, planned):
                raise ValueError('目标路径或同名文件冲突，请重新预览')
            planned.add(path.casefold())


def preview(source: Path, target: Path, *, tag_reader=song_key, dest_subdir='', progress=lambda text: None) -> Plan:
    for path in (Path(source), Path(target)):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('源或目标路径含符号链接')
    source, target = Path(source).resolve(), Path(target).resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('源目录与目标目录相同或嵌套')
    prefix = Path(dest_subdir)
    if prefix.is_absolute() or '..' in prefix.parts:
        raise ValueError('无效目标子目录')
    if not source.is_dir():
        raise ValueError('下载 U 盘曲库目录不存在')
    src = _snapshot(source, progress, "下载盘")
    dst = _snapshot(target, progress, "播放器 SD")
    known_keys, known_hashes = set(), set()
    target_hash_paths, unknown_target = {}, []
    existing_duplicates = 0
    for rel, size, stamp, digest in dst:
        if Path(rel).suffix.lower() not in AUDIO_EXTS:
            continue
        key = _normalize(tag_reader(target / rel))
        if key is None:
            unknown_target.append(rel)
        target_hash_paths.setdefault(digest, rel)
        if digest in known_hashes or (key and key in known_keys):
            existing_duplicates += 1
        known_hashes.add(digest)
        if key:
            known_keys.add(key)
    copies, duplicates, conflicts, lyrics, issues = [], [], [], [], []
    source_rows = {row[0]: row for row in src}
    entries, planned = _target_entries(target), set()
    occupied = set(entries)
    for rel, size, stamp, digest in src:
        if Path(rel).suffix.lower() not in AUDIO_EXTS:
            continue
        key = _normalize(tag_reader(source / rel))
        if digest in known_hashes or (key and key in known_keys):
            duplicates.append(rel)
            # Repair an interrupted lyric copy only for byte-identical SD audio.
            if digest in target_hash_paths:
                lyric_rel = str(Path(rel).with_suffix('.lrc'))
                lyric_dest = str(Path(target_hash_paths[digest]).with_suffix('.lrc'))
                if lyric_rel in source_rows and not _path_conflict(lyric_dest, entries, planned):
                    row = source_rows[lyric_rel]
                    lyrics.append(Copy(lyric_rel, lyric_dest, row[1], row[3]))
                    occupied.add(lyric_dest.casefold())
                    planned.add(lyric_dest.casefold())
            continue
        destination = str(prefix / rel)
        lyric_rel = str(Path(rel).with_suffix('.lrc'))
        lyric = None
        if lyric_rel in source_rows:
            row = source_rows[lyric_rel]
            lyric = (lyric_rel, str(prefix / lyric_rel), row[1], row[3])
        paths = [destination] + ([lyric[1]] if lyric else [])
        item = Copy(rel, destination, size, digest, lyric, key)
        collision = any(_path_conflict(p, entries, planned) for p in paths)
        reason = ('目标同名文件已存在' if collision else
                  '缺少歌名/歌手标签' if key is None else
                  'SD 有缺标签歌曲，无法排除跨格式重复' if unknown_target else '')
        if reason:
            conflicts.append(rel + '（' + reason + '）')
            tags = ' / '.join((str(key[0]), ', '.join(key[1]))) if key else '标签不足'
            issues.append(Conflict(item, reason, not collision, tags))
            continue
        copies.append(item)
        occupied.update(p.casefold() for p in paths)
        planned.update(p.casefold() for p in paths)
        known_hashes.add(digest)
        known_keys.add(key)
    plan = Plan(source, target, src, dst, tuple(copies), tuple(duplicates), tuple(conflicts), existing_duplicates, time.monotonic(), tuple(unknown_target), tuple(lyrics), tuple(issues))
    _capacity(target, plan.bytes_required)
    return plan


def _publish(temp, destination):
    # Linux renameat2 avoids overwriting a file created after the preview.
    if sys.platform == 'linux':
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(temp), -100, os.fsencode(destination), 1):
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err), str(destination))
    else:
        os.link(temp, destination)
        temp.unlink()


def _copy_verified(source, destination, digest, progress=lambda text: None):
    for path in (source, destination):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('复制路径出现符号链接')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.part')
    try:
        with source.open('rb') as src, temp.open('xb') as dst:
            done, total = 0, source.stat().st_size
            progress(f'复制中：{destination.name}，0/{total} 字节')
            for block in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(block)
                done += len(block)
                progress(f'复制中：{destination.name}，{done}/{total} 字节')
            dst.flush()
            os.fsync(dst.fileno())
        progress(f'校验中：{destination.name}')
        report = lambda done, total: progress(f'校验中：{destination.name}，{done}/{total} 字节')
        if _digest(temp, report) != digest:
            raise ValueError('复制校验失败或源文件变化')
        _publish(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()  # Only this operation's unpublished temporary file.


class ImportInterrupted(RuntimeError):
    def __init__(self, completed, lyrics_completed, cause):
        self.completed = completed
        self.lyrics_completed = lyrics_completed
        self.cause = cause
        super().__init__(f'已完成 {completed} 首音频、{lyrics_completed} 份歌词后中断：{cause}')


def execute(plan: Plan, *, verify=lambda: None, progress=lambda text: None) -> int:
    ensure_fresh(plan)
    verify()
    progress('扫描中：重新核对两盘与预览是否一致')
    if (_snapshot(plan.source, progress, '下载盘复核') != plan.source_snapshot or
            _snapshot(plan.target, progress, 'SD 复核') != plan.target_snapshot):
        raise ValueError('曲库发生变化，请重新预览')
    _capacity(plan.target, plan.bytes_required)
    _validate_copy_paths(plan)
    completed, lyrics_completed = 0, 0
    try:
        for index, item in enumerate(plan.copies, 1):
            verify()
            if (plan.source / item.source).is_symlink():
                raise ValueError('源文件变化为符号链接')
            report = lambda text: progress(f'{text}；第 {index}/{len(plan.copies)} 首，已完成 {completed} 首')
            _copy_verified(plan.source / item.source, plan.target / item.destination, item.digest, report)
            completed += 1
            if item.lyric:
                source, destination, size, digest = item.lyric
                _copy_verified(plan.source / source, plan.target / destination, digest, progress)
                lyrics_completed += 1
            progress(f'校验完成：{completed}/{len(plan.copies)} 首')
        for item in plan.lyrics:
            verify()
            _copy_verified(plan.source / item.source, plan.target / item.destination, item.digest, progress)
            lyrics_completed += 1
            progress('已校验补齐歌词：' + item.destination)
        verify()
    except Exception as exc:
        raise ImportInterrupted(completed, lyrics_completed, exc) from exc
    return completed


def ensure_fresh(plan):
    if time.monotonic() - plan.created > PLAN_TTL:
        raise ValueError('预览已过期，请重新发「导入预览」。')


def conflict_details(plan, index):
    ensure_fresh(plan)
    if not 1 <= index <= len(plan.issues):
        raise ValueError('冲突编号不存在，请发「待处理」。')
    issue = plan.issues[index - 1]
    done = dict(plan.decisions).get(index)
    lines = [f'冲突 {index}：{issue.item.source}', f'标签：{issue.tags}',
             f'原因：{issue.reason}', f'目标路径：{issue.item.destination}']
    if plan.unknown_target:
        lines.append('SD 待核对：' + '；'.join(plan.unknown_target[:5]))
    if done:
        lines.append('本次已处理：' + {'add':'加入新增计划','same':'按同曲跳过','skip':'跳过本次'}[done])
    else:
        lines.append(f'标记同曲 {index} / 跳过冲突 {index}（仅本次，不改文件或标签）')
        if issue.can_add:
            lines.append(f'确认不是重复歌曲，可发「确认新增 {index}」；之后仍需「确认导入」才复制。')
        else:
            lines.append('同名冲突禁止强行新增或覆盖；请先在电脑整理文件名，再重新预览。')
    return '\n'.join(lines)


def format_conflicts(plan, page=1):
    ensure_fresh(plan)
    if page < 1:
        raise ValueError('页码从 1 开始')
    unresolved = [(i, issue) for i, issue in enumerate(plan.issues, 1) if i not in dict(plan.decisions)]
    if not unresolved:
        return '没有待处理冲突。可发「确认导入」执行当前新增计划。'
    rows = unresolved[(page - 1) * 10:page * 10]
    if not rows:
        raise ValueError('没有这一页，请发「待处理 1」。')
    lines = [f'待处理 {len(unresolved)} 项，第 {page}/{(len(unresolved)+9)//10} 页（编号不变）：']
    lines.extend(f'{i}. {item.item.source} — {item.reason}' for i, item in rows)
    lines.append('发「冲突详情 编号」查看；「待处理 页码」翻页。未处理项不会复制，其它新增项可正常确认导入。')
    return '\n'.join(lines)


def resolve_conflict(plan, index, action):
    ensure_fresh(plan)
    if action not in {'add', 'same', 'skip'}:
        raise ValueError('不支持的处理方式')
    if not 1 <= index <= len(plan.issues):
        raise ValueError('冲突编号不存在')
    if index in dict(plan.decisions):
        raise ValueError('该项已处理；如需改变决定，请重新预览。')
    issue = plan.issues[index - 1]
    copies, skipped = plan.copies, plan.skipped
    if action == 'add':
        if not issue.can_add:
            raise ValueError('同名文件冲突不能强行新增或覆盖')
        item = issue.item
        if any(c.digest == item.digest or (item.key and c.key == item.key) for c in copies):
            raise ValueError('新增计划已包含同曲，请标记同曲或跳过')
        paths = [item.destination] + ([item.lyric[1]] if item.lyric else [])
        entries, occupied = _target_entries(plan.target), set()
        for copy in copies + plan.lyrics:
            occupied.add(copy.destination.casefold())
            if copy.lyric: occupied.add(copy.lyric[1].casefold())
        if any(_path_conflict(path, entries, occupied) for path in paths):
            raise ValueError('目标同名文件或计划冲突，请重新预览')
        copies += (item,)
    else:
        skipped += (issue.item.source,)
    decisions = plan.decisions + ((index, action),)
    remaining = tuple(x.item.source + '（' + x.reason + '）' for i, x in enumerate(plan.issues, 1) if i not in dict(decisions))
    updated = replace(plan, copies=copies, skipped=skipped, decisions=decisions, conflicts=remaining)
    _capacity(updated.target, updated.bytes_required)
    return updated


def format_preview(plan):
    lines = [f'等待确认：新增 {len(plan.copies)} 首，自动跳过重复 {len(plan.duplicates)} 首，本次手动跳过 {len(plan.skipped)} 首，待处理 {len(plan.conflicts)} 首。',
             f'需要空间：{plan.bytes_required / 1024**2:.1f} MiB；SD 已有重复 {plan.existing_duplicates} 首（不删除）。',
             f'可补齐歌词 {len(plan.lyrics)} 份；SD 缺标签 {len(plan.unknown_target)} 首。']
    lines.extend('新增：' + c.source for c in plan.copies[:5])
    if plan.conflicts:
        lines.append('发「待处理」逐项查看；未处理项不会复制，不阻止其它新增项导入。')
    lines.append('回复「确认导入」执行当前新增计划，或「取消」。预览有效期 10 分钟，处理冲突不延长期限；SD 已有版本始终保留。')
    return '\n'.join(lines)
