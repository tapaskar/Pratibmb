"""Tests for the Gmail MBOX importer."""
from __future__ import annotations

import mailbox
from pathlib import Path

from pratibmb.importers.gmail import GmailMbox, _normalize_subject


def _make_mbox(path: Path, messages: list[dict]) -> Path:
    """Create an mbox file with the given list of raw message dicts.

    Each dict should have: from_, to, subject, body, date, message_id.
    Optional: references, in_reply_to.
    """
    mbox_path = path / "Mail.mbox"
    mbox = mailbox.mbox(str(mbox_path))
    for m in messages:
        msg = mailbox.mboxMessage()
        msg["From"] = m.get("from_", "unknown@example.com")
        msg["To"] = m.get("to", "recipient@example.com")
        msg["Subject"] = m.get("subject", "")
        msg["Date"] = m.get("date", "Mon, 01 Jan 2024 10:00:00 +0000")
        msg["Message-ID"] = f"<{m['message_id']}>"
        if "references" in m:
            msg["References"] = m["references"]
        if "in_reply_to" in m:
            msg["In-Reply-To"] = m["in_reply_to"]
        msg.set_payload(m.get("body", ""), charset="utf-8")
        mbox.add(msg)
    mbox.close()
    return mbox_path


def test_basic_parse(tmp_path: Path):
    mbox_path = _make_mbox(tmp_path, [
        {
            "from_": "Tapas <tapas@example.com>",
            "to": "Sarah <sarah@example.com>",
            "subject": "Hello",
            "body": "Hey Sarah!",
            "date": "Mon, 15 Jan 2024 10:00:00 +0000",
            "message_id": "msg001@example.com",
        },
        {
            "from_": "Sarah <sarah@example.com>",
            "to": "Tapas <tapas@example.com>",
            "subject": "Re: Hello",
            "body": "Hey Tapas!",
            "date": "Mon, 15 Jan 2024 10:05:00 +0000",
            "message_id": "msg002@example.com",
            "in_reply_to": "<msg001@example.com>",
            "references": "<msg001@example.com>",
        },
    ])
    imp = GmailMbox()
    assert imp.detect(mbox_path)
    msgs = list(imp.load(mbox_path, self_name="Tapas"))
    assert len(msgs) == 2
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Tapas"
    assert msgs[0].text == "Hey Sarah!"
    assert msgs[0].source == "gmail"
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "Sarah"


def test_threading(tmp_path: Path):
    """Messages linked by References/In-Reply-To share the same thread_id."""
    mbox_path = _make_mbox(tmp_path, [
        {
            "from_": "A <a@example.com>",
            "subject": "Topic",
            "body": "start",
            "date": "Mon, 01 Jan 2024 09:00:00 +0000",
            "message_id": "root@example.com",
        },
        {
            "from_": "B <b@example.com>",
            "subject": "Re: Topic",
            "body": "reply 1",
            "date": "Mon, 01 Jan 2024 09:10:00 +0000",
            "message_id": "reply1@example.com",
            "in_reply_to": "<root@example.com>",
            "references": "<root@example.com>",
        },
        {
            "from_": "A <a@example.com>",
            "subject": "Re: Re: Topic",
            "body": "reply 2",
            "date": "Mon, 01 Jan 2024 09:20:00 +0000",
            "message_id": "reply2@example.com",
            "in_reply_to": "<reply1@example.com>",
            "references": "<root@example.com> <reply1@example.com>",
        },
        {
            "from_": "C <c@example.com>",
            "subject": "Unrelated",
            "body": "different thread",
            "date": "Mon, 01 Jan 2024 10:00:00 +0000",
            "message_id": "other@example.com",
        },
    ])
    msgs = list(GmailMbox().load(mbox_path, self_name="A"))
    # First 3 should share a thread, 4th is separate
    thread_ids = [m.thread_id for m in msgs]
    assert thread_ids[0] == thread_ids[1] == thread_ids[2]
    assert thread_ids[3] != thread_ids[0]


