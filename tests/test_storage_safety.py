from unittest.mock import Mock

import pytest

import export_to_player as e


def candidate(name, **kwargs):
    return e.flatten_blocks([dict(name=name, path='/dev/' + name,
                                 fstype='vfat', label='IRIVER', **kwargs)])[0]


@pytest.mark.parametrize('name', ['mmcblk0', 'mmcblk0p1', 'mmcblk0p2'])
@pytest.mark.parametrize('tran', ['', 'usb'])
def test_system_disk_never_selected(name, tran):
    part = candidate(name, tran=tran, rm=True)
    assert not e.looks_like_player_partition(part)
    assert e.pick_player_partition([part]) is None


def test_system_device_path_rejected_even_if_name_differs():
    part = candidate('sdd1', tran='usb')
    part.path = '/dev/mmcblk0p1'
    assert not e.looks_like_player_partition(part)


@pytest.mark.parametrize('mounted', [None, '/mock/already-mounted'])
def test_mount_entry_refuses_system_disk(tmp_path, monkeypatch, mounted):
    part = candidate('mmcblk0p1', tran='', mountpoint=mounted)
    run = Mock()
    monkeypatch.setattr(e, 'run', run)
    with pytest.raises(ValueError, match='mmcblk0'):
        e.ensure_mount(part, tmp_path / 'must-not-create')
    run.assert_not_called()
    assert not (tmp_path / 'must-not-create').exists()


def test_usb_reader_still_selected():
    part = candidate('sdd1', tran='usb')
    assert e.pick_player_partition([part]) is part


def test_rsync_copies_audio_but_not_cache(tmp_path, monkeypatch):
    source = tmp_path / 'inbox'
    dest = tmp_path / 'player'
    source.mkdir()
    dest.mkdir()
    for rel in ('song.flac', 'song.lrc', 'cached.pkl', 'nested/song.mp3',
                'nested/cached.pkl', '.musicdl_temp/unfinished.flac'):
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test fixture')
    monkeypatch.setattr(e, 'run', Mock())  # Avoid global sync; rsync itself is real.
    e.rsync_inbox(source, dest)
    copied = {str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()}
    assert copied == {'song.flac', 'song.lrc', 'nested/song.mp3'}


def test_legacy_unmount_requires_success(monkeypatch):
    import subprocess
    def run(args,check=True):
        if check:raise subprocess.CalledProcessError(1,args)
        return subprocess.CompletedProcess(args,1)
    monkeypatch.setattr(e,'run',run)
    with pytest.raises(subprocess.CalledProcessError):e.unmount_if_ours(e.MOUNT_POINT)


def test_legacy_unmount_does_not_claim_unmanaged_mount(tmp_path):
    assert e.unmount_if_ours(tmp_path) is False
