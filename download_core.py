#!/usr/bin/env python3
"""Search and download one keyword via musicdl (first match).

Download flattening follows upstream MrsEWE44/musicDownload (2026-05-18):
musicdl writes to a temp dir, then we move audio/lrc into inbox with a clean name.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

INBOX_DEFAULT = Path.home() / "Music" / "inbox"

DEFAULT_SOURCES = [
    "NeteaseMusicClient",
    "QQMusicClient",
    "KuwoMusicClient",
    "KugouMusicClient",
]

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".opus"}


def sanitize_filename(filename: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", str(filename))


def _init_client(work_dir: Path, sources: List[str] | None = None):
    from musicdl import musicdl

    src = sources or DEFAULT_SOURCES
    work_dir.mkdir(parents=True, exist_ok=True)
    cfg = {s: {"search_size_per_source": 5, "work_dir": str(work_dir)} for s in src}
    return musicdl.MusicClient(music_sources=src, init_music_clients_cfg=cfg)


def _human_size(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(x)} {unit}"
            return f"{x:.2f} {unit}"
        x /= 1024
    return f"{n} B"


def _get_val(obj: Any, key: str, default: Any = ""):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default) if hasattr(obj, key) else default


def flatten_downloaded(downloaded: Any, target_dir: Path) -> Optional[Path]:
    """Move downloaded audio to inbox root, matching upstream DownloadThread."""
    target_dir.mkdir(parents=True, exist_ok=True)
    if downloaded is None:
        return None
    songs = downloaded if isinstance(downloaded, (list, tuple)) else [downloaded]
    last: Optional[Path] = None
    for song in songs:
        save_path = _get_val(song, "save_path")
        if not save_path or not os_path_exists(save_path):
            continue
        save_path = Path(save_path)
        song_name = _get_val(song, "song_name", "未知歌曲")
        singers = _get_val(song, "singers", "未知歌手")
        if isinstance(singers, list):
            singer = "&".join(str(s) for s in singers)
        else:
            singer = str(singers)
        album = _get_val(song, "album", "")
        identifier = _get_val(song, "identifier", "")
        ext = save_path.suffix.lstrip(".") or str(_get_val(song, "ext", "mp3") or "mp3")
        parts = [str(song_name), singer]
        if album:
            parts.append(str(album))
        if identifier:
            parts.append(str(identifier))
        base_name = sanitize_filename("-".join(parts))
        new_audio_path = target_dir / f"{base_name}.{ext}"
        try:
            if new_audio_path.exists():
                new_audio_path.unlink()
            shutil.move(str(save_path), str(new_audio_path))
            last = new_audio_path
        except Exception as e:
            print(f"移动音频文件失败 {save_path}: {e}")
            continue
        old_lrc = save_path.with_suffix(".lrc")
        if old_lrc.exists():
            new_lrc = target_dir / f"{base_name}.lrc"
            try:
                if new_lrc.exists():
                    new_lrc.unlink()
                shutil.move(str(old_lrc), str(new_lrc))
            except Exception as e:
                print(f"移动歌词文件失败: {e}")
    return last


def os_path_exists(p: Any) -> bool:
    try:
        return Path(p).exists()
    except Exception:
        return False


def _fresh_audio(path: Path, root: Path, before=None) -> bool:
    if path.suffix.lower() not in AUDIO_EXTS or not path.is_file():
        return False
    if any(p.is_symlink() for p in (path, *path.parents)):
        return False
    if root.resolve() not in path.resolve().parents:
        return False
    stat = path.stat()
    return stat.st_size > 0 and (before is None or before.get(path.resolve()) != (stat.st_size, stat.st_mtime_ns))


def _newest_audio_since(root: Path, since: float, before=None) -> Optional[Path]:
    newest: Optional[Path] = None
    newest_mtime = since - 2
    if not root.is_dir():
        return None
    for p in root.rglob("*"):
        if not _fresh_audio(p, root, before):
            continue
        stat = p.stat()
        m = stat.st_mtime
        if m >= newest_mtime:
            newest, newest_mtime = p, m
    return newest


def inspect_audio(path: Path, song_info: Any = None) -> str:
    size = _human_size(path.stat().st_size)
    fmt = path.suffix.lstrip(".").upper() or "未知"
    bitrate = "未知"
    duration = ""
    info = song_info or {}
    meta_size = info.get("file_size") or info.get("filesize") or ""
    meta_br = info.get("bitrate") or info.get("bit_rate") or info.get("rate") or ""
    try:
        from tinytag import TinyTag

        tag = TinyTag.get(str(path))
        if tag.bitrate:
            bitrate = f"{int(round(tag.bitrate))} kbps"
        if tag.duration:
            sec = int(tag.duration)
            duration = f"{sec // 60}:{sec % 60:02d}"
        if tag.samplerate:
            fmt = f"{fmt} / {int(tag.samplerate)} Hz"
    except Exception:
        if meta_br:
            bitrate = str(meta_br)
        if meta_size:
            size = f"{size}（源站标注 {meta_size}）"
    if bitrate == "未知" and meta_br:
        bitrate = str(meta_br)
    lines = [
        f"文件：{path.name}",
        f"大小：{size}",
        f"码率：{bitrate}",
        f"格式：{fmt}",
    ]
    if duration:
        lines.append(f"时长：{duration}")
    return "\n".join(lines)


def _title_from_info(info: Any, fallback: str = "") -> str:
    name = info.get("song_name", fallback) or fallback or "未知歌曲"
    singers = info.get("singers", "")
    if isinstance(singers, list):
        singers = ", ".join(str(s) for s in singers)
    return f"{name} - {singers}".strip(" -")


def search_candidates(keyword: str, limit: int = 3, work_dir: Path = INBOX_DEFAULT, *, validate=None, sources=None, diverse=False) -> List[dict]:
    keyword = keyword.strip()
    if not keyword:
        return []
    if validate:
        validate()
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = work_dir / ".musicdl_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    if sources and any(source not in DEFAULT_SOURCES for source in sources):
        raise ValueError("不支持的音乐源")
    client = _init_client(temp_dir, sources) if sources else _init_client(temp_dir)
    results = client.search(keyword=keyword)
    if validate:
        validate()
    buckets = []
    seen = set()
    for source, rows in (results or {}).items():
        bucket = []
        for item in rows or []:
            if not callable(getattr(item, "get", None)):
                continue
            title = _title_from_info(item, keyword)
            identity = (source, str(item.get("identifier") or title), str(item.get("album") or ""),
                        str(item.get("ext") or ""), str(item.get("bitrate") or "")) if diverse else title
            if identity in seen:
                continue
            seen.add(identity)
            bucket.append({"title": title, "info": item, "source": source})
        buckets.append(bucket)
    if diverse:
        # Give each source a turn; preserve alternatives across different sources.
        out = [bucket[index] for index in range(max((len(x) for x in buckets), default=0))
               for bucket in buckets if index < len(bucket)]
    else:
        out = [item for bucket in buckets for item in bucket]
    return out[:max(0, limit)]


def download_song_info(song_info: Any, work_dir: Path = INBOX_DEFAULT, *, validate=None) -> Tuple[str, Path, str]:
    if validate:
        validate()
    started = time.time()
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = work_dir / ".musicdl_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    client = _init_client(temp_dir)
    before = {p.resolve(): (p.stat().st_size, p.stat().st_mtime_ns)
              for p in temp_dir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTS}
    downloaded = client.download(song_infos=[song_info])
    if validate:
        validate()
    songs = downloaded if isinstance(downloaded, (list, tuple)) else [downloaded]
    fresh = []
    for song in songs:
        raw_path = _get_val(song, "save_path")
        if not raw_path or not isinstance(raw_path, (str, Path)):
            continue
        path = Path(raw_path)
        if not _fresh_audio(path, temp_dir, before):
            continue
        fresh.append(song)
    audio = flatten_downloaded(fresh, work_dir)
    if audio is None:
        audio = _newest_audio_since(temp_dir, started, before)
        if audio:
            meta = {key: song_info.get(key) for key in ("song_name", "singers", "album", "identifier")}
            meta["save_path"] = audio
            audio = flatten_downloaded(meta, work_dir)
    title = _title_from_info(song_info)
    if audio:
        details = inspect_audio(audio, song_info)
    else:
        raise RuntimeError("下载源未生成可确认的新音频文件，请重新搜索并换一个来源。")
    return title, work_dir, details


def search_and_download(keyword: str, work_dir: Path = INBOX_DEFAULT, *, validate=None) -> Tuple[str, Path, str]:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("歌名为空")
    kwargs = {"validate": validate} if validate else {}
    found = search_candidates(keyword, limit=1, work_dir=work_dir, **kwargs)
    if not found:
        raise RuntimeError(f"没有搜到：{keyword}")
    return download_song_info(found[0]["info"], work_dir, **kwargs)
