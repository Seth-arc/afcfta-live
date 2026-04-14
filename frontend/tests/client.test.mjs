import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "esbuild";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");

async function loadClientModule() {
  const buildResult = await build({
    entryPoints: [path.join(projectRoot, "src/api/client.ts")],
    bundle: true,
    format: "esm",
    platform: "browser",
    write: false,
  });

  const tempDir = await mkdtemp(path.join(tmpdir(), "afcfta-client-test-"));
  const modulePath = path.join(tempDir, "client.mjs");
  await writeFile(modulePath, buildResult.outputFiles[0].text, "utf8");

  try {
    return await import(`${pathToFileURL(modulePath).href}?t=${Date.now()}`);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

function installBrowserStubs(fetchImpl) {
  const originalFetch = globalThis.fetch;
  const originalCrypto = globalThis.crypto;

  globalThis.fetch = fetchImpl;
  Object.defineProperty(globalThis, "crypto", {
    value: { randomUUID: () => "test-request-id" },
    configurable: true,
  });

  return () => {
    if (originalFetch === undefined) {
      delete globalThis.fetch;
    } else {
      globalThis.fetch = originalFetch;
    }

    if (originalCrypto === undefined) {
      delete globalThis.crypto;
    } else {
      Object.defineProperty(globalThis, "crypto", {
        value: originalCrypto,
        configurable: true,
      });
    }
  };
}

test("postAssistantQuery uses /web/api and never attaches X-API-Key", async () => {
  const client = await loadClientModule();
  let capturedUrl = "";
  let capturedInit = null;

  const restore = installBrowserStubs(async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init ?? null;
    return {
      ok: true,
      json: async () => ({
        response_type: "clarification",
        case_id: null,
        evaluation_id: null,
        audit_url: null,
        audit_persisted: false,
        assessment: null,
        clarification: {
          question: "Need more facts",
          missing_facts: ["hs6_code"],
          missing_evidence: [],
        },
        explanation: null,
        explanation_fallback_used: false,
        assistant_rendering: null,
        error: null,
      }),
      headers: {
        get: () => null,
      },
    };
  });

  try {
    client.configureApiClient({ baseUrl: "/web/api" });
    await client.postAssistantQuery({ user_input: "Can I export HS 110311?" });
  } finally {
    restore();
  }

  assert.equal(capturedUrl, "/web/api/assistant/assess");
  assert.ok(capturedInit);
  assert.equal(capturedInit.method, "POST");
  assert.equal(capturedInit.credentials, "same-origin");
  assert.equal(capturedInit.headers["X-Request-ID"], "test-request-id");
  assert.equal(capturedInit.headers["X-API-Key"], undefined);
  assert.equal(
    JSON.stringify(capturedInit.headers).includes("dev-local-key"),
    false,
  );
});

test("getAuditTrail uses the browser-safe replay path without API-key headers", async () => {
  const client = await loadClientModule();
  let capturedUrl = "";
  let capturedInit = null;

  const restore = installBrowserStubs(async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init ?? null;
    return {
      ok: true,
      json: async () => ({ replay_mode: "snapshot_frozen" }),
      headers: {
        get: () => null,
      },
    };
  });

  try {
    client.configureApiClient({ baseUrl: "/web/api" });
    await client.getAuditTrail("eval-123");
  } finally {
    restore();
  }

  assert.equal(capturedUrl, "/web/api/audit/evaluations/eval-123");
  assert.ok(capturedInit);
  assert.equal(capturedInit.method, "GET");
  assert.equal(capturedInit.headers["X-API-Key"], undefined);
});
