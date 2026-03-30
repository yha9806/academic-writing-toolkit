# Academic Writing Project

This file provides instructions for AI coding agents working in this repository.

## Skill Discovery
Skills are located in `.agents/skills/`. Each `.md` file in that directory defines a slash-command skill for academic writing workflows (reading, note-taking, chapter drafting, verification, etc.).

## Project Overview
This project uses the academic-writing-toolkit skills for structured research and thesis writing.

## Directories
- Chapters: `chapters/`
- Literature PDFs: `literature/`
- Reading notes: `literature/reading_notes/`
- Export output: `final_output/`

## Targets
- Total word count target: 80,000
- Per-chapter targets: edit the table below

| Chapter | Title | Target Words |
|---------|-------|-------------|
| Ch1 | Introduction | 5,000 |
| Ch2 | Background | 10,000 |
| Ch3 | Framework | 12,000 |
| Ch4 | Methodology | 8,000 |
| Ch5 | Results | 15,000 |
| Ch6 | Discussion | 12,000 |
| Ch7 | Practice | 8,000 |
| Ch8 | Conclusion | 5,000 |

## Reading Constraints
- Max pages per read invocation: 15
- Max pages per conversation: 90
- Always complete reading notes before modifying chapters

## Writing Principles
- Read first, write later — finish reading notes before editing chapters
- Each source must have an independent notes file in `literature/reading_notes/`
- Use British English for thesis text
- Notes files follow the standardised format (see `literature/reading_notes/_template_NOTES.md`)
