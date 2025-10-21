#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


LOG_PATH = Path(__file__).resolve().parents[1] / "debug" / "docker.logs"
OUT_DIR = Path(__file__).resolve().parents[1] / "debug" / "analysis"
OUT_FILE = OUT_DIR / "docker_timeline.md"


def parse_log_line(line: str) -> dict[str, Any] | None:
    # Attempt to extract JSON payload from docker-prefixed lines
    try:
        first_brace = line.index("{")
        json_str = line[first_brace:]
        return json.loads(json_str)
    except Exception:
        return None


def main() -> None:
    if not LOG_PATH.exists():
        print(f"No log file at {LOG_PATH}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    event_counts: Counter[str] = Counter()
    per_service_counts: dict[str, Counter[str]] = defaultdict(Counter)
    journeys: dict[str, list[dict[str, Any]]] = {}
    first_ts: str | None = None
    last_ts: str | None = None
    timeline: list[str] = []

    seq = 0
    with LOG_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            seq += 1
            payload = parse_log_line(raw)
            if not payload:
                continue
            event = payload.get("event") or payload.get("message") or payload.get("msg")
            service = payload.get("service") or "unknown"
            ts = payload.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            if event:
                event_counts[event] += 1
                per_service_counts[service][event] += 1
                # Keep a small timeline of key lifecycle events
                if re.search(
                    r"(ready|connected|segment_ready|segment_processing_start|response_received|wake\.detected)",
                    event,
                ):
                    timeline.append(f"{ts or ''} {service} {event}")

            # Track journeys by correlation_id
            corr_id = payload.get("correlation_id")
            if corr_id:
                # Persist a compact view for the journey
                journeys.setdefault(corr_id, [])
                journeys[corr_id].append(
                    {
                        "ts": ts,
                        "seq": seq,
                        "service": service,
                        "event": event or "",
                        # Capture common context fields if present
                        "guild_id": payload.get("guild_id"),
                        "channel_id": payload.get("channel_id"),
                        "user_id": payload.get("user_id"),
                        "frames": payload.get("frames"),
                        "duration": payload.get("duration"),
                        "latency_ms": payload.get("latency_ms"),
                        "text_length": payload.get("text_length"),
                        "language": payload.get("language"),
                        "confidence": payload.get("confidence"),
                        "flush_reason": payload.get("flush_reason"),
                    }
                )

    lines: list[str] = []
    lines.append("# Docker Logs Timeline and Event Summary\n")
    if first_ts and last_ts:
        lines.append(f"Window: {first_ts} → {last_ts}\n")

    lines.append("\n## Top Events\n")
    for event, count in event_counts.most_common(30):
        lines.append(f"- {event}: {count}")

    lines.append("\n## Per-Service Top Events\n")
    for service, ctr in per_service_counts.items():
        lines.append(f"\n### {service}\n")
        for event, count in ctr.most_common(15):
            lines.append(f"- {event}: {count}")

    lines.append("\n## Lifecycle Timeline (sampled)\n")
    lines.extend([f"- {entry}" for entry in timeline[:200]])

    # Correlation journeys
    lines.append("\n## Correlation Journeys\n")

    # Sort correlation IDs by first observed timestamp (fallback: lexical id)
    def _first_ts_of(cid: str) -> str:
        items = journeys.get(cid, [])
        if not items:
            return ""
        # Prefer earliest ts, fallback to empty if missing
        ts_values = [it.get("ts") or "" for it in items]
        return min(ts_values) if any(ts_values) else ""

    for cid in sorted(journeys.keys(), key=_first_ts_of):
        events = sorted(journeys[cid], key=lambda it: ((it.get("ts") or ""), it.get("seq", 0)))
        lines.append(f"\n### {cid} ({len(events)} events)\n")
        limit = 200
        for idx, it in enumerate(events):
            if idx >= limit:
                lines.append("- ... (truncated) ...")
                break
            ts = it.get("ts") or ""
            service = it.get("service") or "unknown"
            event = it.get("event") or ""
            # Build compact details string
            detail_keys = (
                "guild_id",
                "channel_id",
                "user_id",
                "frames",
                "duration",
                "latency_ms",
                "text_length",
                "language",
                "confidence",
                "flush_reason",
            )
            details = []
            for key in detail_keys:
                value = it.get(key)
                if value is not None:
                    details.append(f"{key}={value}")
            detail_str = f" ({', '.join(details)})" if details else ""
            lines.append(f"- {ts} {service} {event}{detail_str}")

    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
