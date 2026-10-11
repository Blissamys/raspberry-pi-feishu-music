from pathlib import Path
import pytest
import library_sync as sync


def put(root, rel, content=b'a'):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def metadata(path):
    return ('晴天', '周杰伦') if path.stem.startswith('same') else None


def test_preview_deduplicates_by_title_artist_and_preserves_sd(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'same-new.flac', b'new-format')
    old = put(target, 'same-old.mp3', b'old-format')
    plan = sync.preview(source, target, tag_reader=metadata)
    assert not plan.copies
    assert len(plan.duplicates) == 1
    assert old.read_bytes() == b'old-format'


def test_source_duplicates_copied_once_and_cache_excluded(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'same-one.flac')
    put(source, 'same-two.mp3', b'b')
    put(source, 'same-one.lrc', b'lyrics')
    put(source, 'cache.pkl')
    put(source, '.musicdl_temp/incomplete.flac')
    target.mkdir()
    plan = sync.preview(source, target, tag_reader=metadata)
    assert len(plan.copies) == 1
    assert len(plan.duplicates) == 1
    sync.execute(plan)
    assert (target/'same-one.flac').exists()
    assert (target/'same-one.lrc').exists()
    assert not (target/'cache.pkl').exists()
    assert not (target/'.musicdl_temp').exists()
    assert not sync.preview(source, target, tag_reader=metadata).copies


def test_unknown_tags_report_conflict_but_identical_content_skips(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'unknown.flac', b'x')
    put(target, 'existing.flac', b'x')
    put(source, 'unidentified.mp3', b'y')
    plan = sync.preview(source, target, tag_reader=lambda path: None)
    assert not plan.copies
    assert len(plan.duplicates) == 1
    assert len(plan.conflicts) == 1


def test_changed_target_rejects_confirmation(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'same.flac')
    target.mkdir()
    plan = sync.preview(source, target, tag_reader=metadata)
    put(target, 'external.mp3')
    with pytest.raises(ValueError, match='变化'):
        sync.execute(plan)
    assert not (target/'same.flac').exists()


def test_filename_collision_not_overwritten(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'same.flac', b'new')
    old = put(target, 'same.flac', b'old')
    def tags(path):
        return (path.read_bytes().decode(), 'artist')
    plan = sync.preview(source, target, tag_reader=tags)
    assert not plan.copies
    assert len(plan.conflicts) == 1
    assert old.read_bytes() == b'old'


def test_nested_or_equal_roots_rejected(tmp_path):
    with pytest.raises(ValueError):
        sync.preview(tmp_path, tmp_path)
    with pytest.raises(ValueError):
        sync.preview(tmp_path, tmp_path/'nested')


