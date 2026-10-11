"""UUID-bound USB roles. No fallback to the system disk when configured."""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess

CONFIG_PATH = Path(__file__).with_name('storage.json')


@dataclass(frozen=True)
class Config:
    source_uuid: str
    target_uuid: str
    source_mount: Path
    target_mount: Path


def configured():
    return CONFIG_PATH.exists()


def load_config():
    if not configured():
        return None
    data = json.loads(CONFIG_PATH.read_text())
    source_uuid, target_uuid = data['source_uuid'], data['target_uuid']
    if any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z0-9-]+', x) for x in (source_uuid, target_uuid)):
        raise ValueError('请先绑定两个分区 UUID')
    if source_uuid.casefold() == target_uuid.casefold():
        raise ValueError('下载盘和播放器 SD 必须不同')
    mounts = [Path(data[key]).expanduser() for key in ('source_mount', 'target_mount')]
    for mount in mounts:
        if not mount.is_absolute() or mount == Path('/') or any(p.is_symlink() for p in (mount, *mount.parents)):
            raise ValueError('挂载目录必须为固定绝对路径且不能是符号链接')
    a, b = [x.resolve() for x in mounts]
    if a == b or a in b.parents or b in a.parents:
        raise ValueError('挂载目录不能相同或嵌套')
    return Config(source_uuid, target_uuid, a, b)


def _run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)


def _devices():
    data = json.loads(_run(['lsblk', '-J', '-e', '179', '-o', 'NAME,PATH,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINT,TRAN,TYPE']).stdout)
    out = []
    def walk(nodes, tran='', disk=''):
        for node in nodes:
            node = dict(node)
            node['tran'] = node.get('tran') or tran
            node['_disk'] = disk or node['path']
            out.append(node)
            walk(node.get('children') or [], node['tran'], node['_disk'])
    walk(data.get('blockdevices') or [])
    return out


def _select(uuid):
    matches = [d for d in _devices() if (d.get('uuid') or '').casefold() == uuid.casefold()]
    if not matches:
        raise ValueError('未找到绑定分区 ' + uuid + '，请插好指定设备')
    if len(matches) != 1:
        raise ValueError('分区 UUID 不唯一，拒绝操作')
    d = matches[0]
    if any(Path(str(d.get(key, ''))).name.startswith('mmcblk0') for key in ('name', 'path', '_disk')):
        raise ValueError('拒绝系统盘 mmcblk0')
    if d.get('tran') != 'usb' or not d.get('fstype'):
        raise ValueError('绑定设备不是 USB 文件系统')
    return d


def _check_pair(cfg):
    source, target = _select(cfg.source_uuid), _select(cfg.target_uuid)
    if source['path'] == target['path'] or source['_disk'] == target['_disk']:
        raise ValueError('下载盘和 SD 不能在同一个物理设备上')
    if target['fstype'].lower() not in {'vfat', 'exfat', 'msdos', 'fat32'}:
        raise ValueError('播放器 SD 需要 FAT/exFAT 文件系统')
    return source, target


def _mounted(uuid, mount):
    d = _select(uuid)
    if not d.get('mountpoint') or Path(d['mountpoint']).resolve() != mount:
        raise ValueError('设备挂载状态变化，请重新预览')
    if any(p.is_symlink() for p in (mount, *mount.parents)):
        raise ValueError('挂载目录变化为符号链接')
    return mount


def _mount(uuid, mount, *, protect_underlay=False):
    d = _select(uuid)
    if d.get('mountpoint'):
        return _mounted(uuid, mount)
    for other in _devices():
        if other.get('mountpoint') and Path(other['mountpoint']).resolve() == mount:
            raise ValueError('挂载目录被其它设备占用')
    if mount.exists() and any(mount.iterdir()):
        raise ValueError('未挂载的目录不为空，拒绝覆盖挂载')
    mount.mkdir(parents=True, exist_ok=True)
    if protect_underlay:
        # When unmounted, this empty directory must not accept fallback writes.
        mount.chmod(0o555)
    options = ['-o', f'uid={os.getuid()},gid={os.getgid()},umask=022'] if d['fstype'].lower() in {'vfat', 'exfat', 'msdos', 'fat32'} else []
    _run(['sudo', '-n', 'mount', *options, '-U', uuid, str(mount)])
    return _mounted(uuid, mount)


