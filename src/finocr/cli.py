from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from finocr.config import load_toml
from finocr.datasets import (
    FinanceBenchError,
    FinLongDocQAError,
    audit_finlongdocqa_release,
    convert_finlongdocqa,
    convert_financebench,
    load_documents,
    load_selection,
    load_tasks,
    select_financebench_pilot,
    validate_manifests,
    write_inventory_csv,
)
from finocr.io import write_json, write_jsonl
from finocr.phase0 import (
    build_phase0_audit,
    load_manual_checks,
    phase0_audit_markdown,
    write_evidence_packets,
)
from finocr.rendering import RenderingError, render_evidence_pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finocr")
    commands = parser.add_subparsers(dest="command", required=True)

    convert = commands.add_parser(
        "convert-finlongdocqa",
        help="Convert a selected FinLongDocQA v1.1 subset to unified manifests",
    )
    convert.add_argument("--annotations", required=True)
    convert.add_argument("--reports", required=True, help="reports.zip or extracted reports directory")
    convert.add_argument("--selection", required=True)
    convert.add_argument("--materialize-root", required=True)
    convert.add_argument("--output-dir", required=True)
    convert.add_argument("--repository-root", default=".")
    convert.add_argument("--source-version", default="v1.1")
    convert.add_argument("--raw-subset-output")

    validate = commands.add_parser("validate-data", help="Audit unified data manifests")
    validate.add_argument("--documents", required=True)
    validate.add_argument("--tasks", required=True)
    validate.add_argument("--require-files", action="store_true")
    validate.add_argument("--repository-root", default=".")
    validate.add_argument("--output")

    audit = commands.add_parser(
        "audit-finlongdocqa", help="Build the release, pilot, and manual Phase 0 audit"
    )
    audit.add_argument("--annotations", required=True)
    audit.add_argument("--reports", required=True)
    audit.add_argument("--documents", required=True)
    audit.add_argument("--tasks", required=True)
    audit.add_argument("--manual-checks", required=True)
    audit.add_argument("--repository-root", default=".")
    audit.add_argument("--output-json", required=True)
    audit.add_argument("--output-markdown", required=True)
    audit.add_argument("--evidence-output-dir")

    financebench = commands.add_parser(
        "audit-financebench",
        help="Inventory FinanceBench PDFs, build manifests, and select a deterministic pilot",
    )
    financebench.add_argument("--metadata", required=True)
    financebench.add_argument("--questions", required=True)
    financebench.add_argument("--pdf-dir", required=True)
    financebench.add_argument("--output-dir", required=True)
    financebench.add_argument("--company-count", type=int, default=4)
    financebench.add_argument("--reports-per-company", type=int, default=3)
    financebench.add_argument("--minimum-years", type=int, default=8)

    render = commands.add_parser(
        "render-pages", help="Render evidence pages from verified PDFs with Poppler"
    )
    render.add_argument("--documents", required=True)
    render.add_argument("--tasks", required=True)
    render.add_argument("--output-dir", required=True)
    render.add_argument("--repository-root", default=".")
    render.add_argument("--dpi", type=int, default=200)

    plan = commands.add_parser("plan", help="Create the dry-run experiment job matrix")
    plan.add_argument("--experiment", required=True)
    plan.add_argument("--models", required=True)
    plan.add_argument("--documents", required=True)
    plan.add_argument("--output", required=True)

    native = commands.add_parser("native-baseline", help="Extract every native PDF page and run within-report BM25")
    native.add_argument("--documents", required=True)
    native.add_argument("--tasks", required=True)
    native.add_argument("--output-dir", required=True, help="New run directory outside Git; existing paths are rejected")
    native.add_argument("--repository-root", default=".")
    native.add_argument("--pdf-dir", help="Rebase PDF basenames while retaining manifest IDs and checksums")
    native.add_argument("--k1", type=float, default=1.2)
    native.add_argument("--b", type=float, default=0.75)
    native.add_argument("--k", nargs="+", type=int, default=[1, 3, 5])
    native.add_argument("--expected-documents", type=int)
    native.add_argument("--expected-pages", type=int)
    native.add_argument("--expected-questions", type=int)
    native.add_argument("--skip-evaluation", action="store_true")

    evaluate = commands.add_parser("evaluate-retrieval", help="Score saved predictions offline against evidence labels")
    evaluate.add_argument("--predictions", required=True)
    evaluate.add_argument("--tasks", required=True)
    evaluate.add_argument("--output", required=True, help="New metrics file; no overwrite")
    evaluate.add_argument("--k", nargs="+", type=int, default=[1, 3, 5])

    stopwords = commands.add_parser("compare-stopwords", help="Reproduce cached native BM25 and compare a function-word ablation")
    stopwords.add_argument("--baseline-dir", required=True)
    stopwords.add_argument("--output-dir", required=True)
    stopwords.add_argument("--tasks", help="Original frozen task manifest; defaults to recorded baseline path")
    stopwords.add_argument("--repository-root", default=".")
    expansion = commands.add_parser("compare-query-expansion", help="Reproduce both cached controls and test fixed financial question terms")
    expansion.add_argument("--baseline-dir", required=True)
    expansion.add_argument("--stopword-dir", required=True, help="Completed stopword comparison for the same baseline")
    expansion.add_argument("--output-dir", required=True, help="New comparison directory outside Git")
    expansion.add_argument("--tasks", help="Original frozen task manifest; defaults to recorded baseline path")
    expansion.add_argument("--repository-root", default=".")
    return parser


