# thaghr

ثَغْر — the fortified frontier outpost.

thaghr breaks your AI agent on purpose, then tells you whether it survived.

**Find the breach before it finds you.**

```bash
pip install thaghr
```

## What it measures

`pass^k`, not `pass@k`. `pass@k` means the agent succeeded at least once in
k tries, which rewards luck. `pass^k` means it succeeded *every* time,
which measures reliability.

## Quick start

```bash
thaghr run examples/01-hello-agent --fault-rate 0.2
thaghr compare examples/01-hello-agent
thaghr proxy --upstream https://api.openai.com
```

## Status

`0.1.0`, live on PyPI. Fault injection, deterministic record/replay,
the pass^k/GDS reliability surface, the CLI report card, and proxy mode
all work today. Prometheus telemetry and alerting are wired for
self-hosted deployments. Helm chart, hosted plane, and a GitHub Action
for CI are in progress.

## License

Apache 2.0