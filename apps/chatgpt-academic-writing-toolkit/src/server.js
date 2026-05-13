import { pathToFileURL } from "node:url";

import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

import { TOOL_DEFINITIONS } from "./tool-definitions.js";
import {
  auditCitations,
  checkBritishEnglish,
  createReadingNoteTemplate,
  reviewParagraphLogic,
  verifyBibtexReferences,
} from "./tool-runner.js";

const APP_NAME = "academic-writing-toolkit";
const APP_VERSION = "1.0.0";

const TOOL_HANDLERS = {
  audit_citations: auditCitations,
  check_british_english: checkBritishEnglish,
  review_paragraph_logic: reviewParagraphLogic,
  verify_bibtex_references: verifyBibtexReferences,
  create_reading_note_template: createReadingNoteTemplate,
};

function contentFor(result) {
  if (result.markdown) {
    return result.markdown;
  }
  const preview = {
    summary: result.summary,
    issue_count: result.issue_count,
    issues: result.issues?.slice(0, 20),
  };
  return JSON.stringify(preview, null, 2);
}

function asToolResult(result) {
  return {
    structuredContent: result,
    content: [{ type: "text", text: contentFor(result) }],
  };
}

export function createMcpServer() {
  const server = new McpServer({
    name: APP_NAME,
    version: APP_VERSION,
  });

  for (const [name, descriptor] of Object.entries(TOOL_DEFINITIONS)) {
    server.registerTool(name, descriptor, async (args) => {
      const result = await TOOL_HANDLERS[name](args);
      return asToolResult(result);
    });
  }

  return server;
}

function methodNotAllowed(_req, res) {
  res.status(405).json({
    jsonrpc: "2.0",
    error: {
      code: -32000,
      message: "Method not allowed.",
    },
    id: null,
  });
}

export function createHttpApp({ host = process.env.HOST || "127.0.0.1" } = {}) {
  const app = createMcpExpressApp({ host });

  app.use((_req, res, next) => {
    res.setHeader(
      "Content-Security-Policy",
      "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
    );
    next();
  });

  app.get("/health", (_req, res) => {
    res.json({
      name: APP_NAME,
      version: APP_VERSION,
      status: "ok",
    });
  });

  app.get("/.well-known/openai-apps-challenge", (_req, res) => {
    const challenge = process.env.OPENAI_APPS_CHALLENGE;
    if (!challenge) {
      res.status(404).type("text/plain").send("OpenAI Apps challenge is not configured.");
      return;
    }
    res.type("text/plain").send(challenge);
  });

  app.post("/mcp", async (req, res) => {
    const server = createMcpServer();
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
    });

    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
    } catch (error) {
      console.error("Error handling MCP request:", error);
      if (!res.headersSent) {
        res.status(500).json({
          jsonrpc: "2.0",
          error: {
            code: -32603,
            message: "Internal server error",
          },
          id: null,
        });
      }
    } finally {
      res.on("close", () => {
        transport.close();
        server.close();
      });
    }
  });

  app.get("/mcp", methodNotAllowed);
  app.delete("/mcp", methodNotAllowed);

  return app;
}

export function startHttpServer({
  host = process.env.HOST || "127.0.0.1",
  port = Number(process.env.PORT || 3000),
} = {}) {
  const app = createHttpApp({ host });
  const server = app.listen(port, host, () => {
    console.log(`${APP_NAME} MCP server listening on http://${host}:${port}/mcp`);
  });
  server.on("error", (error) => {
    console.error("Failed to start server:", error);
    process.exit(1);
  });
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  startHttpServer();
}
