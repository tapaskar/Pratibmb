"""Tests for the WhatsApp .txt importer."""
from __future__ import annotations
from pathlib import Path
import textwrap
from pratibmb.importers.whatsapp import WhatsAppTxt


BRACKET_SAMPLE = textwrap.dedent("""\
    [12/03/2022, 19:45:12] Tapas: hey
    [12/03/2022, 19:45:30] Tapas: you free tonight?
    [12/03/2022, 19:46:02] Sarah: yeah
    this is a
    multi-line reply
    [12/03/2022, 19:47:10] Tapas: \u200eimage omitted
    [12/03/2022, 19:48:00] Sarah: \u200e<Media omitted>
    [12/03/2022, 19:49:00] Tapas: k see you at 8
""")

DASH_SAMPLE = textwrap.dedent("""\
    03/04/2023, 10:15 - Messages and calls are end-to-end encrypted.
    03/04/2023, 10:15 - Tapas: morning
    03/04/2023, 10:16 - Mom: good morning beta
    how are you?
    03/04/2023, 10:17 - Tapas: all good ma
""")


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / f"WhatsApp Chat with {name}.txt"
    p.write_text(body, encoding="utf-8")
    return p


def test_bracket_format_parses_all_messages(tmp_path: Path):
    p = _write(tmp_path, "Sarah", BRACKET_SAMPLE)
    imp = WhatsAppTxt()
    assert imp.detect(p)
    msgs = list(imp.load(p, self_name="Tapas"))
    assert len(msgs) == 6
    assert msgs[0].text == "hey"
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Tapas"
    assert msgs[0].thread_name == "Sarah"
    assert msgs[2].text == "yeah\nthis is a\nmulti-line reply"
    assert msgs[2].author == "other"
    # media rows collapse to empty text + media_ref
    assert msgs[3].media_ref == "media"
    assert msgs[3].text == ""
    assert msgs[4].media_ref == "media"
    assert msgs[5].text == "k see you at 8"


def test_dash_format_skips_system_lines(tmp_path: Path):
    p = _write(tmp_path, "Mom", DASH_SAMPLE)
    imp = WhatsAppTxt()
    assert imp.detect(p)
    msgs = list(imp.load(p, self_name="Tapas"))
    # system line must be skipped
    assert len(msgs) == 3
    assert msgs[0].text == "morning"
    assert msgs[1].text.startswith("good morning beta")
    assert "how are you?" in msgs[1].text
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "Mom"
    assert msgs[2].author == "self"
    assert msgs[0].year == 2023


def test_detect_rejects_non_whatsapp(tmp_path: Path):
    p = tmp_path / "notes.txt"
    p.write_text("this is a plain text file\nnot a chat export\n")
    assert WhatsAppTxt().detect(p) is False


def test_thread_id_stable_across_messages(tmp_path: Path):
    p = _write(tmp_path, "Raj", BRACKET_SAMPLE)
    msgs = list(WhatsAppTxt().load(p, self_name="Tapas"))
    ids = {m.thread_id for m in msgs}
    assert len(ids) == 1
    assert "Raj" in next(iter(ids))
