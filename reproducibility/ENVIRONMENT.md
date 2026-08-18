# Reproducibility Environment

Two environment snapshots exist because the research was run across WSL and Windows system-benchmark contexts. They must not be treated as one simultaneous environment.

## WSL/toolchain record

- OS/kernel: WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
- Python: 3.12.3
- Java: OpenJDK 11.0.31
- Git: 2.43.0

The exact captured strings are retained in `system.txt`, `python_version.txt`, `java_version.txt`, and `git_version.txt` in this directory.

`requirements_freeze.txt` is a compact later Python snapshot containing NumPy 2.5.2 and pandas 3.0.5. It is preserved as an environment record, but it is not claimed to be the full Phase 9 server environment.

## Phase 9 tested environment

Phase 9 performance summaries record:

- Windows Python 3.10.6
- Intel CPU, 20 physical / 28 logical cores
- 34,031,173,632 bytes total system memory

The full package freeze used for those server/system stages is `results/phase9_environment_freeze.txt`. Root `requirements.txt` mirrors that tested full environment for convenience. It includes NumPy 2.2.6, pandas 2.3.2, FastAPI 0.141.1, Uvicorn 0.52.1, SciPy 1.15.3, scikit-learn 1.7.2, Pillow 11.3.0, ImageHash 4.3.2, and the complete transitive environment.

Exact timing reproduction still depends on operating system, CPU, filesystem/cache state, and server process configuration. Treat performance summaries as results from the recorded host rather than universal constants.

## External tools

- Phase 3D requires Java to compile/run `tools/phase3d/JavapBatch.java`.
- Phase 10 uses a separate Open-NiCad/NiCadCross 7.0 installation configured for Java functions with the default/blindrename threshold 0.30.
- Git and network access are required only for restoring public repository snapshots/downloads; those caches are intentionally excluded.

## Recommended isolation

Use separate virtual environments for historical exact-server reproduction and any modern rerun. Do not silently upgrade the pinned Phase 9 environment and compare the resulting timing as though the environments were identical.
