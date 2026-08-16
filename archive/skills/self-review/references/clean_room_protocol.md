# Clean-Room Self-Review Protocol

Use this protocol whenever reviewing the user's own work.

## Source Boundary

The review may use only:

- files listed under `allowed_sources`
- text pasted in the current request and explicitly identified as review material
- deterministic checker outputs generated from allowed sources

Codex can complete the review from these sources alone. External model output is never required.

## Enhanced Advisory Review

An API-key-backed external model pass is optional. Use it only when:

- the user explicitly enables it
- the manifest permits external advisory review
- the source subset is listed
- the API key is stored in an environment variable
- the output is labelled advisory

External output can suggest reviewer risks, but it cannot support claims.

The review must not use:

- prior chat memory
- unstated project assumptions
- model background knowledge as evidence
- unpublished notes not listed in the manifest
- untracked local files not listed in the manifest
- generated reviewer suggestions as final evidence
- external model output as source support
- API key values stored in files

## Finding Categories

### Supported by packet

Use this only when the finding is directly anchored to a listed source.

Required fields:

- finding
- source anchor
- claim ID or section
- severity
- action

### Not supported by packet

Use this when a claim, number, interpretation, or revision need cannot be anchored to the packet.

Required fields:

- claim or need
- missing source
- risk
- action

### Reviewer-risk inference

Use this for plausible reviewer objections inferred from the packet, not for claims of fact.

Required fields:

- risk
- basis in packet
- why it matters
- action

## Anti-Contamination Tests

Before finalising the report, ask:

1. Did I use any fact that is not in the packet?
2. Did I turn prior conversation context into evidence?
3. Did I treat my own general knowledge as source support?
4. Did I explain every supported finding with a source anchor?
5. Did I mark missing support as a gap rather than silently filling it?
