# acme-speedtest

Model health and rate limit intelligence for AI agent operators.

Run it before enabling Transmission. See which models are healthy, which are rate-limited, and whether a limit is a hard block or a soft throttle.

```bash
curl -fsSL https://acmeagentsupply.com/install/speedtest | bash
```

Or run directly:
```bash
python3 speedtest.py
```

**Requires:** Python 3.8+. API keys in environment (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` as applicable for your configured models).

---

Free to use under [ACME Freeware License v1](LICENSE). Not open source.
© 2026 ACME Agent Supply Co. — acmeagentsupply.com
