#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx

# Simple, deterministic text normalization
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[\.,!?;:\-\(\)\[\]\{\}\"']+")


def normalize_text(s: str) -> str:
    s = s.strip().lower()
    s = _PUNCT_RE.sub("", s)
    s = _WS_RE.sub(" ", s)
    return s


def read_phrases(files: Iterable[Path]) -> list[str]:
    phrases: list[str] = []
    for path in files:
        data = path.read_text(encoding="utf-8").splitlines()
        for line in data:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            phrases.append(raw)
    return phrases


@dataclass
class ProviderConfig:
    base_url: str
    auth_token: str | None = None


async def synthesize_tts(tts_url: str, text: str, token: str | None = None) -> bytes:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"text": text}
    async with httpx.AsyncClient(base_url=tts_url, timeout=httpx.Timeout(30.0)) as client:
        resp = await client.post("/synthesize", json=payload, headers=headers)
        resp.raise_for_status()
        content: bytes = resp.content
        return content


async def stt_transcribe(
    stt_url: str, wav_bytes: bytes, language: str | None, beam_size: int | None
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if language:
        params["language"] = language
    if beam_size:
        params["beam_size"] = str(beam_size)
    files = {"file": ("eval.wav", wav_bytes, "audio/wav")}
    async with httpx.AsyncClient(base_url=stt_url, timeout=httpx.Timeout(60.0)) as client:
        resp = await client.post(
            "/transcribe", files=files, data={"metadata": "eval"}, params=params
        )
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
        return payload


def exact_match_score(expected: str, actual: str) -> float:
    return 1.0 if normalize_text(expected) == normalize_text(actual) else 0.0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate STT providers on simple phrase lists")
    parser.add_argument("--provider", default="stt", help="Provider key (stt|openai|azure|gcp)")
    parser.add_argument(
        "--phrases", nargs="+", type=Path, required=True, help="Paths to .txt phrase lists"
    )
    parser.add_argument(
        "--out", type=Path, default=Path("./debug/eval/"), help="Output directory for reports"
    )
    parser.add_argument("--stt-url", default=os.getenv("STT_BASE_URL", "http://localhost:9000"))
    parser.add_argument("--tts-url", default=os.getenv("TTS_BASE_URL", "http://localhost:7000"))
    parser.add_argument("--language", default=os.getenv("STT_FORCED_LANGUAGE", "en"))
    parser.add_argument("--beam-size", type=int, default=int(os.getenv("STT_BEAM_SIZE", "8")))
    args = parser.parse_args()

    phrases = read_phrases(args.phrases)
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    ok = 0
    for phrase in phrases:
        try:
            wav_bytes = await synthesize_tts(args.tts_url, phrase)
            payload = await stt_transcribe(
                args.stt_url, wav_bytes, args.language or None, args.beam_size
            )
            text = payload.get("text", "")
            score = exact_match_score(phrase, text)
            ok += int(score == 1.0)
            results.append(
                {
                    "phrase": phrase,
                    "transcript": text,
                    "score_exact": score,
                    "language": payload.get("language"),
                    "confidence": payload.get("confidence"),
                }
            )
        except httpx.HTTPError as exc:
            results.append({"phrase": phrase, "error": str(exc), "score_exact": 0.0})

    summary = {
        "provider": args.provider,
        "phrases": [str(p) for p in args.phrases],
        "total": len(phrases),
        "exact_matches": ok,
        "accuracy": (ok / max(1, len(phrases))),
    }

    out_json = args.out / "results.json"
    out_json.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
