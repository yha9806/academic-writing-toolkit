import test from "node:test";
import assert from "node:assert/strict";

import { createHttpApp } from "../src/server.js";

test("HTTP app exposes health and guards non-POST MCP requests", async () => {
  const oldChallenge = process.env.OPENAI_APPS_CHALLENGE;
  process.env.OPENAI_APPS_CHALLENGE = "test-openai-apps-challenge";
  const app = createHttpApp({ host: "127.0.0.1" });
  const server = await new Promise((resolve) => {
    const listener = app.listen(0, "127.0.0.1", () => resolve(listener));
  });

  try {
    const port = server.address().port;
    const health = await fetch(`http://127.0.0.1:${port}/health`);
    assert.equal(health.status, 200);
    assert.equal(
      health.headers.get("content-security-policy"),
      "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    );
    assert.deepEqual(await health.json(), {
      name: "academic-writing-toolkit",
      version: "1.0.0",
      status: "ok",
    });

    const mcpGet = await fetch(`http://127.0.0.1:${port}/mcp`);
    assert.equal(mcpGet.status, 405);

    const challenge = await fetch(`http://127.0.0.1:${port}/.well-known/openai-apps-challenge`);
    assert.equal(challenge.status, 200);
    assert.equal(await challenge.text(), "test-openai-apps-challenge");
  } finally {
    if (oldChallenge === undefined) {
      delete process.env.OPENAI_APPS_CHALLENGE;
    } else {
      process.env.OPENAI_APPS_CHALLENGE = oldChallenge;
    }
    await new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    });
  }
});
