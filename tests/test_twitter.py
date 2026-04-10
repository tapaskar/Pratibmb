"""Tests for the Twitter / X archive importer."""
from __future__ import annotations
import json
from pathlib import Path
from pratibmb.importers.twitter import TwitterArchive, _load_js


def _write_js(path: Path, var_name: str, data):
    """Write a Twitter archive JS file with the window.YTD prefix."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"window.YTD.{var_name}.part0 = {json.dumps(data)}")


def test_load_js_strips_prefix(tmp_path: Path):
    f = tmp_path / "test.js"
    _write_js(f, "tweets", [{"a": 1}])
    result = _load_js(f)
    assert result == [{"a": 1}]


def test_detect_tweets_only(tmp_path: Path):
    _write_js(tmp_path / "data" / "tweets.js", "tweets", [])
    imp = TwitterArchive()
    assert imp.detect(tmp_path)


def test_detect_dms_only(tmp_path: Path):
    _write_js(tmp_path / "data" / "direct-messages.js", "direct_messages", [])
    imp = TwitterArchive()
    assert imp.detect(tmp_path)


def test_detect_no_data_dir(tmp_path: Path):
    imp = TwitterArchive()
    assert not imp.detect(tmp_path)


def test_tweet_timestamp_parsing(tmp_path: Path):
    _write_js(tmp_path / "data" / "account.js", "account", [
        {"account": {"accountId": "12345"}},
    ])
    _write_js(tmp_path / "data" / "tweets.js", "tweets", [
        {"tweet": {
            "full_text": "Hello twitter!",
            "created_at": "Mon Feb 03 14:30:00 +0000 2020",
        }},
        {"tweet": {
            "full_text": "Another tweet",
            "created_at": "Tue Mar 10 09:00:00 +0000 2020",
        }},
    ])
    imp = TwitterArchive()
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 2
    assert msgs[0].text == "Hello twitter!"
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Tapas"
    assert msgs[0].source == "twitter"
    assert msgs[0].thread_id == "twitter_post::self"
    assert msgs[0].timestamp.year == 2020
    assert msgs[0].timestamp.month == 2
    assert msgs[0].timestamp.day == 3


def test_dm_sender_resolution(tmp_path: Path):
    _write_js(tmp_path / "data" / "account.js", "account", [
        {"account": {"accountId": "12345"}},
    ])
    _write_js(tmp_path / "data" / "direct-messages.js", "direct_messages", [
        {"dmConversation": {
            "conversationId": "conv-abc",
            "messages": [
                {"messageCreate": {
                    "senderId": "12345",
                    "text": "hey there",
                    "createdAt": "2020-06-15T10:00:00.000Z",
                }},
                {"messageCreate": {
                    "senderId": "99999",
                    "text": "hi!",
                    "createdAt": "2020-06-15T10:01:00.000Z",
                }},
            ],
        }},
    ])
    imp = TwitterArchive()
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 2
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Tapas"
    assert msgs[0].thread_id == "twitter_dm::conv-abc"
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "99999"


def test_tweets_and_dms_together(tmp_path: Path):
    _write_js(tmp_path / "data" / "account.js", "account", [
        {"account": {"accountId": "12345"}},
    ])
    _write_js(tmp_path / "data" / "tweets.js", "tweets", [
        {"tweet": {
            "full_text": "a tweet",
            "created_at": "Mon Feb 03 14:30:00 +0000 2020",
        }},
    ])
    _write_js(tmp_path / "data" / "direct-messages.js", "direct_messages", [
        {"dmConversation": {
            "conversationId": "conv-1",
            "messages": [
                {"messageCreate": {
                    "senderId": "12345",
                    "text": "dm text",
                    "createdAt": "2020-06-15T10:00:00.000Z",
                }},
            ],
        }},
    ])
    imp = TwitterArchive()
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 2
    tweets = [m for m in msgs if m.thread_id == "twitter_post::self"]
    dms = [m for m in msgs if m.thread_id.startswith("twitter_dm::")]
    assert len(tweets) == 1
    assert len(dms) == 1
