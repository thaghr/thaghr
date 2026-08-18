# 06-node-proxy

Phase 6 DoD: a Node script using the OpenAI JS SDK gets faults injected
with no change beyond `baseURL`.

This works because `thaghr proxy` reuses the same `ThaghrTransport` that
Phase 2's httpx integration uses, just fronted by a real HTTP server
instead of an in-process transport hook. Any HTTP-based SDK, in any
language, gets the identical fault stack by pointing its base URL at the
proxy.

## Zero-cost local run

Three terminals (or three background processes), all from the repo root:

```bash
# 1. a deterministic, zero-cost stand-in for a real provider
python examples/06-node-proxy/fake_upstream.py 8090

# 2. thaghr proxy, fronting the fake upstream, faults off
thaghr proxy --upstream http://127.0.0.1:8090 --fault-rate 0.0 --seed 1 --port 8135

# 3. the Node example
cd examples/06-node-proxy
npm install
node agent.mjs
```

Expected output with `--fault-rate 0.0`:

```
thaghr proxy demo: call succeeded
  content: hi there friend
  usage: { prompt_tokens: 9, completion_tokens: 3, total_tokens: 12 }
```

Kill the proxy, restart it with `--fault-rate 1.0`, run `node agent.mjs`
again. Same client code, only the proxy's fault rate changed:

```
thaghr proxy demo: call failed
  name: RateLimitError
  status: 429
  message: 429 status code (no body)
```

## Against a real provider

Point `--upstream` at a real OpenAI-compatible endpoint instead of
`fake_upstream.py`, and set `OPENAI_API_KEY` to a real key before running
`node agent.mjs`. Everything else is unchanged; the proxy doesn't inspect
or need the key, it only sits on the wire between the client and whatever
`--upstream` points at.

## What to look at if this breaks

- `thaghr proxy` prints its listening URL and fault rate on startup;
  confirm `THAGHR_PROXY_URL` in the Node script's environment matches it.
- A `ECONNREFUSED` from Node means the proxy isn't running or is on a
  different port than `THAGHR_PROXY_URL` expects.
- If the proxy process log shows a Python traceback ending in
  `httpx.ResponseNotRead`, that's the streaming-response bug fixed in
  `proxy.py`'s `_handle()` (`response.read()` before touching
  `.content`); if it recurs, something upstream of that line changed.
