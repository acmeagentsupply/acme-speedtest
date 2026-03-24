#!/usr/bin/env python3
"""
acme-speedtest v0.1
ACME Agent Supply Co. — Model Health & Rate Limit Intelligence

Free to use under ACME Freeware License v1.
Not open source. Do not fork, resell, or compete.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

VERSION = "0.1.0"
DEFAULT_CONFIG_PATH = Path.home() / ".openclaw" / "watchdog" / "transmission_config.json"
DEFAULT_LOG_PATH    = Path.home() / ".openclaw" / "watchdog" / "transmission_events.log"
TIMEOUT_SECONDS     = 10
HISTORY_HOURS       = 24

# ANSI colors
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
DIM    = "\033[2m"

# ── Model config ──────────────────────────────────────────────────────────────

def load_models(config_path: Path) -> dict:
    """Load model list from Transmission config if available."""
    if not config_path.exists():
        # Fallback: well-known defaults
        return {
            "anthropic/claude-sonnet-4-6": {"tier": "premium", "provider": "anthropic"},
            "openai/gpt-4.1-mini":         {"tier": "mid",     "provider": "openai"},
            "google/gemini-2.5-flash-lite": {"tier": "efficient", "provider": "google"},
        }
    try:
        cfg = json.loads(config_path.read_text())
        return cfg.get("models", {})
    except Exception:
        return {}


# ── Event log parsing ─────────────────────────────────────────────────────────

def parse_events(log_path: Path, since_hours: float = HISTORY_HOURS) -> list[dict]:
    """Parse routing event log. Treats log format as internal — no schema documented."""
    if not log_path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    events = []
    try:
        for line in log_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                ts_str = ev.get("ts", "")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        events.append(ev)
            except (json.JSONDecodeError, ValueError):
                continue
    except Exception:
        pass
    return events


def classify_rate_limit(events: list[dict], model: str) -> dict:
    """
    Classify rate limit state for a model from event history.
    Hard block = circuit open (429). Throttle = degraded health score.
    Returns: {status, started_at, cooldown_remaining_min, pattern_count, type}
    """
    result = {"status": "healthy", "started_at": None, "cooldown_min": 0,
              "pattern_count": 0, "type": None}

    model_events = [e for e in events if model in str(e.get("model", ""))
                    or model in str(e.get("chain", ""))]

    # Detect circuit opens (hard 429)
    circuit_opens = [e for e in model_events if e.get("event") == "TRANSMISSION_CIRCUIT_OPEN"]
    health_alerts = [e for e in model_events if e.get("event") == "TRANSMISSION_MODEL_HEALTH_ALERT"]

    if circuit_opens:
        last_open = circuit_opens[-1]
        ts = datetime.fromisoformat(last_open["ts"].replace("Z", "+00:00"))
        cooldown_min = int(last_open.get("cooldown_minutes", 10))
        elapsed_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
        remaining = max(0, cooldown_min - elapsed_min)

        result["pattern_count"] = len(circuit_opens)
        if remaining > 0:
            result["status"] = "blocked"
            result["type"] = "hard_429"
            result["started_at"] = ts
            result["cooldown_min"] = int(remaining)
        else:
            # Circuit may have recovered
            result["status"] = "recovering"
            result["type"] = "hard_429"
            result["started_at"] = ts

    elif health_alerts:
        last_alert = health_alerts[-1]
        ts = datetime.fromisoformat(last_alert["ts"].replace("Z", "+00:00"))
        score = last_alert.get("health_score", 100)
        result["status"] = "throttled"
        result["type"] = "throttle"
        result["started_at"] = ts
        result["pattern_count"] = len(health_alerts)
        result["health_score"] = score

    return result


def count_failures_by_hour(events: list[dict], model: str) -> list[tuple]:
    """Return (hour_label, failure_count) for last 24h in 6h buckets."""
    buckets = defaultdict(int)
    now = datetime.now(timezone.utc)
    for ev in events:
        if model not in str(ev.get("model", "")) + str(ev.get("chain", "")):
            continue
        if ev.get("event") not in ("TRANSMISSION_CIRCUIT_OPEN", "TRANSMISSION_MODEL_HEALTH_ALERT"):
            continue
        try:
            ts = datetime.fromisoformat(ev["ts"].replace("Z", "+00:00"))
            hours_ago = (now - ts).total_seconds() / 3600
            bucket = int(hours_ago // 6) * 6
            buckets[bucket] += 1
        except Exception:
            continue
    result = []
    for b in [18, 12, 6, 0]:
        label = f"{b+6}–{b}h ago" if b > 0 else "last 6h"
        result.append((label, buckets[b]))
    return result


# ── Probe ─────────────────────────────────────────────────────────────────────

def probe_model(model_id: str, provider: str) -> dict:
    """Send a minimal probe request and measure latency."""
    start = time.monotonic()
    try:
        if provider == "anthropic":
            import urllib.request, urllib.error
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return {"ok": False, "error": "no API key", "latency_ms": None}
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": model_id.split("/")[-1],
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                }).encode(),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                latency_ms = int((time.monotonic() - start) * 1000)
                return {"ok": True, "latency_ms": latency_ms, "status": resp.status}

        elif provider == "openai":
            import urllib.request
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                return {"ok": False, "error": "no API key", "latency_ms": None}
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps({
                    "model": model_id.split("/")[-1],
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                }).encode(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                latency_ms = int((time.monotonic() - start) * 1000)
                return {"ok": True, "latency_ms": latency_ms}

        elif provider == "google":
            import urllib.request
            api_key = os.environ.get("GOOGLE_API_KEY", "")
            if not api_key:
                return {"ok": False, "error": "no API key", "latency_ms": None}
            model_name = model_id.split("/")[-1]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps({"contents": [{"parts": [{"text": "hi"}]}], "generationConfig": {"maxOutputTokens": 1}}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                latency_ms = int((time.monotonic() - start) * 1000)
                return {"ok": True, "latency_ms": latency_ms}

        else:
            return {"ok": False, "error": f"unsupported provider: {provider}", "latency_ms": None}

    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        error_str = str(e)
        is_429 = "429" in error_str or "rate" in error_str.lower()
        return {"ok": False, "error": error_str[:80], "latency_ms": latency_ms,
                "is_rate_limit": is_429}


# ── Display ───────────────────────────────────────────────────────────────────

def format_latency(ms: Optional[int]) -> str:
    if ms is None:
        return f"{DIM}  —    {RESET}"
    if ms < 500:
        return f"{GREEN}{ms:4d}ms{RESET}"
    if ms < 1500:
        return f"{YELLOW}{ms:4d}ms{RESET}"
    return f"{RED}{ms:4d}ms{RESET}"


def format_status(probe: dict, rate: dict) -> tuple[str, str]:
    """Returns (pill, detail)"""
    if rate["status"] == "blocked":
        pill = f"{RED}● BLOCKED   {RESET}"
        cd = rate.get("cooldown_min", 0)
        detail = f"hard 429 — {cd}min cooldown remaining"
    elif rate["status"] == "throttled":
        pill = f"{YELLOW}● THROTTLED {RESET}"
        score = rate.get("health_score", "?")
        detail = f"soft throttle — health {score}/100, routing around it"
    elif rate["status"] == "recovering":
        pill = f"{YELLOW}● RECOVERING{RESET}"
        detail = "recent circuit open — may be clear now"
    elif not probe["ok"]:
        if probe.get("is_rate_limit"):
            pill = f"{RED}● BLOCKED   {RESET}"
            detail = "429 on probe — hard rate limit active"
        else:
            pill = f"{RED}● ERROR     {RESET}"
            detail = probe.get("error", "unknown error")[:60]
    else:
        pill = f"{GREEN}● HEALTHY   {RESET}"
        detail = ""
    return pill, detail


def run():
    config_path = Path(os.environ.get("TRANSMISSION_CONFIG", str(DEFAULT_CONFIG_PATH)))
    log_path    = Path(os.environ.get("TRANSMISSION_LOG",    str(DEFAULT_LOG_PATH)))

    models = load_models(config_path)
    if not models:
        print(f"{RED}No models configured. Set TRANSMISSION_CONFIG or ensure ~/.openclaw/watchdog/transmission_config.json exists.{RESET}")
        sys.exit(1)

    events = parse_events(log_path)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M %Z")
    print()
    print(f"{BOLD}{'━'*62}{RESET}")
    print(f"{BOLD}  ⚡ ACME Speedtest v{VERSION}  •  {now_str}{RESET}")
    print(f"{BOLD}{'━'*62}{RESET}")
    print()
    print(f"  {'Model':<40} {'Status':<22} {'Latency'}")
    print(f"  {'─'*40} {'─'*22} {'─'*8}")

    results = []
    for model_id, cfg in models.items():
        provider = cfg.get("provider", model_id.split("/")[0])
        tier = cfg.get("tier", "?")
        rate = classify_rate_limit(events, model_id)

        # Only probe if not clearly blocked from log
        if rate["status"] in ("blocked",):
            probe = {"ok": False, "is_rate_limit": True, "latency_ms": None, "error": "blocked (from log)"}
        else:
            sys.stdout.write(f"  {DIM}probing {model_id[:38]!s:<38}...{RESET}\r")
            sys.stdout.flush()
            probe = probe_model(model_id, provider)

        pill, detail = format_status(probe, rate)
        latency = format_latency(probe.get("latency_ms"))
        short_name = model_id.replace("anthropic/", "").replace("openai/", "").replace("google/", "").replace("openrouter/", "")

        print(f"  {short_name:<40} {pill} {latency}")
        if detail:
            print(f"  {' '*40}   {DIM}{detail}{RESET}")

        # Pattern history
        pattern = count_failures_by_hour(events, model_id)
        if any(c > 0 for _, c in pattern):
            hist = "  ".join(f"{label}: {count}" for label, count in pattern if count > 0)
            print(f"  {' '*40}   {DIM}incidents: {hist}{RESET}")

        results.append({"model": model_id, "probe": probe, "rate": rate})

    print()
    print(f"  {'─'*62}")

    healthy = sum(1 for r in results if r["rate"]["status"] == "healthy" and r["probe"]["ok"])
    blocked = sum(1 for r in results if r["rate"]["status"] == "blocked" or r["probe"].get("is_rate_limit"))
    total = len(results)

    if blocked == 0 and healthy == total:
        verdict = f"{GREEN}{BOLD}TRANSMISSION READY{RESET}  {healthy}/{total} models healthy"
    elif healthy > 0:
        verdict = f"{YELLOW}{BOLD}DEGRADED{RESET}  {healthy}/{total} models healthy — {blocked} blocked/throttled"
    else:
        verdict = f"{RED}{BOLD}NOT READY{RESET}  All models unavailable"

    print(f"  {verdict}")
    print()


if __name__ == "__main__":
    run()
