from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from twitchbot.migration import InspectionError, LegacySourceInspector, build_migration_plan


def _inspector(tmp_path, reference="synthetic-source"):
    source, downloads = tmp_path / "source", tmp_path / "downloads"
    source.mkdir(); downloads.mkdir()
    return source, downloads, LegacySourceInspector(source, downloads, reference, clock=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc), monotonic=lambda: 1.0)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def test_inspection_is_safe_deterministic_and_never_import_ready(tmp_path):
    source, downloads, inspector = _inspector(tmp_path)
    _write(source / "config.json", '{"is_running":true,"enable_vod_download":false,"future_flag":1,"access_token":"SENTINEL_TOKEN"}')
    _write(source / "viewers.json", '{"private-viewer":{"name":"Never Report","future":1}}')
    _write(source / "history/stream_index.json", '{"private-stream":{"file_path":"nested/file.mp4","transient":1}}')
    _write(source / "history/stream_abc.jsonl", '{"timestamp":"2026-01-01T00:00:00Z","stream_info":{},"metrics":{},"future":true}\n\nnot-json\n')
    report = inspector.inspect(); safe = report.to_safe_mapping(); plan = build_migration_plan(report)
    assert [entry["name"] for entry in safe["manifest"]] == sorted(entry["name"] for entry in safe["manifest"])
    assert safe["credentials_redacted"] and safe["source_unchanged"]
    assert "SENTINEL_TOKEN" not in repr(report) and "Never Report" not in repr(safe) and "private-viewer" not in repr(safe)
    assert plan.import_ready is False and "domain_schema_unavailable" in plan.blockers and "credential_validation_required" in plan.blockers
    inspector.verify_unchanged(report)


def test_missing_malformed_unknown_and_jsonl_continuation_are_reported(tmp_path):
    source, _, inspector = _inspector(tmp_path)
    _write(source / "config.json", '{"ignored_users":"not-a-list","another":1}')
    _write(source / "history/stream_bad.jsonl", '{"timestamp":1}\n{"timestamp":"ok"}\n')
    report = inspector.inspect(); safe = report.to_safe_mapping()
    documents = {item["file"]: item for item in safe["documents"]}
    assert documents["viewers.json"]["status"] == "missing"
    assert any(issue["code"] == "invalid_shape" for issue in safe["issues"])
    assert any(issue["code"] == "invalid_type" for issue in safe["issues"])
    assert "another" in {item["field"] for item in safe["unknown_fields"]}


@pytest.mark.parametrize("name", ["../escape.mp4", "/outside.mp4", r"C:\outside.mp4", r"\\server\share\x.mp4"])
def test_vod_paths_are_safe_aggregate_only(tmp_path, name):
    source, _, inspector = _inspector(tmp_path)
    _write(source / "history/stream_index.json", json.dumps({"private": {"file_path": name}}))
    safe = inspector.inspect().to_safe_mapping()
    assert name not in repr(safe)
    assert safe["vod_path_counts"]


def test_mutation_and_symlink_sources_fail_closed(tmp_path):
    source, _, inspector = _inspector(tmp_path)
    config = source / "config.json"; _write(config, "{}")
    report = inspector.inspect(); config.write_text('{"unknown":1}', encoding="utf-8")
    with pytest.raises(InspectionError) as changed: inspector.verify_unchanged(report)
    assert changed.value.code == "source_changed"
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit synthetic directory symlink creation")
    with pytest.raises(InspectionError): LegacySourceInspector(linked, tmp_path / "downloads", "synthetic").inspect()


def test_unsupported_and_mtime_mutation_are_verified(tmp_path):
    source, _, inspector = _inspector(tmp_path); config = source / "config.json"; _write(config, "{}")
    report = inspector.inspect(); (source / "unsupported.txt").write_text("x")
    with pytest.raises(InspectionError) as caught: inspector.verify_unchanged(report)
    assert caught.value.code == "source_changed"
    (source / "unsupported.txt").unlink(); report = inspector.inspect()
    config.touch()
    with pytest.raises(InspectionError): inspector.verify_unchanged(report)