def test_source_change_rejects_confirmation(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    song = put(source, 'same.flac')
    target.mkdir()
    plan = sync.preview(source, target, tag_reader=metadata)
    song.write_bytes(b'changed')
    with pytest.raises(ValueError, match='变化'):
        sync.execute(plan)


def test_insufficient_capacity_rejected(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'same.flac')
    target.mkdir()
    monkeypatch.setattr(sync.shutil, 'disk_usage', lambda path: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match='空间'):
        sync.preview(source, target, tag_reader=metadata)


def test_race_at_publish_does_not_overwrite_existing_file(tmp_path):
    temp = put(tmp_path, '.copy.part', b'new')
    destination = put(tmp_path, 'song.flac', b'old')
    with pytest.raises(FileExistsError):
        sync._publish(temp, destination)
    assert destination.read_bytes() == b'old'


def test_symlink_parent_rejected_before_creating_directories(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(outside, target_is_directory=True)
    source = put(tmp_path, 'source.flac')
    with pytest.raises(ValueError, match='符号链接'):
        sync._copy_verified(source, link / 'new-dir/song.flac', sync._digest(source))
    assert not (outside / 'new-dir').exists()


def test_preexisting_sd_duplicates_are_reported_not_deleted(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    source.mkdir()
    a = put(target, 'same-a.mp3', b'a')
    b = put(target, 'same-b.flac', b'b')
    plan = sync.preview(source, target, tag_reader=metadata)
    assert plan.existing_duplicates == 1
    sync.execute(plan)
    assert a.exists() and b.exists()


def test_artist_order_and_separator_do_not_add_duplicate(tmp_path):
    source, target = tmp_path/'usb', tmp_path/'sd'
    put(source, 'source.flac', b'a')
    put(target, 'target.mp3', b'b')
    def tags(path):
        return ('そばにいるね', '青山テルマ、SoulJa' if path.parent == source else 'SoulJa, 青山テルマ')
    plan = sync.preview(source, target, tag_reader=tags)
    assert not plan.copies
    assert len(plan.duplicates) == 1


def test_expired_plan_refused(tmp_path, monkeypatch):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same.flac');target.mkdir()
    plan=sync.preview(source,target,tag_reader=metadata)
    monkeypatch.setattr(sync.time,'monotonic',lambda:plan.created+601)
    with pytest.raises(ValueError,match='过期'):sync.execute(plan)
    assert not list(target.iterdir())


def test_device_check_failure_prevents_copy(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same.flac');target.mkdir()
    plan=sync.preview(source,target,tag_reader=metadata)
    def disconnected():raise ValueError('设备变化')
    with pytest.raises(ValueError,match='设备变化'):sync.execute(plan,verify=disconnected)
    assert not list(target.iterdir())


def test_unknown_target_tags_block_ambiguous_new_song(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same-new.flac',b'new-encoding')
    put(target,'unidentified.mp3',b'old-encoding')
    plan=sync.preview(source,target,tag_reader=metadata)
    assert not plan.copies
    assert plan.conflicts
    assert plan.unknown_target == ('unidentified.mp3',)


def test_retry_repairs_missing_lyric_for_exact_content_audio(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same.flac',b'audio')
    put(source,'same.lrc',b'lyric')
    put(target,'same.flac',b'audio')
    plan=sync.preview(source,target,tag_reader=metadata)
    assert not plan.copies
    assert len(plan.lyrics)==1
    sync.execute(plan)
    assert (target/'same.lrc').read_bytes()==b'lyric'
    assert (target/'same.flac').read_bytes()==b'audio'


def test_review_conflict_adds_to_plan_only_then_confirms(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'unlabelled.flac',b'new');target.mkdir()
    plan=sync.preview(source,target,tag_reader=lambda p:None)
    assert '缺少' in sync.conflict_details(plan,1)
    updated=sync.resolve_conflict(plan,1,'add')
    assert len(updated.copies)==1 and not updated.conflicts
    assert not list(target.iterdir())
    assert updated.created==plan.created
    sync.execute(updated)
    assert (target/'unlabelled.flac').read_bytes()==b'new'


def test_conflict_ids_stable_after_skip_and_same_decisions(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'a.mp3',b'a');put(source,'b.mp3',b'b');target.mkdir()
    plan=sync.preview(source,target,tag_reader=lambda p:None)
    plan=sync.resolve_conflict(plan,1,'skip')
    assert 'b.mp3' in sync.conflict_details(plan,2)
    plan=sync.resolve_conflict(plan,2,'same')
    assert not plan.copies and not plan.conflicts
    assert len(plan.skipped)==2
    with pytest.raises(ValueError,match='已处理'):
        sync.resolve_conflict(plan,1,'add')


def test_manual_add_cannot_override_filename_collision(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same.flac',b'new');old=put(target,'same.flac',b'old')
    plan=sync.preview(source,target,tag_reader=lambda p:(p.read_bytes().decode(),'artist'))
    with pytest.raises(ValueError,match='同名'):
        sync.resolve_conflict(plan,1,'add')
    assert old.read_bytes()==b'old'


def test_manual_decision_cannot_bypass_expiry(tmp_path,monkeypatch):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'a.mp3');target.mkdir()
    plan=sync.preview(source,target,tag_reader=lambda p:None)
    monkeypatch.setattr(sync.time,'monotonic',lambda:plan.created+601)
    with pytest.raises(ValueError,match='过期'):sync.resolve_conflict(plan,1,'add')


def test_ambiguous_same_song_cannot_be_manually_added_twice(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same-a.flac',b'a');put(source,'same-b.mp3',b'b')
    put(target,'unlabelled.mp3',b'c')
    plan=sync.preview(source,target,tag_reader=metadata)
    plan=sync.resolve_conflict(plan,1,'add')
    with pytest.raises(ValueError,match='同曲'):
        sync.resolve_conflict(plan,2,'add')


def test_import_reports_copy_and_verify_stages(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same.flac',b'audio');target.mkdir()
    events=[]
    plan=sync.preview(source,target,tag_reader=metadata,progress=events.append)
    assert any('扫描中' in e for e in events)
    sync.execute(plan,progress=events.append)
    copy=next(i for i,e in enumerate(events) if '复制中' in e)
    verify=next(i for i,e in enumerate(events) if '校验中' in e)
    assert copy<verify


def test_failed_lyric_reports_already_completed_audio(tmp_path,monkeypatch):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'same.flac',b'audio');put(source,'same.lrc',b'lyric');target.mkdir()
    plan=sync.preview(source,target,tag_reader=metadata)
    original=sync._copy_verified
    def fail_lyric(source,*args,**kwargs):
        if source.suffix=='.lrc':raise OSError('test failure')
        return original(source,*args,**kwargs)
    monkeypatch.setattr(sync,'_copy_verified',fail_lyric)
    with pytest.raises(sync.ImportInterrupted) as caught:sync.execute(plan)
    assert caught.value.completed==1
    assert (target/'same.flac').exists()


def test_parent_file_collision_is_not_manually_addable(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'unknown.mp3',b'new');put(target,'music',b'not a directory')
    plan=sync.preview(source,target,tag_reader=lambda p:None,dest_subdir='MUSIC')
    assert not plan.issues[0].can_add
    with pytest.raises(ValueError,match='同名'):
        sync.resolve_conflict(plan,1,'add')


def test_parent_file_created_after_preview_rejects_manual_add(tmp_path):
    source,target=tmp_path/'usb',tmp_path/'sd'
    put(source,'unknown.mp3',b'new');target.mkdir()
    plan=sync.preview(source,target,tag_reader=lambda p:None,dest_subdir='MUSIC')
    put(target,'MUSIC',b'file')
    with pytest.raises(ValueError,match='冲突'):
        sync.resolve_conflict(plan,1,'add')