def source_directory(default, *, create=False):
    cfg = load_config()
    if cfg is None:
        return Path(default)
    mount = _mount(cfg.source_uuid, cfg.source_mount, protect_underlay=True)
    root = mount / 'inbox'
    if root.is_symlink():
        raise ValueError('下载目录不能是符号链接')
    if create:
        _mounted(cfg.source_uuid, cfg.source_mount)
        root.mkdir(exist_ok=True)
    return root


def prepare_import():
    cfg = load_config()
    if cfg is None:
        raise ValueError('请先配置下载 U 盘和播放器 SD 的 UUID')
    _check_pair(cfg)
    _mount(cfg.source_uuid, cfg.source_mount, protect_underlay=True)
    _mount(cfg.target_uuid, cfg.target_mount)
    if (cfg.source_mount / 'inbox').is_symlink():
        raise ValueError('下载目录不能是符号链接')
    # Import all music on the dedicated USB, including files outside inbox.
    return cfg, cfg.source_mount, cfg.target_mount


def verify_import(cfg):
    if load_config() != cfg:
        raise ValueError('存储配置变化，请重新预览')
    _check_pair(cfg)
    _mounted(cfg.source_uuid, cfg.source_mount)
    _mounted(cfg.target_uuid, cfg.target_mount)
    if (cfg.source_mount / 'inbox').is_symlink():
        raise ValueError('下载目录发生变化')


@contextmanager
def _pin(cfg, roles):
    handles = []
    try:
        for uuid, mount in roles:
            _mounted(uuid, mount)
            fd = os.open(mount, os.O_RDONLY | os.O_DIRECTORY)
            handles.append((uuid, mount, fd))

        def validate():
            if load_config() != cfg:
                raise ValueError('存储配置变化')
            for uuid, mount, fd in handles:
                _mounted(uuid, mount)
                pinned, current = os.fstat(fd), mount.stat()
                if (pinned.st_dev, pinned.st_ino) != (current.st_dev, current.st_ino):
                    raise ValueError('挂载设备身份变化')
        validate()
        yield validate
    finally:
        for uuid, mount, fd in handles:
            os.close(fd)


@contextmanager
def source_session(default, *, create=False):
    cfg = load_config()
    root = source_directory(default, create=create)
    if cfg is None:
        yield root, None
        return
    # Directory references pin the mounted filesystem during network/download work.
    with _pin(cfg, [(cfg.source_uuid, cfg.source_mount)]) as validate:
        yield root, validate


@contextmanager
def import_session(cfg):
    verify_import(cfg)
    with _pin(cfg, [(cfg.source_uuid, cfg.source_mount), (cfg.target_uuid, cfg.target_mount)]) as validate:
        def guard():
            verify_import(cfg)
            validate()
        yield guard


def eject_target():
    cfg = load_config()
    if cfg is None:
        raise ValueError('播放器 SD 尚未绑定')
    d = _select(cfg.target_uuid)
    if not d.get('mountpoint'):
        return '播放器 SD 已卸载，可以拔卡。'
    _mounted(cfg.target_uuid, cfg.target_mount)
    _run(['sync', '-f', str(cfg.target_mount)])
    _run(['sudo', '-n', 'umount', str(cfg.target_mount)])
    if _select(cfg.target_uuid).get('mountpoint'):
        raise ValueError('SD 仍然挂载，请勿拔卡')
    return '播放器 SD 已安全卸载，可以拔卡。下载 U 盘保持连接。'


def status():
    cfg = load_config()
    if cfg is None:
        return '当前使用树莓派本地 inbox；尚未启用双盘模式。'
    lines = ['【存储角色】']
    for label, uuid, mount in [('下载 U 盘', cfg.source_uuid, cfg.source_mount), ('播放器 SD', cfg.target_uuid, cfg.target_mount)]:
        try:
            d = _select(uuid)
            lines.append(f"{label}：{d['path']}，卷标={d.get('label') or '无'}，容量={d.get('size') or '未知'}，UUID={uuid}，挂载={d.get('mountpoint') or '未挂载'}")
        except ValueError as exc:
            lines.append(f'{label}：{exc}')
    lines.append('只从下载 U 盘向播放器 SD 导入；请发「导入预览」。')
    return '\n'.join(lines)