@pytest.mark.parametrize("payload,code", [(b'\xef\xbb\xbf{}', "bom"), (b'{"a":1,"a":2}', "malformed_json"), (b'{"x":NaN}', "malformed_json"), (b'[]', "document_not_object"), (b'\xff', "invalid_utf8")])
def test_strict_document_encodings_are_safe(tmp_path, payload, code):
    source, _, inspector = _inspector(tmp_path); (source / "config.json").write_bytes(payload)
    report = inspector.inspect(); assert any(issue["code"] == code for issue in report.to_safe_mapping()["issues"])


def test_vod_matrix_and_safe_relative_existing_target(tmp_path):
    source, downloads, inspector = _inspector(tmp_path); (downloads / "nested").mkdir(); (downloads / "nested" / "ok.mp4").write_bytes(b"x")
    entries = {"safe":{"file_path":"nested/ok.mp4"},"missing":{"file_path":"nested/missing.mp4"},"traversal":{"file_path":"../bad"},"empty":{"file_path":""},"outside":{"file_path":"/outside"}}
    _write(source / "history/stream_index.json", json.dumps(entries)); counts=inspector.inspect().to_safe_mapping()["vod_path_counts"]
    assert counts["safe_relative"] == 1 and counts["missing_target"] == 1 and counts["traversal"] == 1 and counts["empty"] == 1


def test_stream_index_is_not_jsonl_and_reports_vod(tmp_path):
    source, _, inspector = _inspector(tmp_path)
    _write(source / "history/stream_index.json", '{"private":{"file_path":"missing.mp4"}}')
    _write(source / "history/stream_one.jsonl", '{"timestamp":"x","stream_info":{},"metrics":{}}\n')
    report = inspector.inspect().to_safe_mapping(); docs = {item["file"]: item for item in report["documents"]}
    assert docs["history/stream_index.json"]["records_read"] == 1
    assert docs["history/stream_one.jsonl"]["records_read"] == 1
    assert report["vod_path_counts"]["missing_target"] == 1


def test_unsupported_metadata_changes_are_detected(tmp_path):
    source, _, inspector = _inspector(tmp_path); extra = source / "extra.txt"; extra.write_text("one")
    report = inspector.inspect(); extra.write_text("two changed")
    with pytest.raises(InspectionError): inspector.verify_unchanged(report)


def test_constructor_is_inert_and_rejects_bad_inputs(tmp_path):
    with pytest.raises(InspectionError): LegacySourceInspector("relative", tmp_path, "source")
    with pytest.raises(InspectionError): LegacySourceInspector(tmp_path, tmp_path, "bad reference")
    LegacySourceInspector(tmp_path / "does-not-exist", tmp_path / "also-missing", "synthetic")


def test_linklike_detection_has_deterministic_unit_path(tmp_path, monkeypatch):
    import stat
    class FakeStat: st_mode = stat.S_IFLNK
    monkeypatch.setattr(LegacySourceInspector, "_safe_lstat", staticmethod(lambda _path, _context: FakeStat()))
    with pytest.raises(InspectionError) as caught:
        LegacySourceInspector._link_or_special(tmp_path, "synthetic")
    assert caught.value.code == "unsafe_source_entry"


def test_inspection_guarded_offline_and_without_legacy_modules(tmp_path, monkeypatch):
    import os, socket, sqlite3, subprocess, threading, sys
    source, downloads, inspector = _inspector(tmp_path); _write(source / "config.json", "{}")
    def blocked(*_args, **_kwargs): raise AssertionError("forbidden boundary")
    monkeypatch.setattr(socket.socket, "connect", blocked); monkeypatch.setattr(threading.Thread, "start", blocked)
    monkeypatch.setattr(subprocess, "run", blocked); monkeypatch.setattr(sqlite3, "connect", blocked)
    monkeypatch.setattr(os, "getenv", blocked)
    legacy_before = {name for name in sys.modules if name == "config" or name.startswith("services") or name.startswith("routes")}
    report = inspector.inspect()
    assert report.source_reference == "synthetic-source"
    legacy_after = {name for name in sys.modules if name == "config" or name.startswith("services") or name.startswith("routes")}
    assert legacy_after == legacy_before


