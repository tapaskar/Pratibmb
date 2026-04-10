"""
Twitter / X archive importer.

Handles the official "Download your data" archive.  The archive contains JS
files with a ``window.YTD.<name>.part0 = [...]`` prefix that must be stripped
before JSON-parsing.

Supported files:
  - data/tweets.js      (your own tweets)
  - data/direct-messages.js   (DM conversations)
  - data/account.js     (account metadata, used for sender resolution in DMs)
"""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from ..schema import Message

_JS_PREFIX = re.compile(r"^window\.YTD\.\w+\.part\d+\s*=\s*")

_TWEET_TS_FMT = "%a %b %d %H:%M:%S %z %Y"


def _load_js(path: Path) -> Any:
    """Read a Twitter archive JS file, strip the assignment prefix, return JSON."""
    content = path.read_text(encoding="utf-8", errors="replace")
    content = _JS_PREFIX.sub("", content, count=1)
    return json.loads(content)


class TwitterArchive:
    name = "twitter_archive"

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        data_dir = path / "data"
        if not data_dir.is_dir():
            return False
        return (data_dir / "tweets.js").exists() or (
            data_dir / "direct-messages.js"
        ).exists()

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        data_dir = path / "data"

        # Resolve account ID for DM sender matching
        account_id: str = ""
        account_js = data_dir / "account.js"
        if account_js.exists():
            try:
                acct_data = _load_js(account_js)
                for entry in acct_data:
                    acc = entry.get("account", entry)
                    if "accountId" in acc:
                        account_id = acc["accountId"]
                        break
            except Exception:
                pass

        # --- Tweets ---
        tweets_js = data_dir / "tweets.js"
        if tweets_js.exists():
            yield from self._load_tweets(tweets_js, self_name)

        # --- Direct messages ---
        dm_js = data_dir / "direct-messages.js"
        if dm_js.exists():
            yield from self._load_dms(dm_js, self_name, account_id)

    def _load_tweets(
        self, path: Path, self_name: str,
    ) -> Iterator[Message]:
        try:
            data = _load_js(path)
        except Exception:
            return
        for entry in data:
            tweet = entry.get("tweet", entry)
            text = tweet.get("full_text", "")
            if not text:
                continue
            ts_raw = tweet.get("created_at", "")
            try:
                ts = datetime.strptime(ts_raw, _TWEET_TS_FMT)
            except ValueError:
                continue
            yield Message(
                source="twitter",
                timestamp=ts,
                author="self",
                author_name=self_name,
                text=text,
                thread_id="twitter_post::self",
                thread_name="Tweets",
            )

    def _load_dms(
        self, path: Path, self_name: str, account_id: str,
    ) -> Iterator[Message]:
        try:
            data = _load_js(path)
        except Exception:
            return
        for conv_wrapper in data:
            conv = conv_wrapper.get("dmConversation", conv_wrapper)
            conv_id = conv.get("conversationId", "")
            thread_id = f"twitter_dm::{conv_id}"
            for msg_wrapper in conv.get("messages", []):
                mc = msg_wrapper.get("messageCreate")
                if mc is None:
                    continue
                text = mc.get("text", "")
                if not text:
                    continue
                ts_raw = mc.get("createdAt", "")
                try:
                    # Python 3.9 doesn't handle 'Z' suffix
                    ts = datetime.fromisoformat(
                        ts_raw.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    continue
                sender_id = mc.get("senderId", "")
                is_self = sender_id == account_id
                yield Message(
                    source="twitter",
                    timestamp=ts,
                    author="self" if is_self else "other",
                    author_name=self_name if is_self else sender_id,
                    text=text,
                    thread_id=thread_id,
                    thread_name="",
                )