def test_self_detection_by_email(tmp_path: Path):
    """Self-detection works when self_name matches the email address."""
    mbox_path = _make_mbox(tmp_path, [
        {
            "from_": "Some Display Name <tapas@gmail.com>",
            "subject": "Test",
            "body": "hello",
            "date": "Mon, 01 Jan 2024 10:00:00 +0000",
            "message_id": "selftest@example.com",
        },
    ])
    msgs = list(GmailMbox().load(mbox_path, self_name="tapas"))
    assert msgs[0].author == "self"


def test_empty_body_skipped(tmp_path: Path):
    """Messages with empty bodies are not yielded."""
    mbox_path = _make_mbox(tmp_path, [
        {
            "from_": "A <a@example.com>",
            "subject": "Empty",
            "body": "",
            "date": "Mon, 01 Jan 2024 10:00:00 +0000",
            "message_id": "empty@example.com",
        },
        {
            "from_": "A <a@example.com>",
            "subject": "Not empty",
            "body": "has content",
            "date": "Mon, 01 Jan 2024 10:01:00 +0000",
            "message_id": "notempty@example.com",
        },
    ])
    msgs = list(GmailMbox().load(mbox_path, self_name="nobody"))
    assert len(msgs) == 1
    assert msgs[0].text == "has content"


def test_html_fallback(tmp_path: Path):
    """When only HTML body is available, tags are stripped."""
    mbox_path = path = tmp_path / "html.mbox"
    mbox = mailbox.mbox(str(mbox_path))
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["From"] = "A <a@example.com>"
    msg["To"] = "B <b@example.com>"
    msg["Subject"] = "HTML only"
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    msg["Message-ID"] = "<html01@example.com>"
    html_part = MIMEText("<p>Hello <b>world</b></p>", "html")
    msg.attach(html_part)
    mbox.add(mailbox.mboxMessage(msg))
    mbox.close()

    msgs = list(GmailMbox().load(mbox_path, self_name="nobody"))
    assert len(msgs) == 1
    assert "Hello" in msgs[0].text
    assert "world" in msgs[0].text
    assert "<p>" not in msgs[0].text


def test_detect_rejects_non_mbox(tmp_path: Path):
    txt = tmp_path / "notes.txt"
    txt.write_text("this is not an mbox\n")
    assert GmailMbox().detect(txt) is False

    csv = tmp_path / "data.csv"
    csv.write_text("a,b,c\n1,2,3\n")
    assert GmailMbox().detect(csv) is False


def test_detect_directory_with_mbox(tmp_path: Path):
    """detect() finds .mbox files inside a directory tree."""
    takeout = tmp_path / "Takeout" / "Mail"
    takeout.mkdir(parents=True)
    _make_mbox(takeout, [
        {
            "from_": "A <a@example.com>",
            "subject": "Test",
            "body": "hello",
            "date": "Mon, 01 Jan 2024 10:00:00 +0000",
            "message_id": "dir@example.com",
        },
    ])
    # Point detect at the top-level Takeout dir
    assert GmailMbox().detect(tmp_path / "Takeout") is True


def test_normalize_subject():
    assert _normalize_subject("Re: Hello") == "Hello"
    assert _normalize_subject("Fwd: Re: Hello") == "Hello"
    assert _normalize_subject("RE: FW: RE: Topic") == "Topic"
    assert _normalize_subject("Hello") == "Hello"
    assert _normalize_subject("Re:Re: nested") == "nested"


def test_thread_name_strips_prefixes(tmp_path: Path):
    mbox_path = _make_mbox(tmp_path, [
        {
            "from_": "A <a@example.com>",
            "subject": "Re: Fwd: Dinner plans",
            "body": "sure",
            "date": "Mon, 01 Jan 2024 10:00:00 +0000",
            "message_id": "tn@example.com",
        },
    ])
    msgs = list(GmailMbox().load(mbox_path, self_name="nobody"))
    assert msgs[0].thread_name == "Dinner plans"
