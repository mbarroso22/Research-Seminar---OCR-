# Research checkpoint — prospective E2E v8

This is an allowlisted code/synthetic-test and preregistration checkpoint for the OCR / FinanceBench research project. It is not the complete financial experiment bundle. `study_lock.json` records the full private study bundle hashes; missing financial assets in this Git subset are intentional, so `run_pilot.py --check` cannot pass here.

No new v8 model calls/results exist at registration. Four additional-to-v6 questions are drawn from the prior Phase2 pool: Nike FY2019, Microsoft FY2016, American Water Works FY2022 and PayPal FY2022. This is a prospective evaluation of the frozen integrated workflow, not unseen questions/companies or independent human-certified accuracy. `study_plan.json` freezes retrieval, schema, source-reference lock, identity and budget. Do not change matching to accommodate pilot outputs.

Run the public synthetic tests, requiring only Python's standard library:

```powershell
py -m unittest discover -s component -p test_binding_v3.py -v
py -m unittest discover -s . -p test_contract.py -v
```

20 matching guards and 3 contract guards. `component/test_binding_v3.py` builds fictional ACME geometry; it does not use real financial document excerpts. Code is byte-identical to the packaged matcher/calculators. `.gitattributes` disables newline conversion to preserve SHA-256 byte identity.

Omitted: PDFs, page images, native page text/layouts, real claims/answers, API responses, credentials, resource endpoints, logs and environment files. No credential is required to run tests. Full pilot execution uses the separately delivered ZIP, which includes `prepared/` and references. Hash-only provenance here does not reconstruct those assets.

`prior_results/` contains scoped **previous** summaries. V3 development replay: 24 saved responses, 14 candidates (not newly generated accuracy). Corrected locked cell-claim validation: 96/108 supported variants accepted and 0/270 invalid accepted; 12 unsupported variants remain held. The 378 variants share 18 source cells and are not independent questions. An original duplicate-row fixture construction error was corrected without changing matcher code; the corrected rerun is not another independent cohort. V2 context-policy controls were newly imposed during this comparison. V7: 24 replay outputs and 378 fixture results reproduced, no new model calls; source_verified=false and independent human source/formula review pending. Supplemental claims stay held.

The full v8 runner's 16 mocked transport/integration guards are tested in the delivery bundle, not included as runnable tests here because some guard checks require full frozen assets. No model-ranking or full-answer correctness claim follows from these checkpoint summaries.
