import * as z from "zod/v4";

const MAX_TEXT_CHARS = 100_000;
const READ_ONLY_ANNOTATIONS = {
  readOnlyHint: true,
  openWorldHint: false,
  destructiveHint: false,
};

const issueListSchema = z.array(z.record(z.string(), z.unknown()));
const citationStyleSchema = z
  .enum([
    "harvard",
    "apa",
    "chicago-author-date",
    "mla",
    "ieee",
    "vancouver",
    "gb-t-7714-2015",
  ])
  .default("harvard");

export const TOOL_DEFINITIONS = {
  audit_citations: {
    title: "Audit citations",
    description:
      "Use this when the user wants to check pasted academic prose against pasted reading-note source lines for citation consistency.",
    inputSchema: {
      chapterText: z
        .string()
        .min(1)
        .max(MAX_TEXT_CHARS)
        .describe("Chapter or draft text to audit."),
      readingNotesText: z
        .string()
        .max(MAX_TEXT_CHARS)
        .optional()
        .default("")
        .describe("Reading-note text containing one or more **Source** lines."),
      style: citationStyleSchema.describe("Citation style to apply."),
    },
    outputSchema: {
      schema_version: z.number(),
      style: z.string().nullable(),
      mode: z.string().nullable().optional(),
      issue_count: z.number(),
      issues: issueListSchema,
      summary: z.string(),
    },
    annotations: READ_ONLY_ANNOTATIONS,
  },
  check_british_english: {
    title: "Check British English",
    description:
      "Use this when the user wants conservative British English spelling checks for pasted academic text.",
    inputSchema: {
      text: z.string().min(1).max(MAX_TEXT_CHARS).describe("Academic text to check."),
      includeFixedText: z
        .boolean()
        .optional()
        .default(false)
        .describe("Return a conservative fixed-text preview."),
    },
    outputSchema: {
      schema_version: z.number(),
      issue_count: z.number(),
      issues: issueListSchema,
      fixed_text: z.string().optional(),
      summary: z.string(),
    },
    annotations: READ_ONLY_ANNOTATIONS,
  },
  review_paragraph_logic: {
    title: "Review paragraph logic",
    description:
      "Use this when the user wants a deterministic paragraph-level logic review of pasted chapter prose.",
    inputSchema: {
      text: z.string().min(1).max(MAX_TEXT_CHARS).describe("Chapter prose to review."),
    },
    outputSchema: {
      schema_version: z.number(),
      issue_count: z.number(),
      issues: issueListSchema,
      summary: z.string(),
    },
    annotations: READ_ONLY_ANNOTATIONS,
  },
  verify_bibtex_references: {
    title: "Verify BibTeX references",
    description:
      "Use this when the user wants offline validation of pasted BibTeX reference records.",
    inputSchema: {
      bibtex: z.string().min(1).max(MAX_TEXT_CHARS).describe("BibTeX records to validate."),
    },
    outputSchema: {
      schema_version: z.number(),
      entries: z.number(),
      issue_count: z.number(),
      issues: issueListSchema,
      verified: issueListSchema,
      metadata_checks: issueListSchema,
      online_sources: z.array(z.string()),
      summary: z.string(),
    },
    annotations: READ_ONLY_ANNOTATIONS,
  },
  create_reading_note_template: {
    title: "Create reading note template",
    description:
      "Use this when the user wants a standard reading-notes Markdown template for a source.",
    inputSchema: {
      author: z.string().min(1).max(300).describe("Author name or author list."),
      title: z.string().min(1).max(500).describe("Source title."),
      year: z.string().min(1).max(20).describe("Publication year or date label."),
      citationStyle: citationStyleSchema.describe("Citation style for the Source line hint."),
      relevance: z
        .string()
        .max(500)
        .optional()
        .default("{e.g. Ch3 S3.2 - supports argument about X}")
        .describe("Optional chapter or argument relevance note."),
    },
    outputSchema: {
      schema_version: z.number(),
      markdown: z.string(),
      summary: z.string(),
    },
    annotations: READ_ONLY_ANNOTATIONS,
  },
};
