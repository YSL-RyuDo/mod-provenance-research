# Server-Side Multi-Parent Provenance Reconstruction for Heterogeneous Game MOD Packages

Research repository for hierarchical multi-parent provenance reconstruction of heterogeneous game MOD packages.

## Current experiment status

Completed:
- Phase 6: frozen benchmark construction
- Phase 7: frozen identity-neutral provenance method
- Phase 8: bootstrap and ablation analysis
- Phase 9: server and latency evaluation
- Phase 10: StoneDetector compatibility audit and NiCadCross external baseline
- Phase 11A: multi-UNKNOWN controlled robustness benchmark

In progress:
- Phase 11B/C: frozen-method evaluation on multi-UNKNOWN robustness benchmark

## Important reproducibility policy

The primary frozen TEST benchmark and Phase 7 parameters must not be retuned.

Frozen final parameters are stored in:
- `results/phase7g_final_method_parameters.json`
- `reproducibility/phase7g_final_method_parameters.json`

Raw MOD/JAR payloads and large generated datasets are intentionally excluded from Git.
