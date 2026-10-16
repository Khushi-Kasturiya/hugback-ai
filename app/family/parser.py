"""Dependency-free bounded direct-chat parser. Original bytes are stored unchanged."""
import base64
import binascii
from datetime import datetime, timezone
import json
import re
from zoneinfo import ZoneInfo

from app.family.models import ImportInput, MAX_FILE_BYTES

PARSER_VERSION = 1
ISO = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))\] ([^:\n]{1,100}): (.*)$")
WA = re.compile(r"^\[?(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}),? (\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)\]?(?: - | )(.+)$", re.I)
OMITTED = re.compile(r"^(?:<media omitted>|(?:image|video|audio|sticker|document) omitted|this message was deleted|you deleted this message)$", re.I)


class FamilyError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def timestamp(value, zone):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        first, second = parsed.replace(tzinfo=zone, fold=0), parsed.replace(tzinfo=zone, fold=1)
        if first.utcoffset() != second.utcoffset() or first.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != parsed:
            raise ValueError("Ambiguous local timestamp")
        parsed = first
    return parsed.isoformat()


def decode_upload(request: ImportInput):
    suffixes = (".txt", ".json") if request.source == "instagram" else (".txt",)
    if not request.filename.lower().endswith(suffixes):
        raise FamilyError("Choose a supported text export, not media, HTML or an archive.")
    try:
        raw = base64.b64decode(request.fileBase64, validate=True)
    except (ValueError, binascii.Error):
        raise FamilyError("The upload is not valid base64.")
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise FamilyError("Choose a file up to 1 MiB.", 413)
    return raw, parse(raw, request.model_dump(exclude={"fileBase64", "acknowledgeUpload"}))


def parse(raw: bytes, metadata: dict) -> list[dict]:
    try:
        if not 0 < len(raw) <= MAX_FILE_BYTES:
            raise ValueError()
        text = raw.decode("utf-8-sig")
        if not text.strip() or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", text):
            raise ValueError()
        zone = ZoneInfo(metadata["timeZone"])
        messages = []
        if metadata["source"] == "instagram" and text.lstrip().startswith("{"):
            data = json.loads(text)
            participants = [p["name"] for p in data["participants"]]
            if len(participants) != 2 or len(set(participants)) != 2 or len(data["messages"]) > 2000:
                raise ValueError()
            for item in data["messages"]:
                if item["sender_name"] not in participants or type(item["timestamp_ms"]) is not int or item["timestamp_ms"] < 0:
                    raise ValueError()
                when = datetime.fromtimestamp(item["timestamp_ms"] / 1000, timezone.utc).isoformat()
                if "content" not in item:
                    continue
                if not isinstance(item["content"], str):
                    raise ValueError()
                messages.append({"sender": item["sender_name"], "timestamp": when, "text": item["content"]})
            messages.sort(key=lambda m: m["timestamp"])
        else:
            current = None
            for original in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
                line = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", original).replace("\u202f", " ").replace("\u00a0", " ")
                if not line.strip():
                    continue
                iso, wa = ISO.match(line), WA.match(line) if metadata["source"] == "whatsapp" else None
                if iso:
                    current = {"timestamp": timestamp(iso[1], zone), "sender": iso[2].strip(), "text": iso[3]}
                    messages.append(current)
                elif wa:
                    a, b, year = map(int, re.split(r"[/.]", wa[1]))
                    year = year + 2000 if year < 100 else year
                    month, day = (b, a) if metadata["dateOrder"] == "DMY" else (a, b)
                    clock = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s?(AM|PM)?", wa[2], re.I)
                    hour, minute, second = int(clock[1]), int(clock[2]), int(clock[3] or 0)
                    if clock[4]:
                        if not 1 <= hour <= 12:
                            raise ValueError()
                        hour = hour % 12 + (12 if clock[4].upper() == "PM" else 0)
                    when = timestamp(datetime(year, month, day, hour, minute, second).isoformat(), zone)
                    sender, separator, message = wa[3].partition(": ")
                    if not separator:
                        current = None  # System/media notices are not a speaker.
                        continue
                    current = {"sender": sender.strip(), "timestamp": when, "text": message}
                    messages.append(current)
                else:
                    if current is None or re.match(r"^\[?\d{1,4}[/-]\d{1,2}[/-]\d{1,4}", line):
                        raise ValueError()
                    current["text"] += "\n" + line
                if len(messages) > 2000:
                    raise ValueError()
        names = {m["sender"] for m in messages}
        if len(names) != 2 or names != {metadata["childSender"], metadata["parentSender"]} or any(not n or len(n) > 100 for n in names):
            raise ValueError()
        messages = [m for m in messages if m["text"].strip() and not OMITTED.fullmatch(m["text"].strip())]
        if not messages:
            raise ValueError()
        return [m | {"sourceIndex": i, "role": "child" if m["sender"] == metadata["childSender"] else "parent"} for i, m in enumerate(messages)]
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, OSError, RecursionError):
        # Never echo rejected chat text, participant names or provider errors.
        raise FamilyError("Unsupported export, participant mapping, date or timezone. Use one two-person UTF-8 conversation with at most 2,000 messages.") from None