def _run_convert(args: argparse.Namespace) -> int:
    selected_keys, selection_metadata = load_selection(args.selection)
    conversion = convert_finlongdocqa(
        args.annotations,
        args.reports,
        selected_keys,
        args.materialize_root,
        args.repository_root,
        source_version=args.source_version,
        selection_metadata=selection_metadata,
    )
    output = Path(args.output_dir)
    documents_path = output / "documents.jsonl"
    tasks_path = output / "tasks.jsonl"
    write_jsonl(documents_path, (document.to_dict() for document in conversion.documents))
    write_jsonl(tasks_path, (task.to_dict() for task in conversion.tasks))
    if args.raw_subset_output:
        write_jsonl(args.raw_subset_output, conversion.raw_records)
    print(
        json.dumps(
            {
                "documents": len(conversion.documents),
                "tasks": len(conversion.tasks),
                "documents_path": str(documents_path),
                "tasks_path": str(tasks_path),
                "source_page_index_base": 1,
                "internal_page_index_base": 0,
                "pdfs_materialized": 0,
            },
            indent=2,
        )
    )
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    result = validate_manifests(
        load_documents(args.documents),
        load_tasks(args.tasks),
        require_files=args.require_files,
        repository_root=args.repository_root,
    )
    value = result.to_dict()
    if args.output:
        write_json(args.output, value)
    print(json.dumps(value, indent=2))
    return 0 if result.valid else 1


def _run_audit(args: argparse.Namespace) -> int:
    documents = load_documents(args.documents)
    tasks = load_tasks(args.tasks)
    manifest_audit = validate_manifests(
        documents,
        tasks,
        require_files=True,
        repository_root=args.repository_root,
    )
    release_audit = audit_finlongdocqa_release(args.annotations, args.reports)
    checks = load_manual_checks(args.manual_checks)
    audit = build_phase0_audit(
        release_audit, manifest_audit, documents, tasks, checks
    )
    write_json(args.output_json, audit)
    Path(args.output_markdown).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_markdown).write_text(
        phase0_audit_markdown(audit), encoding="utf-8"
    )
    evidence_packets = []
    if args.evidence_output_dir:
        evidence_packets = write_evidence_packets(
            args.reports, tasks, checks, args.evidence_output_dir
        )
    print(
        json.dumps(
            {
                "status": audit["status"],
                "structurally_valid": manifest_audit.valid,
                "ocr_ready": audit["ocr_readiness"]["ready"],
                "manual_review": audit["manual_review"]["status_counts"],
                "evidence_packets": len(evidence_packets),
                "output_json": args.output_json,
                "output_markdown": args.output_markdown,
            },
            indent=2,
        )
    )
    return 0


def _run_render(args: argparse.Namespace) -> int:
    written = render_evidence_pages(
        load_documents(args.documents),
        load_tasks(args.tasks),
        args.output_dir,
        repository_root=args.repository_root,
        dpi=args.dpi,
    )
    print(json.dumps({"rendered_pages": len(written), "dpi": args.dpi}, indent=2))
    return 0


