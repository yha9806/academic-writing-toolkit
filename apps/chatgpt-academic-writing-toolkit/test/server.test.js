import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import { createHttpApp } from "../src/server.js";

async function readJson(url) {
  return JSON.parse(await readFile(url, "utf8"));
}

test("HTTP app exposes package-aligned health and guards non-POST MCP requests", async () => {
  const appPackage = await readJson(new URL("../package.json", import.meta.url));
  const pluginManifest = await readJson(
    new URL("../../../plugins/academic-writing-toolkit/.codex-plugin/plugin.json", import.meta.url),
  );
  assert.equal(appPackage.version, pluginManifest.version);

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
      version: appPackage.version,
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
