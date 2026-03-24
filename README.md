# acme-speedtest

Model health and rate limit intelligence for AI agent operators.

Run it before enabling Transmission — or any time you hit a rate limit and want to know what's actually happening.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/acmeagentsupply/acme-speedtest/main/install.sh | bash
```

Then run:

```bash
acme-speedtest
```

## What it does

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚡ ACME Speedtest v0.1.0  •  2026-03-24 09:30 EDT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Model                                    Status                 Latency
  ──────────────────────────────────────── ────────────────────── ────────
  claude-sonnet-4-6                        ● HEALTHY              342ms
  gpt-4.1-mini                             ● HEALTHY              198ms
  gemini-2.5-flash-lite                    ● HEALTHY              287ms
  kimi-k2                                  ● THROTTLED            —
                                             soft throttle — health 55/100
                                             incidents: last 6h: 2  12–6h ago: 1

  ──────────────────────────────────────────────────────────────────
  DEGRADED  3/4 models healthy — 1 blocked/throttled
```

**Rate limit intelligence** — the killer feature. Instead of just "model X is down", you get:
- Is it a hard 429 block or a soft throttle?
- When did it start?
- How long until the cooldown clears?
- 24h incident pattern — is this model consistently failing at a certain time?

## Requirements

- Python 3.8+
- API keys in your environment for the models you want to probe:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `GOOGLE_API_KEY`

## Options

```
acme-speedtest --help       Show help
acme-speedtest --no-probe   Log analysis only (no live API calls)
acme-speedtest --version    Print version
```

---

Free to use under [ACME Freeware License v1](LICENSE).  
Not open source — do not fork, resell, or compete.  
© 2026 ACME Agent Supply Co. — [acmeagentsupply.com](https://acmeagentsupply.com)