def test_entity_records_and_document_routing_are_explicit(tmp_path):
    source, _, inspector = _inspector(tmp_path)
    _write(source / "viewers.json", json.dumps({
        "private-id": {"name": "private", "is_sub": True, "total_visits": 2},
        "other-id": "not-an-object",
    }))
    _write(source / "history/stream_index.json", json.dumps({
        "private-stream": {"file_path": "missing.mp4", "sid": "transient", "legacy_extra": 1},
    }))
    _write(source / "history/stream_record.jsonl", '{"timestamp":"x","stream_info":{},"metrics":{}}\n')
    report = inspector.inspect().to_safe_mapping()
    documents = {item["file"]: item for item in report["documents"]}
    assert documents["viewers.json"] == {
        "file": "viewers.json", "status": "partial", "records_read": 2, "valid": 1, "rejected": 1,
    }
    assert documents["history/stream_index.json"]["records_read"] == 1
    assert documents["history/stream_record.jsonl"]["records_read"] == 1
    unknown = {(item["entity"], item["field"]) for item in report["unknown_fields"]}
    assert ("stream_index", "legacy_extra") in unknown
    assert "private-id" not in repr(report) and "private-stream" not in repr(report)


def test_json_document_limits_and_jsonl_nested_validation_continue(tmp_path, monkeypatch):
    import twitchbot.migration.inspector as module

    source, _, inspector = _inspector(tmp_path)
    _write(source / "config.json", "{}")
    _write(source / "viewers.json", "")
    _write(source / "history/stream_index.json", "{}")
    _write(
        source / "history/stream_nested.jsonl",
        '\n{"timestamp":"x","stream_info":{"unknown":1},"metrics":{"viewer_count":true}}\n'
        '{"timestamp":"x","stream_info":{},"metrics":{},"messages":[{"time":"x","user":"u","text":"secret chat","is_sub":false,"badges":"","new_field":1}]}\n',
    )
    report = inspector.inspect().to_safe_mapping()
    documents = {item["file"]: item for item in report["documents"]}
    assert documents["viewers.json"]["status"] == "invalid"
    assert documents["history/stream_nested.jsonl"]["valid"] == 1
    assert documents["history/stream_nested.jsonl"]["rejected"] == 2
    unknown = {(item["entity"], item["field"]) for item in report["unknown_fields"]}
    assert ("jsonl", "stream_info.unknown") in unknown
    assert ("jsonl", "messages.new_field") in unknown
    assert "secret chat" not in repr(report)

    monkeypatch.setattr(module, "_MAX_JSON", 1)
    too_large = inspector.inspect().to_safe_mapping()
    assert any(issue["code"] == "document_too_large" for issue in too_large["issues"])


def test_jsonl_line_limit_empty_document_and_mutation_during_parse(tmp_path, monkeypatch):
    import twitchbot.migration.inspector as module

    source, _, inspector = _inspector(tmp_path)
    _write(source / "config.json", "{}")
    _write(source / "history/stream_empty.jsonl", "")
    _write(source / "history/stream_long.jsonl", "{" + "x" * 32 + "}\n")
    monkeypatch.setattr(module, "_MAX_LINE", 8)
    safe = inspector.inspect().to_safe_mapping()
    assert any(issue["code"] == "empty_document" for issue in safe["issues"])
    assert any(issue["code"] == "line_too_large" for issue in safe["issues"])

    monkeypatch.undo()
    original = inspector._config
    def mutate_then_parse(*args, **kwargs):
        (source / "config.json").write_text('{"changed":true}', encoding="utf-8")
        return original(*args, **kwargs)
    monkeypatch.setattr(inspector, "_config", mutate_then_parse)
    with pytest.raises(InspectionError) as caught:
        inspector.inspect()
    assert caught.value.code == "source_changed"


