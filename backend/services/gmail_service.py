"""Gmail integration: send news alerts (SMTP), poll for YES/NO replies (IMAP),
and send draft-ready notifications.

Credentials come from GMAIL_ADDRESS / GMAIL_APP_PASSWORD in .env (a Google App
Password, not the account password). Uses Python's built-in smtplib + imaplib.
"""
from __future__ import annotations

import datetime
import email
import imaplib
import re
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Any, Dict, List

from core import alerts
from core.config import config
from core.logger import get_logger

log = get_logger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
IMAP_HOST = "imap.gmail.com"

ALERT_SUBJECT_PREFIX = "🔴 BREAKING AI NEWS"
STORY_ID_MARKER = "Story-ID:"  # machine-readable line embedded in alert bodies


def _require_creds() -> None:
    if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_ADDRESS / GMAIL_APP_PASSWORD are not configured in .env"
        )


def _send(subject: str, body: str, to_addr: str | None = None) -> None:
    """Send a plain-text email via Gmail SMTP over SSL."""
    _require_creds()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.GMAIL_ADDRESS
    msg["To"] = to_addr or config.GMAIL_ADDRESS
    msg.set_content(body)
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)
        log.info("Sent email %r to %s", subject[:50], msg["To"])
    except (smtplib.SMTPException, OSError) as exc:
        log.exception("Failed to send email %r", subject[:50])
        raise RuntimeError(f"Failed to send email: {exc}") from exc


# --------------------------------------------------------------------------- #
# Outbound: news alerts
# --------------------------------------------------------------------------- #
def _alert_body(story: Dict[str, Any]) -> str:
    return (
        f"A new breaking AI/tech story is trending and may be worth a video.\n\n"
        f"HEADLINE: {story.get('title', '')}\n"
        f"SOURCE: {story.get('source', '')}\n"
        f"PUBLISHED: {story.get('published_date', 'n/a')}\n\n"
        f"SUMMARY:\n{story.get('summary', '')}\n\n"
        f"--- AI ANALYSIS ---\n"
        f"Viral score:       {story.get('viral_score', '?')}/10\n"
        f"Relevance score:   {story.get('relevance_score', '?')}/10\n"
        f"Estimated views:   {story.get('estimated_views', '?')}\n"
        f"Recommended length:{story.get('recommended_duration', 3)} minutes\n"
        f"Suggested title:   {story.get('suggested_title', '')}\n\n"
        f"ARTICLE: {story.get('url', '')}\n\n"
        f"================ ACTION REQUIRED ================\n"
        f"Reply YES to produce this video automatically.\n"
        f"Reply NO to skip.\n"
        f"(Just reply with YES or NO as the first word.)\n\n"
        f"{STORY_ID_MARKER} {story.get('story_id', '')}\n"
    )


def send_news_alert(stories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Send one alert email per story and record each as pending in alerts.json.

    Returns the list of stored alert records.
    """
    records: List[Dict[str, Any]] = []
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    for story in stories:
        subject = f"{ALERT_SUBJECT_PREFIX} — Action Required: {story.get('title', '')}"
        try:
            _send(subject, _alert_body(story))
            record = alerts.add_alert(story, timestamp=timestamp, status="pending")
            records.append(record)
        except RuntimeError as exc:
            log.error("Could not send alert for %r: %s", story.get("title", "")[:50], exc)
    log.info("Sent %d/%d news alerts", len(records), len(stories))
    return records


def send_draft_ready_notification(title: str, youtube_draft_url: str) -> None:
    """Notify the creator that a private YouTube draft is ready to review."""
    subject = f"✅ Video Draft Ready: {title}"
    body = (
        f"Your auto-generated video is ready as a private YouTube draft.\n\n"
        f"TITLE: {title}\n"
        f"DRAFT URL: {youtube_draft_url}\n\n"
        f"Next steps:\n"
        f"1. Open the draft URL to preview the video and thumbnail.\n"
        f"2. Edit details if needed.\n"
        f"3. Set visibility to Public when you're happy to publish.\n"
    )
    _send(subject, body)


def send_failure_alert(context: str, error: str) -> None:
    """Notify the creator that a scheduled job failed."""
    try:
        _send(
            subject=f"⚠️ Video Generator job failed: {context}",
            body=f"A scheduled job failed.\n\nContext: {context}\n\nError:\n{error}\n",
        )
    except RuntimeError:
        log.error("Could not send failure alert email")


# --------------------------------------------------------------------------- #
# Inbound: reply polling
# --------------------------------------------------------------------------- #
def _decode(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001
        return value or ""


def _body_text(msg: email.message.Message) -> str:
    """Extract the best-effort plain-text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                part.get("Content-Disposition", "")
            ):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
        # Fall back to any text part.
        for part in msg.walk():
            if part.get_content_type().startswith("text/"):
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", "replace")
    return str(msg.get_payload())


def _extract_story_id(body: str) -> str | None:
    """Pull the embedded Story-ID out of a quoted reply thread."""
    m = re.search(rf"{re.escape(STORY_ID_MARKER)}\s*([A-Za-z0-9]+)", body)
    return m.group(1).strip() if m else None


def _extract_decision(body: str) -> str | None:
    """Return 'YES' or 'NO' based on the first meaningful word of the reply."""
    for line in body.splitlines():
        stripped = line.strip()
        # Skip quoted lines and the embedded marker.
        if not stripped or stripped.startswith(">") or STORY_ID_MARKER in stripped:
            continue
        first = re.sub(r"[^a-zA-Z]", "", stripped.split()[0]).upper() if stripped.split() else ""
        if first in ("YES", "Y"):
            return "YES"
        if first in ("NO", "N"):
            return "NO"
        # First real content line wasn't a decision — stop scanning.
        break
    return None


def check_replies() -> List[Dict[str, Any]]:
    """Poll the inbox for replies to alert emails.

    Looks for unseen messages whose subject contains 'Re: 🔴 BREAKING AI NEWS',
    extracts a YES/NO decision and the embedded story_id, marks them read, and
    returns the parsed decisions.
    """
    _require_creds()
    results: List[Dict[str, Any]] = []
    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST)
        imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
    except (imaplib.IMAP4.error, OSError) as exc:
        log.error("IMAP login failed: %s", exc)
        return results

    try:
        imap.select("INBOX")
        # Unseen messages only, so we don't re-process old replies.
        status, data = imap.search(None, "UNSEEN")
        if status != "OK":
            return results
        ids = data[0].split()
        log.info("Reply check: %d unseen messages", len(ids))
        for mid in ids:
            status, msg_data = imap.fetch(mid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode(msg.get("Subject", ""))
            if "Re:" not in subject or ALERT_SUBJECT_PREFIX not in subject:
                continue  # leave non-matching mail unread/untouched
            body = _body_text(msg)
            story_id = _extract_story_id(body)
            decision = _extract_decision(body)
            sender = parseaddr(msg.get("From", ""))[1]
            if story_id and decision:
                results.append(
                    {
                        "story_id": story_id,
                        "reply": decision,
                        "email_from": sender,
                        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                    }
                )
                # Mark as read so it isn't processed again.
                imap.store(mid, "+FLAGS", "\\Seen")
                log.info("Reply parsed: story=%s decision=%s from=%s",
                         story_id, decision, sender)
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass
    return results
