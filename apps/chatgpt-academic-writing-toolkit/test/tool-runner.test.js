import test from "node:test";
import assert from "node:assert/strict";

import {
  auditCitations,
  checkBritishEnglish,
  createReadingNoteTemplate,
  resolvePythonInterpreter,
  reviewParagraphLogic,
  verifyBibtexReferences,
} from "../src/tool-runner.js";
import { TOOL_DEFINITIONS } from "../src/tool-definitions.js";

function executableLookup(entries) {
  const commands = new Map(entries);
  return (command) => commands.get(command) ?? [];
}

test("Python resolver gives AWT_PYTHON precedence over PYTHON", () => {
  const result = resolvePythonInterpreter({
    env: {
      AWT_PYTHON: "C:\\Python312\\python.exe",
      PYTHON: "C:\\OtherPython\\python.exe",
    },
    platform: "win32",
    findExecutables: executableLookup([
      ["C:\\Python312\\python.exe", ["C:\\Python312\\python.exe"]],
      ["C:\\OtherPython\\python.exe", ["C:\\OtherPython\\python.exe"]],
    ]),
  });

  assert.deepEqual(result, {
    command: "C:\\Python312\\python.exe",
    args: [],
    source: "AWT_PYTHON",
  });
});

test("Python resolver uses the standard PYTHON environment variable", () => {
  const result = resolvePythonInterpreter({
    env: { PYTHON: "/opt/project/python" },
    platform: "linux",
    findExecutables: executableLookup([["/opt/project/python", ["/opt/project/python"]]]),
  });

  assert.deepEqual(result, {
    command: "/opt/project/python",
    args: [],
    source: "PYTHON",
  });
});

test("Python resolver skips Windows Store aliases and selects a real python.exe", () => {
  const result = resolvePythonInterpreter({
    env: {},
    platform: "win32",
    findExecutables: executableLookup([
      [
        "python.exe",
        [
          "C:\\Users\\reader\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe",
          "C:\\Python312\\python.exe",
        ],
      ],
    ]),
  });

  assert.deepEqual(result, {
    command: "C:\\Python312\\python.exe",
    args: [],
    source: "PATH",
  });
});

test("Python resolver falls back to the Windows py launcher", () => {
  const result = resolvePythonInterpreter({
    env: {},
    platform: "win32",
    findExecutables: executableLookup([
      [
        "python.exe",
        ["C:\\Users\\reader\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe"],
      ],
      ["py.exe", ["C:\\Windows\\py.exe"]],
    ]),
  });

  assert.deepEqual(result, {
    command: "C:\\Windows\\py.exe",
    args: ["-3"],
    source: "PATH",
  });
});

test("Python resolver uses python3 on POSIX and fails clearly without a runtime", () => {
  const result = resolvePythonInterpreter({
    env: {},
    platform: "linux",
    findExecutables: executableLookup([["python3", ["/usr/bin/python3"]]]),
  });
  assert.deepEqual(result, {
    command: "/usr/bin/python3",
    args: [],
    source: "PATH",
  });

  assert.throws(
    () =>
      resolvePythonInterpreter({
        env: {},
        platform: "win32",
        findExecutables: executableLookup([
          [
            "python.exe",
            ["C:\\Users\\reader\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe"],
          ],
        ]),
      }),
    /No usable Python interpreter found.*Windows Store aliases are ignored/,
  );
});

test("checkBritishEnglish reports conservative US spelling replacements", async () => {
  const result = await checkBritishEnglish({
    text: "The color center helps analyze behavior.",
  });

  assert.equal(result.issue_count, 4);
  assert.deepEqual(
    result.issues.map((issue) => `${issue.current}->${issue.replacement}`),
    ["color->colour", "center->centre", "analyze->analyse", "behavior->behaviour"],
  );
});

test("reviewParagraphLogic flags short paragraphs and repeated transitions", async () => {
  const result = await reviewParagraphLogic({
    text: "However, this matters.\n\nHowever, it also matters.",
  });

  const kinds = new Set(result.issues.map((issue) => issue.kind));
  assert.equal(result.issue_count, 3);
  assert.equal(kinds.has("short-paragraph"), true);
  assert.equal(kinds.has("repeated-transition"), true);
});

test("verifyBibtexReferences validates BibTeX offline", async () => {
  const result = await verifyBibtexReferences({
    bibtex: `@article{smith2024,
  title={Incomplete article},
  year={2024}
}

@article{smith2024,
  title={Complete article},
  author={Smith, Jane},
  year={2024},
  journal={Journal of Tests},
  doi={not-a-doi}
}
`,
  });

  const kinds = new Set(result.issues.map((issue) => issue.kind));
  assert.equal(result.entries, 2);
  assert.equal(kinds.has("duplicate-key"), true);
  assert.equal(kinds.has("missing-required-field"), true);
  assert.equal(kinds.has("doi-invalid"), true);
});

test("auditCitations compares chapter text with reading-note sources", async () => {
  const result = await auditCitations({
    style: "harvard",
    chapterText: "Smith (2024) argues that the archive changes interpretation.",
    readingNotesText: "**Source**: Jones, J. (2024) Title in sentence case. *Publisher*.",
  });

  assert.equal(result.style, "harvard");
  assert.equal(result.issue_count > 0, true);
  assert.equal(Array.isArray(result.issues), true);
});

test("createReadingNoteTemplate returns the standard notes structure", () => {
  const result = createReadingNoteTemplate({
    author: "Smith, J.",
    title: "Test Article",
    year: "2024",
    citationStyle: "harvard",
    relevance: "Ch2 S2.1 - background context",
  });

  assert.match(result.markdown, /^# Reading Notes: Smith, J\. - Test Article \(2024\)/);
  assert.match(result.markdown, /\*\*Status\*\*: reading/);
  assert.match(result.markdown, /## Key Arguments/);
  assert.match(result.markdown, /Ch2 S2\.1 - background context/);
});

test("all ChatGPT tool descriptors declare review hints and output schemas", () => {
  const expectedNames = [
    "audit_citations",
    "check_british_english",
    "review_paragraph_logic",
    "verify_bibtex_references",
    "create_reading_note_template",
  ];

  assert.deepEqual(Object.keys(TOOL_DEFINITIONS).sort(), expectedNames.sort());
  for (const [name, descriptor] of Object.entries(TOOL_DEFINITIONS)) {
    assert.equal(descriptor.description.startsWith("Use this when"), true, name);
    assert.deepEqual(descriptor.annotations, {
      readOnlyHint: true,
      openWorldHint: false,
      destructiveHint: false,
    });
    assert.ok(descriptor.outputSchema, `${name} is missing outputSchema`);
  }
});
