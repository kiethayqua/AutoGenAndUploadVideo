from pathlib import Path
from types import SimpleNamespace

from auto_tiktok_orchestrator.tiktok_cli import TikTokCliPublisher


class FakeStdout:
    def __iter__(self):
        return iter(["Uploading video...\n", "[upload] Chunk 1/1 complete (4/4 bytes, 100.0%)\n"])


class FakeProcess:
    stdout = FakeStdout()

    def wait(self):
        return 0


def test_publish_streams_child_output(monkeypatch, tmp_path, capsys):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"data")
    calls = []

    def fake_popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return FakeProcess()

    monkeypatch.setattr("auto_tiktok_orchestrator.tiktok_cli.subprocess.Popen", fake_popen)
    publisher = TikTokCliPublisher(SimpleNamespace(tiktok_repo=Path("/tmp")))

    output = publisher.publish(username="user", video_path=video, title="title")

    captured = capsys.readouterr()
    assert "[upload] Chunk 1/1 complete" in captured.out
    assert "[upload] Chunk 1/1 complete" in output
    assert calls[0][0] == ["python3", "cli.py", "upload", "-u", "user", "-v", str(video), "-t", "title"]
    assert calls[0][1]["stderr"] is not None