def _run_financebench(args: argparse.Namespace) -> int:
    conversion = convert_financebench(args.metadata, args.questions, args.pdf_dir)
    output = Path(args.output_dir)
    manifests = output / "manifests"
    output.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)

    write_inventory_csv(output / "document_inventory.csv", conversion.inventory)
    write_jsonl(output / "document_inventory.jsonl", conversion.inventory)
    write_jsonl(manifests / "documents.jsonl", (item.to_dict() for item in conversion.documents))
    write_jsonl(manifests / "tasks.jsonl", (item.to_dict() for item in conversion.tasks))

    selected = []
    pilot_errors: list[dict[str, object]] = []
    try:
        selected = select_financebench_pilot(
            conversion.inventory,
            company_count=args.company_count,
            reports_per_company=args.reports_per_company,
            minimum_years=args.minimum_years,
        )
    except FinanceBenchError as exc:
        pilot_errors.append({"code": "pilot_selection_failed", "message": str(exc)})

    selected_ids = {row["doc_id"] for row in selected}
    pilot_documents = [item for item in conversion.documents if item.doc_id in selected_ids]
    pilot_tasks = [item for item in conversion.tasks if item.doc_id in selected_ids]
    write_inventory_csv(output / "pilot_selection.csv", selected)
    write_jsonl(manifests / "pilot_documents.jsonl", (item.to_dict() for item in pilot_documents))
    write_jsonl(manifests / "pilot_tasks.jsonl", (item.to_dict() for item in pilot_tasks))

    audit = validate_manifests(conversion.documents, conversion.tasks, require_files=True)
    if conversion.source_document_count != len(conversion.documents):
        conversion.issues.append({"code": "document_count_mismatch"})
    if conversion.source_question_count != len(conversion.tasks):
        conversion.issues.append({"code": "question_count_mismatch"})
    if selected and not pilot_tasks:
        pilot_errors.append({"code": "pilot_has_no_questions", "message": "Selected reports have no annotated QA cases"})
    sectors = sorted({str(row.get("sector") or "Unknown") for row in selected})
    pilot_warnings = []
    if selected and ("Unknown" in sectors or len(sectors) < args.company_count):
        pilot_warnings.append({"code": "limited_sector_coverage", "sectors": sectors})
    unannotated = [row["doc_name"] for row in selected if not row["qa_case_count"]]
    if unannotated:
        pilot_warnings.append({"code": "pilot_reports_without_questions", "documents": unannotated})
    blocking_issues = [issue for issue in conversion.issues if issue["code"] != "pdf_without_metadata"]
    ready = audit.valid and not blocking_issues and not pilot_errors
    issue_counts: dict[str, int] = {}
    for issue in conversion.issues:
        code = str(issue["code"])
        issue_counts[code] = issue_counts.get(code, 0) + 1
    summary = {
        "phase": 0,
        "dataset": "FinanceBench",
        "status": "ready_for_native_text_baseline" if ready else "blocked",
        "source_documents": conversion.source_document_count,
        "source_questions": conversion.source_question_count,
        "documents": len(conversion.documents),
        "annual_reports": sum(row["doc_type"] in {"10k", "10k_annualreport"} for row in conversion.inventory),
        "questions": len(conversion.tasks),
        "pdfs_present": sum(bool(row["pdf_exists"]) for row in conversion.inventory),
        "valid_pdfs": sum(bool(row["pdf_valid"]) for row in conversion.inventory),
        "native_text_documents": sum(bool(row["native_text_available"]) for row in conversion.inventory),
        "evidence_page_errors": sum(error["code"] == "invalid_evidence_page" for error in audit.errors),
        "issue_counts": dict(sorted(issue_counts.items())),
        "ingestion_issues": conversion.issues,
        "blocking_ingestion_issues": blocking_issues,
        "manifest_validation": audit.to_dict(),
        "pilot": {
            "selection_rule": "highest annual-report QA coverage with sector diversity; earliest, middle, and latest usable year",
            "document_count": len(pilot_documents),
            "task_count": len(pilot_tasks),
            "sectors": sectors,
            "errors": pilot_errors,
            "warnings": pilot_warnings,
            "tasks_by_document": {row["doc_name"]: row["qa_case_count"] for row in selected},
            "parameters": {
                "company_count": args.company_count,
                "reports_per_company": args.reports_per_company,
                "minimum_years": args.minimum_years,
            },
            "companies": sorted({str(row["company"]) for row in selected}),
            "documents": [row["doc_name"] for row in selected],
        },
    }
    write_json(output / "audit.json", summary)
    lines = [
        "# FinanceBench Phase 0 audit",
        "",
        f"**Status:** `{summary['status']}`",
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| Metadata documents | {summary['documents']} |",
        f"| Annual reports | {summary['annual_reports']} |",
        f"| QA cases | {summary['questions']} |",
        f"| PDFs present | {summary['pdfs_present']} |",
        f"| Valid PDFs | {summary['valid_pdfs']} |",
        f"| Documents with sampled native text | {summary['native_text_documents']} |",
        f"| Invalid evidence-page references | {summary['evidence_page_errors']} |",
        "",
        "## Deterministic pilot",
        "",
        "The selector prioritizes annual-report QA coverage, then preserves sector diversity. "
        "For each company it selects the earliest, middle, and latest usable annual report.",
        "",
        "| Company | Year | Document | Pages | QA cases |",
        "|---|---:|---|---:|---:|",
    ]
    for row in sorted(selected, key=lambda value: (str(value["company"]), int(value["fiscal_year"]))):
        lines.append(
            f"| {row['company']} | {row['fiscal_year']} | `{row['doc_name']}` | "
            f"{row['page_count']} | {row['qa_case_count']} |"
        )
    lines.extend([
        "",
        "## Diagnostics",
        "",
    ])
    for issue in blocking_issues + audit.errors + pilot_errors + pilot_warnings:
        lines.append(f"- `{issue['code']}`: {json.dumps(issue, ensure_ascii=False, sort_keys=True)}")
    if not (blocking_issues or audit.errors or pilot_errors or pilot_warnings):
        lines.append("No blocking issues or pilot warnings.")
    lines.extend([
        "",
        "## Gate",
        "",
        "Proceed to the native-PDF-text baseline only when the status is "
        "`ready_for_native_text_baseline`. OCR installation remains the following phase.",
        "",
    ])
    (output / "AUDIT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if ready else 1


def _run_plan(args: argparse.Namespace) -> int:
    try:
        from finocr.pipelines import build_experiment_jobs
    except ImportError as exc:
        raise RuntimeError(
            "Experiment planning modules were not part of this Phase 0 overlay. "
            "Merge this overlay into the complete starter repository to use `finocr plan`."
        ) from exc

    experiment = load_toml(args.experiment)["experiment"]
    models = load_toml(args.models)["models"]
    jobs = build_experiment_jobs(
        load_documents(args.documents),
        models,
        page_sizes=list(experiment["page_sizes"]),
        windows_per_size=int(experiment["windows_per_size"]),
        seed=int(experiment["seed"]),
    )
    write_jsonl(args.output, (job.to_dict() for job in jobs))
    print(f"Wrote {len(jobs)} jobs to {Path(args.output)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "convert-finlongdocqa":
            return _run_convert(args)
        if args.command == "validate-data":
            return _run_validate(args)
        if args.command == "audit-finlongdocqa":
            return _run_audit(args)
        if args.command == "audit-financebench":
            return _run_financebench(args)
        if args.command == "render-pages":
            return _run_render(args)
        if args.command == "plan":
            return _run_plan(args)
        if args.command == "native-baseline":
            from finocr.pipelines.native_baseline import run_native_baseline
            result = run_native_baseline(
                args.documents, args.tasks, args.output_dir, repository_root=args.repository_root,
                pdf_dir=args.pdf_dir, k1=args.k1, b=args.b, ks=tuple(args.k),
                expected_documents=args.expected_documents, expected_pages=args.expected_pages,
                expected_questions=args.expected_questions, skip_evaluation=args.skip_evaluation,
                progress=lambda message: print(message, file=sys.stderr, flush=True),
            )
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "complete" else 1
        if args.command == "evaluate-retrieval":
            from finocr.evaluation.retrieval import evaluate_retrieval
            from finocr.io import read_jsonl
            from finocr.pipelines.native_baseline import load_evidence_labels
            if Path(args.output).exists():
                raise ValueError("Metrics output already exists; choose a new path")
            metrics = evaluate_retrieval(read_jsonl(args.predictions), load_evidence_labels(Path(args.tasks)), ks=tuple(args.k))
            write_json(args.output, metrics)
            print(json.dumps({"question_count": metrics["question_count"], "output": args.output}, indent=2))
            return 0
        if args.command == "compare-stopwords":
            from finocr.pipelines.stopword_comparison import compare_stopwords
            result = compare_stopwords(
                args.baseline_dir, args.output_dir, tasks_path=args.tasks,
                repository_root=args.repository_root,
                progress=lambda message: print(message, file=sys.stderr, flush=True),
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command == "compare-query-expansion":
            from finocr.pipelines.stopword_comparison import compare_query_expansion
            result = compare_query_expansion(
                args.baseline_dir, args.stopword_dir, args.output_dir, tasks_path=args.tasks,
                repository_root=args.repository_root,
                progress=lambda message: print(message, file=sys.stderr, flush=True),
            )
            print(json.dumps(result, indent=2))
            return 0
    except (FinanceBenchError, FinLongDocQAError, RenderingError, RuntimeError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
