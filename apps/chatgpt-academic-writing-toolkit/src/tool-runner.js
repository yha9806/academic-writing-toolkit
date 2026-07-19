import { accessSync, constants, statSync } from "node:fs";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const SOURCE_DIR = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(SOURCE_DIR, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "../..");
const SCRIPTS_DIR = path.join(REPO_ROOT, "scripts");

function envValue(env, name) {
  const direct = env[name];
  if (direct !== undefined) {
    return direct;
  }

  const matchedKey = Object.keys(env).find((key) => key.toLowerCase() === name.toLowerCase());
  return matchedKey === undefined ? undefined : env[matchedKey];
}

function stripOuterQuotes(value) {
  const trimmed = value.trim();
  if (
    trimmed.length >= 2 &&
    ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
      (trimmed.startsWith("'") && trimmed.endsWith("'")))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function isUsableExecutable(candidate, platform) {
  try {
    if (!statSync(candidate).isFile()) {
      return false;
    }
    if (platform !== "win32") {
      accessSync(candidate, constants.X_OK);
    }
    return true;
  } catch {
    return false;
  }
}

function executableMatches(command, { env, platform }) {
  const normalizedCommand = stripOuterQuotes(command);
  if (!normalizedCommand || normalizedCommand.includes("\0")) {
    return [];
  }

  const hasPathSeparator =
    normalizedCommand.includes("/") || normalizedCommand.includes("\\");
  if (path.isAbsolute(normalizedCommand) || hasPathSeparator) {
    const candidate = path.resolve(normalizedCommand);
    return isUsableExecutable(candidate, platform) ? [candidate] : [];
  }

  const pathValue = envValue(env, "PATH") ?? "";
  const delimiter = platform === "win32" ? ";" : ":";
  const extensions =
    platform === "win32" && path.extname(normalizedCommand) === "" ? [".exe"] : [""];
  const matches = [];

  for (const rawDirectory of pathValue.split(delimiter)) {
    const directory = stripOuterQuotes(rawDirectory);
    if (!directory) {
      continue;
    }
    for (const extension of extensions) {
      const candidate = path.join(directory, `${normalizedCommand}${extension}`);
      if (isUsableExecutable(candidate, platform)) {
        matches.push(candidate);
      }
    }
  }
  return matches;
}

function isWindowsStoreAlias(candidate, platform) {
  if (platform !== "win32") {
    return false;
  }
  const normalized = candidate.replaceAll("\\", "/").toLowerCase();
  return normalized.includes("/microsoft/windowsapps/");
}

/**
 * Resolve the Python process without invoking a shell.
 *
 * AWT_PYTHON and PYTHON must name one executable, not a command line. Windows
 * Store aliases are deliberately ignored because they can exist while failing
 * with spawn UNKNOWN instead of starting Python.
 */
export function resolvePythonInterpreter({
  env = process.env,
  platform = process.platform,
  findExecutables = (command) => executableMatches(command, { env, platform }),
} = {}) {
  const explicitVariables = ["AWT_PYTHON", "PYTHON"];
  for (const variable of explicitVariables) {
    const configured = envValue(env, variable);
    if (typeof configured !== "string" || configured.trim() === "") {
      continue;
    }

    const matches = findExecutables(stripOuterQuotes(configured));
    const command = matches.find((candidate) => !isWindowsStoreAlias(candidate, platform));
    if (!command) {
      throw new Error(
        `${variable} does not resolve to a usable Python executable. ` +
          "Set it to one executable path; Windows Store aliases are not supported.",
      );
    }
    return { command, args: [], source: variable };
  }

  const candidates =
    platform === "win32"
      ? [
          { command: "python.exe", args: [] },
          { command: "py.exe", args: ["-3"] },
        ]
      : [
          { command: "python3", args: [] },
          { command: "python", args: [] },
        ];

  for (const candidate of candidates) {
    const matches = findExecutables(candidate.command);
    const command = matches.find((match) => !isWindowsStoreAlias(match, platform));
    if (command) {
      return { command, args: candidate.args, source: "PATH" };
    }
  }

  throw new Error(
    "No usable Python interpreter found. Set AWT_PYTHON or PYTHON to a real executable. " +
      "Windows Store aliases are ignored.",
  );
}

function summarize(kind, count) {
  if (count === 0) {
    return `${kind}: no issues found.`;
  }
  return `${kind}: ${count} issue${count === 1 ? "" : "s"} found.`;
}

async function withTempProject(callback) {
  const baseDir = await mkdtemp(path.join(tmpdir(), "awt-chatgpt-"));
  try {
    await mkdir(path.join(baseDir, "chapters"), { recursive: true });
    await mkdir(path.join(baseDir, "literature", "reading_notes"), { recursive: true });
    return await callback(baseDir);
  } finally {
    await rm(baseDir, { recursive: true, force: true });
  }
}

function runPythonScript(scriptName, args, { allowIssuesExit = true } = {}) {
  return new Promise((resolve, reject) => {
    const interpreter = resolvePythonInterpreter();
    const child = spawn(
      interpreter.command,
      [...interpreter.args, path.join(SCRIPTS_DIR, scriptName), ...args],
      {
        cwd: REPO_ROOT,
        stdio: ["ignore", "pipe", "pipe"],
      },
    );

    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", (error) => {
      reject(
        new Error(
          `Could not start Python via ${interpreter.source} (${interpreter.command}): ` +
            error.message,
        ),
      );
    });
    child.on("close", (code) => {
      if (code !== 0 && !(allowIssuesExit && code === 1)) {
        reject(new Error(`${scriptName} exited ${code}: ${stderr || stdout}`));
        return;
      }
      resolve({ stdout, stderr, code });
    });
  });
}

