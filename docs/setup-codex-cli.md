# Setup: Codex skills

AWT provides nine Advisory skills for local Codex use. Installing them does
not enable the deterministic enforcement supplied by the separate dsh app.

## Global installation

Install Python 3.9+ and Node.js ^22.12 or >=24. These commands work in a
terminal or Windows PowerShell; substitute `python3` if needed:

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git
cd academic-writing-toolkit
npm ci --prefix guards
python scripts/install-codex-skills.py --install-deps
```

The installer copies the existing canonical catalogue from `.claude/skills/`
into `~/.agents/skills`, the user scope in [OpenAI's skill discovery
documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills).
The skills are available across local projects; another computer needs its
own installation. These are ordinary folders, so the global installation
does not require Windows symlink privileges.

The source checkout remains a tool installation. Open your actual manuscript
folder in Codex and ask, for example, “Use `$review` to review this chapter.”
You do not have to copy your manuscript into the AWT repository.

`--install-deps` creates a private environment under the destination's sibling
`.skills-awt/runtimes/`. Pip downloads the dependencies listed in
`scripts/codex-skills-requirements.txt`; subsequent runs reuse that environment.
Your existing Python environments are not modified. The npm step installs
the repository's locked build dependencies, and the installer compiles the
audit modules afresh using the local TypeScript compiler. It does not install
or launch dsh and never needs a model API key.

For PDF reading and PDF-based audits, also install Poppler so `pdftotext` is
on PATH. The installer verifies reference checks, citation detection,
author-control templates and DOCX/ZIP conversion using fictional text; it
does not test PDF extraction or establish scholarly review quality.

## Updating an existing installation

From the clean AWT tool checkout:

```bash
git pull --ff-only
npm ci --prefix guards
python scripts/install-codex-skills.py --install-deps
python scripts/install-codex-skills.py --verify
```

An unchanged installation keeps its existing skill files and receipt. An
update stages and exercises all nine skills before replacing them, preserves
existing UI metadata/assets, and backs up the previous folders. Other skill
names are left alone. Installed helpers resolve their own scripts and
references; manuscript inputs remain relative to the user's project.

To preview the destination and name collisions without writing or downloading:

```bash
python scripts/install-codex-skills.py --dry-run
```

If you previously installed AWT by another method, or intentionally want to
replace locally edited AWT skills, inspect the listed collisions and run:

```bash
python scripts/install-codex-skills.py --install-deps --replace-existing
```

This option authorises replacement of the nine listed names, including an
unrelated skill with one of those names. Their whole previous folders are
saved first. Symlink/junction targets are refused even with this option.

Some Codex desktop installations or older installers use `~/.codex/skills`
or `$CODEX_HOME/skills`. Use the existing destination consistently, including
when verifying; avoid installing a second copy under a different user root:

```bash
python scripts/install-codex-skills.py --dest ~/.codex/skills --install-deps --replace-existing
python scripts/install-codex-skills.py --dest ~/.codex/skills --verify
```

For a prepared/offline Python environment, install the declared dependencies
yourself and replace `--install-deps` with `--python /path/to/python`. The
compiler dependencies must already be present. No installer operation uses
the network unless `--install-deps` needs to prepare a runtime.

## Receipts and recovery

The installer prints the exact destination, source commit, file count,
receipt and backup location. `sourceDirty` records whether the tool checkout
had local changes. The current receipt stores SHA-256 hashes for all installed
files; `--verify` checks those bytes and runs the bundled helpers again. This
detects accidental changes, not malicious alteration of both files and receipt.

State is outside the skill discovery directory, normally in
`~/.agents/.skills-awt/`. Each transaction contains `before.json`, an
`installation.json` receipt and the original folders under `backup/`. Failed
or unchanged staging is retained there for inspection. Receipts and runtime
notes contain paths specific to the installing computer; keep them local.
Updates also preserve the prior receipt as `previous-installation.json`.

A handled replacement error moves new folders into `rejected/` and restores
the old folders. The previous current receipt is not changed. A power loss or
process termination can interrupt that sequence: stop other installers,
inspect the latest transaction, move any partial new folders aside, and
restore the original folders from that transaction's `backup/`. Keep
`before.json` to check their hashes. Do not delete a backup before checking
it. When restoring an earlier managed installation, restore its saved
`previous-installation.json` as `current.json` too. A leftover `install.lock`
directory causes the next installer to stop;
remove that empty directory only after confirming no install is running and
the interrupted transaction has been inspected.

If runtime setup was interrupted, the installer reports its incomplete
runtime directory. Move that directory aside after inspection and retry
`--install-deps`; already installed skill folders have not been replaced.

Codex normally detects skill updates automatically. If a skill does not
appear, open a new task or restart Codex. `$export` retains its existing
explicit-only invocation policy.

## Available skills

| Skill | Purpose |
|---|---|
| read | Guided reading with page-anchored PDF extraction |
| note | Record structured reading notes |
| map | Show literature coverage and writing progress |
| integrate | Integrate reading notes into chapter drafts |
| edit-contract | Set a bounded edit scope and record revision attempts |
| review | External review or an own-work review in a fresh-context clean room |
| audit | Consistency, claim-positioning and citation-fidelity checks |
| verify-refs | Offline BibTeX checks; online metadata checks only when requested |
| export | Explicitly requested Word and ZIP conversion |

## Project-local use

You can instead open the source repository directly in Codex, which reads
`.agents/skills/`, or create a thesis workspace with `awt init` as described
in the README. This route uses the canonical source tree rather than an
independent global copy. Edit `CLAUDE.md` for that workspace's chapter targets
and reading limits, then run `make sync` to regenerate `AGENTS.md`.
