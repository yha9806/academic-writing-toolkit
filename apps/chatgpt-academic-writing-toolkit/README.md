# Academic Writing Toolkit ChatGPT App

Tool-only ChatGPT App MCP server for academic writing checks.

## Tools

- `audit_citations`: checks pasted chapter text against pasted reading-note source lines.
- `check_british_english`: finds conservative US-to-British spelling replacements.
- `review_paragraph_logic`: flags short paragraphs and repeated adjacent transition words.
- `verify_bibtex_references`: validates pasted BibTeX records offline.
- `create_reading_note_template`: creates the standard reading-notes Markdown scaffold.

The server processes user-provided text through temporary files only. It does not read local thesis files, persist user submissions, authenticate users, or call external metadata APIs.

## Local Development

```sh
npm install
npm test
npm start
```

The server listens on `http://127.0.0.1:3000/mcp` by default. Override with:

```sh
HOST=0.0.0.0 PORT=3000 npm start
```

## Docker

Build from the repository root so the image includes both this app and the shared Python scripts:

```sh
docker build -f apps/chatgpt-academic-writing-toolkit/Dockerfile -t academic-writing-toolkit-chatgpt-app .
docker run --rm -p 3000:3000 academic-writing-toolkit-chatgpt-app
```

## Submission

OpenAI app review requires a public HTTPS MCP URL, not a local endpoint. Deploy this app to a public host, then submit the hosted `/mcp` URL through OpenAI Platform Apps Manage.

The review import file is `chatgpt-app-submission.json`.