def test_jsonl_optional_nested_types_reject_only_bad_lines_and_redact(tmp_path):
    source, _, inspector = _inspector(tmp_path)
    _write(source / "config.json", "{}")
    _write(
        source / "history/stream_nested_optional.jsonl",
        '{"timestamp":"x","stream_info":{"tags":[1]},"metrics":{}}\n'
        '{"timestamp":"x","stream_info":{},"metrics":{},"messages":[{"time":"x","user":"private-user","text":"private-chat","is_sub":false,"badges":{}}]}\n'
        '{"timestamp":"x","stream_info":{},"metrics":{},"events":[{"type":"bits","amount":"not-a-number"}]}\n'
        '{"timestamp":"x","stream_info":{"tags":["safe"]},"metrics":{},"messages":[{"time":"x","user":"u","text":"ok","is_sub":false,"badges":""}],"events":[{"type":"bits","amount":1,"user":"u","count":2}]}\n',
    )
    safe = inspector.inspect().to_safe_mapping()
    document = {item["file"]: item for item in safe["documents"]}["history/stream_nested_optional.jsonl"]
    assert (document["records_read"], document["valid"], document["rejected"]) == (4, 1, 3)
    rendered = repr(safe)
    assert "private-user" not in rendered and "private-chat" not in rendered and "not-a-number" not in rendered


def test_broken_vod_link_component_is_rejected_before_exists(tmp_path, monkeypatch):
    source, downloads, inspector = _inspector(tmp_path)
    _write(source / "config.json", "{}")
    linked = downloads / "broken-link"
    try:
        linked.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit synthetic broken symlink creation")
    _write(source / "history/stream_index.json", '{"private":{"file_path":"broken-link/video.mp4"}}')
    assert inspector.inspect().to_safe_mapping()["vod_path_counts"] == {"symlink_escape": 1}

    monkeypatch.setattr(
        LegacySourceInspector,
        "_path_is_linklike",
        staticmethod(lambda path: path.name == "deterministic-link"),
    )
    assert inspector._vod_components_safe(downloads / "deterministic-link" / "missing.mp4") is False


def test_privacy_determinism_and_guarded_inspection(tmp_path, monkeypatch):
    import os
    import sqlite3
    import socket
    import subprocess
    import threading

    source, downloads, inspector = _inspector(tmp_path)
    private_root = str(tmp_path)
    _write(source / "config.json", '{"access_token":"SENTINEL_TOKEN","malicious-key":"SENTINEL_VALUE"}')
    _write(source / "viewers.json", '{"SENTINEL_VIEWER_ID":{"name":"SENTINEL_NAME","memo":"SENTINEL_MEMO"}}')
    _write(source / "history/stream_index.json", json.dumps({"SENTINEL_STREAM_ID": {"file_path": str(downloads / "private.mp4")}}))

    def blocked(*_args, **_kwargs):
        raise AssertionError("forbidden boundary")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(threading.Thread, "start", blocked)
    monkeypatch.setattr(subprocess, "run", blocked)
    monkeypatch.setattr(sqlite3, "connect", blocked)
    monkeypatch.setattr(os, "getenv", blocked)
    original_open = Path.open
    def guarded_open(path, mode="r", *args, **kwargs):
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise AssertionError("filesystem write")
        return original_open(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded_open)
    for method in ("write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "replace"):
        monkeypatch.setattr(Path, method, blocked)

    report = inspector.inspect()
    second = LegacySourceInspector(
        source, downloads, "synthetic-source",
        clock=lambda: datetime(2026, 1, 2, tzinfo=timezone.utc), monotonic=lambda: 1.0,
    ).inspect()
    plan = build_migration_plan(report)
    assert report == second and plan == build_migration_plan(second)
    rendered = repr(report) + repr(report.to_safe_mapping()) + repr(plan) + repr(plan.to_safe_mapping())
    for private in ("SENTINEL_TOKEN", "SENTINEL_VALUE", "SENTINEL_VIEWER_ID", "SENTINEL_NAME", "SENTINEL_MEMO", "SENTINEL_STREAM_ID", private_root):
        assert private not in rendered
