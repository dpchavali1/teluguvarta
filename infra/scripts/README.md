# infra/scripts — seed and operational scripts. See docs/tickets/T02.md.

`spike3_inference_benchmark.py` — Spike 3 harness (see
`docs/plans/gemini-hetzner-telugu-plan.md` Phase -1). Not run by CI or any
other script; installs nothing on its own. Copy onto the candidate box and
run manually once its prerequisites (llama-cpp-python, sentence-transformers,
a local BGE-M3 + 4B GGUF model) are installed there — see the script's
module docstring.

`fema_openfema_cutover.py`: one-off move of the FEMA source from its RSS feed
to the OpenFEMA API, with cleanup of the RSS-era rows. Dry run unless given
`--apply`; see the module docstring.
