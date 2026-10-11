#!/usr/bin/env python3
"""Export downloaded music to an Iriver / Astell&Kern player in USB MSC (U-disk) mode.

Flow: detect block device -> mount FAT/exFAT -> rsync inbox -> sync -> optional unmount.

Usage:
    python3 export_to_player.py
    python3 export_to_player.py --source ~/Music/inbox --dest-subdir MUSIC
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional


# USB vendor IDs commonly used by Iriver / Astell & Kern (extend after `lsusb`).
KNOWN_VENDOR_IDS = {
    "4102",  # iRiver
    "0bb4",  # some AK / HTC-related IDs appear on certain models
}

MOUNT_POINT = Path("/media/iriver")
INBOX_DEFAULT = Path.home() / "Music" / "inbox"
DEST_SUBDIR_DEFAULT = "MUSIC"  # change if the player uses MUSIC, Music, or root
FSTAB_LABEL = "IRIVER"
AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg", ".opus"}
LIST_CAP = 40


@dataclass
class BlockCandidate:
    name: str
    path: str
    size: str
    fstype: str
    label: str
    uuid: str
    mountpoint: Optional[str]
    tran: str
    vendor: str
    model: str
    rm: bool
    children: List["BlockCandidate"] = field(default_factory=list)

    @property
    def is_mounted(self) -> bool:
        return bool(self.mountpoint)


def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def lsblk_json() -> dict:
    out = run(["lsblk", "-J", "-o", "NAME,PATH,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT,TRAN,VENDOR,MODEL,RM,TYPE"])
    return json.loads(out.stdout)


def flatten_blocks(nodes: list, parent_tran: str = "", parent_vendor: str = "", parent_model: str = "", parent_rm: bool = False) -> List[BlockCandidate]:
    result: List[BlockCandidate] = []
    for n in nodes:
        tran = (n.get("tran") or parent_tran or "").strip()
        vendor = (n.get("vendor") or parent_vendor or "").strip()
        model = (n.get("model") or parent_model or "").strip()
        rm = bool(n.get("rm") if n.get("rm") is not None else parent_rm)
        cand = BlockCandidate(
            name=n.get("name") or "",
            path=n.get("path") or f"/dev/{n.get('name')}",
            size=str(n.get("size") or ""),
            fstype=(n.get("fstype") or "") or "",
            label=(n.get("label") or "") or "",
            uuid=(n.get("uuid") or "") or "",
            mountpoint=n.get("mountpoint"),
            tran=tran,
            vendor=vendor,
            model=model,
            rm=rm,
        )
        children = n.get("children") or []
        cand.children = flatten_blocks(children, tran, vendor, model, rm)
        result.append(cand)
        result.extend(cand.children)
    return result


def is_system_device(c: BlockCandidate) -> bool:
    return c.name.startswith("mmcblk0") or Path(c.path).name.startswith("mmcblk0")


def looks_like_player_partition(c: BlockCandidate) -> bool:
    if is_system_device(c):
        return False
    if c.tran and c.tran.lower() != "usb":
        return False
    # Prefer partitions with a filesystem, not the whole disk.
    if not c.fstype:
        return False
    fstype = c.fstype.lower()
    if fstype not in {"vfat", "fat32", "exfat", "msdos", "fuseblk"}:
        return False
    label = (c.label or "").upper()
    if FSTAB_LABEL and label == FSTAB_LABEL.upper():
        return True
    if "IRIVER" in label or "ASTELL" in label or "AK70" in label or "KANN" in label:
        return True
    # Removable USB FAT/exFAT is a reasonable candidate on a dedicated Pi.
    return c.rm or c.tran.lower() == "usb"


def list_usb_partitions() -> List[BlockCandidate]:
    data = lsblk_json()
    blocks = flatten_blocks(data.get("blockdevices") or [])
    return [b for b in blocks if looks_like_player_partition(b)]


def _human_size(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if x < 1024 or unit == "GB":
            return f"{int(x)} {unit}" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{n} B"


def list_audio_files(root: Path) -> List[Path]:
    if not root.is_dir():
        return []
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            files.append(p)
    return sorted(files, key=lambda x: str(x).lower())


def _format_audio_block(title: str, root: Path, missing_hint: str) -> List[str]:
    lines = [title]
    if not root.exists():
        lines.append(missing_hint)
        return lines
    files = list_audio_files(root)
    lines.append(f"共 {len(files)} 首")
    if not files:
        lines.append("（没有音频文件）")
        return lines
    for p in files[:LIST_CAP]:
        try:
            rel = p.relative_to(root)
        except ValueError:
            rel = p.name
        try:
            sz = _human_size(p.stat().st_size)
        except OSError:
            sz = "?"
        lines.append(f"· {rel}  {sz}")
    extra = len(files) - LIST_CAP
    if extra > 0:
        lines.append(f"... 还有 {extra} 首未列出")
    return lines


def _unlink_audio_and_lrc(path: Path, inbox: Path | None = None) -> None:
    lrc = path.with_suffix(".lrc")
    path.unlink()
    if lrc.exists():
        lrc.unlink()
    parent = path.parent
    root = (inbox or INBOX_DEFAULT).resolve()
    while parent.resolve() != root and root in parent.resolve().parents:
        try:
            next(parent.iterdir())
            break
        except StopIteration:
            if parent.name == ".musicdl_temp":
                break
            parent.rmdir()
            parent = parent.parent
        except OSError:
            break


def delete_local_audio(keyword: str, inbox: Path | None = None) -> str:
    root = inbox or INBOX_DEFAULT
    keyword = keyword.strip()
    files = list_audio_files(root)
    if not files:
        return "本地 inbox 里没有歌曲。"
    if keyword in {"全部", "所有", "*"}:
        removed = []
        for p in files:
            try:
                rel = p.relative_to(root)
                _unlink_audio_and_lrc(p, root)
                removed.append(str(rel))
            except OSError as e:
                return f"删除失败：{p.name} {e}"
        return "已删除本地全部 {} 首：\n{}".format(len(removed), "\n".join(f"· {n}" for n in removed[:LIST_CAP]))
    if not keyword:
        return "请写成：删除本地 晴天\n清空全部请发：删除本地全部"
    matches = [p for p in files if keyword.lower() in str(p.relative_to(root)).lower()]
    if not matches:
        # Prefer a literal title; only then remove spoken/listing decorations.
        cleaned = re.sub(r"^(?:那首|这首)\s*", "", keyword).removeprefix("·").strip()
        extensions = "|".join(re.escape(ext) for ext in sorted(AUDIO_EXTS))
        listing = re.fullmatch(
            rf"(.+(?:{extensions}))\s+\d+(?:\.\d+)?\s+(?:B|KB|MB|GB)",
            cleaned,
            re.I,
        )
        if listing:
            # A copied list entry identifies one relative path, not a substring.
            target = listing.group(1).lower()
            matches = [p for p in files if str(p.relative_to(root)).lower() == target]
        elif cleaned and cleaned not in {"全部", "所有", "*"}:
            matches = [p for p in files if cleaned.lower() in str(p.relative_to(root)).lower()]
    if not matches:
        return f"本地没有匹配「{keyword}」的歌曲。先发「盘」查看文件名。"
    names = []
    for p in matches:
        rel = str(p.relative_to(root))
        _unlink_audio_and_lrc(p, root)
        names.append(rel)
    return "已从本地删除 {} 首：\n{}".format(len(names), "\n".join(f"· {n}" for n in names))


def format_library_list() -> str:
    """Feishu「盘」：本地 inbox + USB SD 上的歌曲。"""
    lines: List[str] = []
    lines.extend(
        _format_audio_block(
            f"【树莓派本地】{INBOX_DEFAULT}",
            INBOX_DEFAULT,
            "目录不存在（尚未下载过）。",
        )
    )
    lines.append("")

    try:
        parts = list_usb_partitions()
        picked = pick_player_partition(parts) if parts else None
        if not picked:
            lines.append("【SD 卡】未检测到 USB 上的 FAT/exFAT 分区。请把卡插入读卡器后再发「盘」。")
            return "\n".join(lines)

        mounted_before = bool(picked.mountpoint)
        mounted = ensure_mount(picked)
        music_root = mounted / DEST_SUBDIR_DEFAULT
        scan_root = music_root if music_root.is_dir() else mounted
        lines.extend(
            _format_audio_block(
                f"【SD 卡】{picked.path} {picked.fstype} {picked.size} 卷标={picked.label or '无'}\n挂载：{mounted}",
                scan_root,
                f"无法读取 {scan_root}",
            )
        )
        if not mounted_before:
            if unmount_if_ours(mounted):
                lines.append("（本次只读已卸载，导入前请再插稳读卡器）")
    except Exception as e:
        lines.append(f"【SD 卡】读取失败：{e}")
    return "\n".join(lines)


def format_usb_list() -> str:
    parts = list_usb_partitions()
    if not parts:
        return "未检测到 USB 上的 FAT/exFAT 分区。请把 SD 插入读卡器后再发「盘」。"
    lines = ["可写入的 USB 分区："]
    picked = pick_player_partition(parts)
    for p in parts:
        mark = " ← 将导入到这里" if picked and p.path == picked.path else ""
        mount = p.mountpoint or "未挂载"
        lines.append(
            f"- {p.path} {p.fstype} {p.size} 卷标={p.label or '无'} 挂载={mount}{mark}"
        )
    lines.append("导入前请确认箭头指向读卡器里的那张 SD，不要指向系统盘。")
    return "\n".join(lines)


def pick_player_partition(blocks: List[BlockCandidate]) -> Optional[BlockCandidate]:
    parts = [b for b in blocks if looks_like_player_partition(b)]
    if not parts:
        return None
    labeled = [p for p in parts if (p.label or "").upper() == FSTAB_LABEL.upper() or "IRIVER" in (p.label or "").upper()]
    return labeled[0] if labeled else parts[0]


def ensure_mount(part: BlockCandidate, mount_point: Path = MOUNT_POINT) -> Path:
    if is_system_device(part):
        raise ValueError("拒绝访问系统盘 mmcblk0 及其分区")
    if part.mountpoint:
        return Path(part.mountpoint)
    mount_point.mkdir(parents=True, exist_ok=True)
    fstype = part.fstype.lower()
    if fstype in {"vfat", "fat32", "msdos"}:
        run(["sudo", "mount", "-t", "vfat", "-o", "uid=1000,gid=1000,utf8,umask=000", part.path, str(mount_point)])
    elif fstype == "exfat":
        run(["sudo", "mount", "-t", "exfat", "-o", "uid=1000,gid=1000,umask=000", part.path, str(mount_point)])
    else:
        run(["sudo", "mount", "-o", "uid=1000,gid=1000", part.path, str(mount_point)])
    return mount_point


def dest_dir(mounted_root: Path, subdir: str) -> Path:
    if not subdir:
        return mounted_root
    d = mounted_root / subdir
    d.mkdir(parents=True, exist_ok=True)
    return d


def rsync_inbox(
    source: Path,
    dest: Path,
    progress: Optional[Callable[[str], None]] = None,
) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"下载目录不存在: {source}")
    cmd = [
        "rsync",
        "-av",
        "--progress",
        "--modify-window=1",
        "--exclude", "*.pkl",
        "--exclude", "*.pyc",
        "--exclude", ".DS_Store",
        "--exclude", ".musicdl_temp",
        "--include", "*/",
        "--include", "*.flac",
        "--include", "*.mp3",
        "--include", "*.m4a",
        "--include", "*.wav",
        "--include", "*.aac",
        "--include", "*.ogg",
        "--include", "*.opus",
        "--include", "*.lrc",
        "--exclude", "*",
        f"{source}/",
        f"{dest}/",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        if progress:
            progress(line.rstrip())
        else:
            print(line, end="")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"rsync 失败，退出码 {rc}")
    run(["sync"])


def unmount_if_ours(mounted: Path, configured: Path = MOUNT_POINT) -> bool:
    if mounted.resolve() != configured.resolve():
        return False
    run(["sudo", "-n", "umount", str(configured)])
    return True


def export_once(
    source: Path = INBOX_DEFAULT,
    dest_subdir: str = DEST_SUBDIR_DEFAULT,
    unmount: bool = False,
    progress: Optional[Callable[[str], None]] = None,
) -> Path:
    data = lsblk_json()
    blocks = flatten_blocks(data.get("blockdevices") or [])
    part = pick_player_partition(blocks)
    if not part:
        raise RuntimeError(
            "未找到艾利和 U 盘分区。请用 USB-C 连接并切到 MSC/U 盘模式，然后运行: lsblk -f"
        )
    if progress:
        progress(f"检测到 {part.path} ({part.fstype} {part.label or '无卷标'} {part.size})")
    mounted = ensure_mount(part)
    target = dest_dir(mounted, dest_subdir)
    if progress:
        progress(f"同步 {source} → {target}")
    rsync_inbox(source, target, progress=progress)
    if unmount:
        if not unmount_if_ours(mounted):
            raise RuntimeError("曲目已复制，但未自动卸载非专用挂载点；请先安全弹出，勿直接拔卡")
        if progress:
            progress("已卸载，可以拔线")
    else:
        if progress:
            progress("导入完成，请先安全弹出再拔线")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="将本机 inbox 同步到艾利和 MSC 分区")
    parser.add_argument("--source", type=Path, default=INBOX_DEFAULT)
    parser.add_argument("--dest-subdir", default=DEST_SUBDIR_DEFAULT)
    parser.add_argument("--unmount", action="store_true", help="同步后卸载 /media/iriver")
    args = parser.parse_args()
    try:
        export_once(args.source, args.dest_subdir, unmount=args.unmount)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
