# Contributing

Contributions should preserve the research record, reproducibility boundaries, and third-party redistribution constraints documented in this repository.

## Before changing anything

1. Read `README.md`, `REPRODUCE.md`, and `reproducibility/EXPERIMENT_INDEX.md`.
2. Check `reproducibility/TRACKING_AUDIT.md` before adding data or generated outputs.
3. Work on a focused branch and keep unrelated local files out of the commit.

## Protected research artifacts

Do not modify Phase 6 splits/manifests, Phase 7 frozen parameters or primary TEST predictions, or the Phase 12/13 freeze manifests as part of routine cleanup or documentation work. A scientifically justified successor method must be recorded as a new phase or explicitly versioned protocol; it must not silently replace frozen evidence.

Never commit raw MOD/JAR archives, third-party source/tool caches, reconstructed external-tool corpora, credentials, private tokens, virtual environments, compiled output, or high-volume regenerable files.

## Pull-request checklist

- Explain the research or documentation purpose of the change.
- List the scripts, inputs, outputs, and summaries affected.
- State whether any frozen artifact changes; if yes, explain why and provide new hashes without overwriting historical records.
- Confirm that reported metrics were copied from tracked summaries and retain their original scope.
- Confirm that no secret, redistribution-sensitive payload, or held-out mapping was added unintentionally.
- Run the relevant script checks and verify all relative Markdown links.

## Reporting issues

Use GitHub Issues for reproducibility problems, documentation gaps, and narrowly scoped research questions. Do not attach third-party payloads or evaluation-private labels to a public report.
