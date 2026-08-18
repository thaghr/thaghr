// thaghr Phase 6 example: the OpenAI JS SDK gets the same fault stack as
// the Python httpx-transport integration (Phase 2), with the only
// client-side change being `baseURL`.
//
// Run against:
//   1. `thaghr proxy` fronting a real OpenAI-compatible endpoint, or
//   2. `thaghr proxy` fronting the local fake_upstream.py in this
//      directory, for a deterministic, zero-cost demo.
//
// Env vars (all optional, mirrors examples/01-hello-agent/agent.py):
//   THAGHR_PROXY_URL   base URL of the running `thaghr proxy` (default http://127.0.0.1:8135/v1)
//   OPENAI_API_KEY     forwarded to the SDK; the proxy doesn't check it,
//                      the real upstream does (default a dummy key, fine
//                      against fake_upstream.py)
//   THAGHR_DEMO_MODEL  model name to request (default gpt-4o-mini)

import OpenAI from "openai";

const baseURL = process.env.THAGHR_PROXY_URL ?? "http://127.0.0.1:8135/v1";
const model = process.env.THAGHR_DEMO_MODEL ?? "gpt-4o-mini";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY ?? "thaghr-demo-key",
  baseURL,
  maxRetries: 2,
});

async function run() {
  try {
    const completion = await client.chat.completions.create({
      model,
      messages: [{ role: "user", content: "Say hello in exactly three words." }],
    });
    console.log("thaghr proxy demo: call succeeded");
    console.log("  content:", completion.choices[0].message.content);
    console.log("  usage:", completion.usage);
  } catch (err) {
    // A faulted call surfaces here as whatever error the OpenAI JS SDK
    // raises for the injected status code (RateLimitError for 429), the
    // same shape a real production 429 would take. This is the point of
    // Phase 6: the SDK's own retry/error handling engages against an
    // injected fault exactly as it would against a real one, and nothing
    // about the client code above changed to make that happen.
    console.log("thaghr proxy demo: call failed");
    console.log("  name:", err.name);
    console.log("  status:", err.status);
    console.log("  message:", err.message);
    process.exitCode = 1;
  }
}

run();
