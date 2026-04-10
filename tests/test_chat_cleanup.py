"""Tests for the LLM output post-processor."""
from pratibmb.llm import _clean


def test_strip_markdown_bold():
    assert _clean("**hey** how are you?") == "hey how are you?"


def test_strip_meta_preamble():
    raw = "Okay, here is my response:\nhey ma, all good"
    assert _clean(raw) == "hey ma, all good"


def test_strip_reasoning_trailer():
    raw = "hey bro just tired\n\nReasoning behind the response:\n- I used the past messages"
    assert _clean(raw) == "hey bro just tired"


def test_strip_headers_and_bullets():
    raw = "# Title\n- one\n- two"
    assert _clean(raw) == "Title\none\ntwo"


def test_strip_wrapping_quotes():
    assert _clean('"just a normal reply"') == "just a normal reply"


def test_strip_smart_quotes():
    assert _clean('\u201cjust a normal reply\u201d') == "just a normal reply"


def test_strip_hr_separator():
    raw = "hey bro\n\n---\n\nReasoning:\n- stuff"
    assert _clean(raw) == "hey bro"


def test_idempotent_clean_reply():
    assert _clean("yeah i'm fine bro, tired but ok") == "yeah i'm fine bro, tired but ok"


def test_truncate_long_reply():
    raw = "One. Two. Three. Four. Five. Six."
    result = _clean(raw)
    assert result == "One. Two. Three. Four."


def test_strip_ai_identity_preamble():
    raw = "As an AI assistant, I can help.\nActual reply here."
    result = _clean(raw)
    assert result == "Actual reply here."
