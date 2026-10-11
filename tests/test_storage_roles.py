import json
from pathlib import Path
import pytest
import storage_roles as s


def config(tmp_path, monkeypatch):
    path=tmp_path/'storage.json'
    path.write_text(json.dumps({'source_uuid':'SOURCE','target_uuid':'TARGET',
                                'source_mount':str(tmp_path/'usb'),'target_mount':str(tmp_path/'sd')}))
    monkeypatch.setattr(s,'CONFIG_PATH',path)
    return path


def device(uuid, path, mountpoint=None, disk=None):
    return {'uuid':uuid,'path':path,'name':Path(path).name,'tran':'usb',
            'fstype':'vfat','mountpoint':mountpoint,'_disk':disk or path}


def test_missing_source_does_not_fall_back_to_local(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    monkeypatch.setattr(s,'_devices',lambda:[])
    with pytest.raises(ValueError,match='未找到'):
        s.source_directory(tmp_path/'local')
    assert not (tmp_path/'local').exists()


def test_no_config_preserves_local_mode(tmp_path,monkeypatch):
    monkeypatch.setattr(s,'CONFIG_PATH',tmp_path/'missing.json')
    assert s.source_directory(tmp_path/'local')==tmp_path/'local'


def test_uuid_identity_does_not_depend_on_device_order(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    source=device('SOURCE','/dev/sdz1',str(tmp_path/'usb'))
    target=device('TARGET','/dev/sda1',str(tmp_path/'sd'))
    monkeypatch.setattr(s,'_devices',lambda:[target,source])
    assert s._select('SOURCE')['path']=='/dev/sdz1'


def test_system_device_rejected_even_if_uuid_matches(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    monkeypatch.setattr(s,'_devices',lambda:[device('SOURCE','/dev/mmcblk0p1')])
    with pytest.raises(ValueError,match='系统盘'):
        s._select('SOURCE')


def test_duplicate_uuid_rejected(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    monkeypatch.setattr(s,'_devices',lambda:[device('SOURCE','/dev/sda1'),device('SOURCE','/dev/sdb1')])
    with pytest.raises(ValueError,match='不唯一'):
        s._select('SOURCE')


def test_same_roles_rejected(tmp_path,monkeypatch):
    path=config(tmp_path,monkeypatch)
    data=json.loads(path.read_text());data['target_uuid']='SOURCE';path.write_text(json.dumps(data))
    with pytest.raises(ValueError):s.load_config()


def test_unexpected_existing_mount_rejected(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    monkeypatch.setattr(s,'_devices',lambda:[device('SOURCE','/dev/sda1',str(tmp_path/'other'))])
    with pytest.raises(ValueError,match='挂载'):
        s.source_directory(tmp_path/'local')


def test_unmount_failure_does_not_report_safe(tmp_path,monkeypatch):
    import subprocess
    config(tmp_path,monkeypatch)
    mount=tmp_path/'sd';mount.mkdir()
    monkeypatch.setattr(s,'_devices',lambda:[device('TARGET','/dev/sdb1',str(mount))])
    def fail(*args,**kwargs):raise subprocess.CalledProcessError(1,['umount'])
    monkeypatch.setattr(s,'_run',fail)
    with pytest.raises(subprocess.CalledProcessError):s.eject_target()


def test_roles_on_same_physical_disk_rejected(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    monkeypatch.setattr(s,'_devices',lambda:[device('SOURCE','/dev/sda1',disk='/dev/sda'),device('TARGET','/dev/sda2',disk='/dev/sda')])
    with pytest.raises(ValueError,match='同一个物理'):
        s.prepare_import()


def test_config_change_invalidates_plan(tmp_path,monkeypatch):
    path=config(tmp_path,monkeypatch)
    cfg=s.load_config()
    data=json.loads(path.read_text());data['target_uuid']='NEW-CARD';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='配置变化'):
        s.verify_import(cfg)


def test_pinned_mount_identity_change_rejected(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    cfg=s.load_config();cfg.source_mount.mkdir()
    monkeypatch.setattr(s,'_mounted',lambda uuid,mount:mount)
    with s._pin(cfg,[(cfg.source_uuid,cfg.source_mount)]) as validate:
        cfg.source_mount.rename(tmp_path/'detached')
        cfg.source_mount.mkdir()
        with pytest.raises(ValueError,match='身份变化'):
            validate()


def test_source_underlay_is_readonly_before_mount(tmp_path,monkeypatch):
    config(tmp_path,monkeypatch)
    cfg=s.load_config()
    selected=device('SOURCE','/dev/sda1')
    monkeypatch.setattr(s,'_devices',lambda:[selected])
    def mount(args):
        assert cfg.source_mount.stat().st_mode & 0o222 == 0
        selected['mountpoint']=str(cfg.source_mount)
    monkeypatch.setattr(s,'_run',mount)
    try:
        assert s._mount(cfg.source_uuid,cfg.source_mount,protect_underlay=True)==cfg.source_mount
    finally:
        cfg.source_mount.chmod(0o755)
