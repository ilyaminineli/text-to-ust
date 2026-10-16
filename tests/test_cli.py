import pytest

from hiro_ust import cli

class FakeConfig:
    def __init__(self, **values):
        self.values = values


class FakeProcessor:
    def __init__(self, config):
        self.config = config

    def process_lyrics(self, lyrics, project_name, output_format):
        return f"{project_name}|{output_format}|{lyrics}"


def _patch_processor(monkeypatch):
    monkeypatch.setattr(cli, "GeneratorConfig", FakeConfig)
    monkeypatch.setattr(cli, "HiroUSTProcessor", FakeProcessor)


def test_cli_generates_from_text_without_opening_gui(monkeypatch, tmp_path, capsys):
    _patch_processor(monkeypatch)
    output = tmp_path / "demo.ust"
    result = cli.main(
        [
            "hiro-ust",
            "--lyrics",
            "あ い う",
            "--output",
            str(output),
            "--format",
            "ust",
            "--root",
            "62",
        ]
    )
    assert result == 0
    assert output.read_text(encoding="utf-8") == "demo|ust|あ い う"
    assert str(output) in capsys.readouterr().out


def test_cli_generates_from_utf8_file(monkeypatch, tmp_path):
    _patch_processor(monkeypatch)
    source = tmp_path / "lyrics.txt"
    source.write_text("こころ", encoding="utf-8")
    output = tmp_path / "from_file.ustx"
    result = cli.main(
        [
            "hiro-ust",
            "--lyrics-file",
            str(source),
            "--output",
            str(output),
        ]
    )
    assert result == 0
    assert output.read_text(encoding="utf-8") == "from_file|ustx|こころ"


def test_cli_requires_one_lyrics_source(monkeypatch, tmp_path):
    _patch_processor(monkeypatch)
    with pytest.raises(SystemExit) as exc:
        cli.main(["hiro-ust", "--output", str(tmp_path / "missing.ust")])
    assert exc.value.code == 2
