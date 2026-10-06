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


def _newest_audio_since(root: Path, since: float) -> Optional[Path]:
    newest: Optional[Path] = None
    newest_mtime = since - 2
    if not root.is_dir():
        return None
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in AUDIO_EXTS:
            continue
        m = p.stat().st_mtime
        if m >= newest_mtime:
            newest, newest_mtime = p, m
    return newest


def inspect_audio(path: Path, song_info: Optional[dict] = None) -> str:
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


def search_and_download(keyword: str, work_dir: Path = INBOX_DEFAULT) -> Tuple[str, Path, str]:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("歌名为空")
    started = time.time()
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = work_dir / ".musicdl_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    client = _init_client(temp_dir)
    results = client.search(keyword=keyword)
    first = None
    for rows in results.values():
        if rows:
            first = rows[0]
            break
    if not first:
        raise RuntimeError(f"没有搜到：{keyword}")
    name = first.get("song_name", keyword)
    singers = first.get("singers", "")
    if isinstance(singers, list):
        singers = ", ".join(str(s) for s in singers)
    downloaded = client.download(song_infos=[first])
    audio = flatten_downloaded(downloaded, work_dir)
    if audio is None:
        audio = _newest_audio_since(work_dir, started)
    title = f"{name} - {singers}"
    if audio:
        details = inspect_audio(audio, first if isinstance(first, dict) else None)
    else:
        details = "未找到本地下载文件，无法读取大小/码率。"
    return title, work_dir, details