function parseJson(stdout, scriptName) {
  try {
    return JSON.parse(stdout);
  } catch (error) {
    throw new Error(`Could not parse JSON from ${scriptName}: ${error.message}`);
  }
}

export async function auditCitations({ chapterText, readingNotesText = "", style = "harvard" }) {
  return withTempProject(async (baseDir) => {
    await writeFile(path.join(baseDir, "chapters", "input.md"), chapterText, "utf8");
    if (readingNotesText.trim()) {
      await writeFile(
        path.join(baseDir, "literature", "reading_notes", "input_NOTES.md"),
        readingNotesText,
        "utf8",
      );
    }

    const { stdout } = await runPythonScript("audit-citations.py", [
      "--base-dir",
      baseDir,
      "--style",
      style,
      "--json",
    ]);
    const payload = parseJson(stdout, "audit-citations.py");
    const issueCount = payload.issue_count ?? payload.issues?.length ?? 0;
    return {
      schema_version: payload.schema_version,
      style: payload.style ?? style,
      mode: payload.mode ?? null,
      issues: payload.issues ?? [],
      issue_count: issueCount,
      summary: summarize("Citation audit", issueCount),
    };
  });
}

export async function checkBritishEnglish({ text, includeFixedText = false }) {
  return withTempProject(async (baseDir) => {
    const inputPath = path.join(baseDir, "chapters", "input.md");
    await writeFile(inputPath, text, "utf8");

    const { stdout } = await runPythonScript("audit-british-english.py", [
      "--base-dir",
      baseDir,
      "--json",
    ]);
    const payload = parseJson(stdout, "audit-british-english.py");
    const result = {
      ...payload,
      summary: summarize("British English check", payload.issue_count ?? 0),
    };

    if (includeFixedText) {
      await runPythonScript("audit-british-english.py", [
        "--base-dir",
        baseDir,
        "--fix",
        "--json",
      ]);
      result.fixed_text = await readFile(inputPath, "utf8");
    }

    return result;
  });
}

export async function reviewParagraphLogic({ text }) {
  return withTempProject(async (baseDir) => {
    await writeFile(path.join(baseDir, "chapters", "input.md"), text, "utf8");
    const { stdout } = await runPythonScript("audit-logic.py", [
      "--base-dir",
      baseDir,
      "--json",
    ]);
    const payload = parseJson(stdout, "audit-logic.py");
    return {
      ...payload,
      summary: summarize("Paragraph logic review", payload.issue_count ?? 0),
    };
  });
}

export async function verifyBibtexReferences({ bibtex }) {
  return withTempProject(async (baseDir) => {
    const bibPath = path.join(baseDir, "references.bib");
    await writeFile(bibPath, bibtex, "utf8");
    const { stdout } = await runPythonScript("verify-refs.py", [
      "--bib",
      bibPath,
      "--json",
    ]);
    const payload = parseJson(stdout, "verify-refs.py");
    return {
      ...payload,
      summary: summarize("BibTeX reference verification", payload.issue_count ?? 0),
    };
  });
}

function sourceLineFor(style, author, title, year) {
  switch (style) {
    case "apa":
      return `${author} (${year}). ${title}. *Publisher*.`;
    case "chicago-author-date":
      return `${author}. ${year}. *${title}*. Publisher.`;
    case "mla":
      return `${author}. *${title}*. Publisher, ${year}.`;
    case "ieee":
      return `[1] ${author}, "${title}," *Journal*, ${year}.`;
    case "vancouver":
      return `1. ${author}. ${title}. Journal. ${year}.`;
    case "gb-t-7714-2015":
      return `${author}. ${title}[J]. *Journal*, ${year}.`;
    case "harvard":
    default:
      return `${author} (${year}) ${title}. *Publisher*.`;
  }
}

export function createReadingNoteTemplate({
  author,
  title,
  year,
  citationStyle = "harvard",
  relevance = "{e.g. Ch3 S3.2 - supports argument about X}",
}) {
  const markdown = `# Reading Notes: ${author} - ${title} (${year})

**Source**: ${sourceLineFor(citationStyle, author, title, year)}
**Date read**: {YYYY-MM-DD}
**Status**: reading
**Relevance**: ${relevance}

---

## Key Arguments

- {Main argument 1}
- {Main argument 2}

## Detailed Notes

### p.{N}-{M}: {Section Title}

> "{direct quote}" (p.{N})

{Your analysis and commentary}

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|-----------------------|
| {term} | {translation if applicable} | {meaning in this text} |

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| {concept} | Ch{N} | S{N.M} | supports / challenges / extends |

## Questions & Follow-ups

- {Open questions for future reading}

---
*Last updated: {YYYY-MM-DD}*
`;

  return {
    schema_version: 1,
    markdown,
    summary: "Reading note template created.",
  };
}
