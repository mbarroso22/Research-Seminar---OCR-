"""Evaluator-only arithmetic, typed quantities, citations and private-key checks.

These helpers establish mechanical checks, not semantic correctness or an LLM judge.
Synthetic validation imports mechanical helpers; it never loads a private key.
"""
from __future__ import annotations
import ast
import hashlib
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path

SCALES = {"unit": Decimal(1), "thousand": Decimal(1000), "million": Decimal(10)**6,
          "billion": Decimal(10)**9}


def decimal_string(value: str) -> Decimal:
    value = unicodedata.normalize("NFKC", value).strip().replace("−", "-")
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1].strip()
    # Units/currency are separate typed fields; never silently discard them.
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value):
        raise ValueError("Expected signed decimal with optional grouping commas")
    if negative and value[:1] in "+-":
        raise ValueError("Double sign")
    result = Decimal(value.replace(",", ""))
    return -result if negative else result


def arithmetic(expression: str, operands: dict[str, Decimal]) -> Decimal:
    if len(expression) > 256:
        raise ValueError("Expression too long")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 64:
        raise ValueError("Expression too complex")
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Name) and node.id in operands: return operands[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            return left / right
        raise ValueError("Only named operands, constants and + - * / allowed")
    try:
        with localcontext() as ctx:
            ctx.prec = 40
            result = visit(tree)
            if not result.is_finite() or abs(result) > Decimal("1e30"):
                raise ValueError("Arithmetic result out of bounds")
            return result
    except (ArithmeticError, InvalidOperation) as exc:
        raise ValueError("Invalid arithmetic") from exc


def quantity_check(actual: dict, expected: dict) -> dict:
    """Expected value/quantum is in its declared scale. HALF_UP, no relative error."""
    checks = {k: actual.get(k) == expected[k] for k in ("unit", "currency", "fiscal_year")}
    try:
        a, e = decimal_string(actual["value"]), decimal_string(expected["value"])
        a *= SCALES[actual["scale"]] / SCALES[expected["scale"]]
        q = Decimal(expected["quantum"])
        if q <= 0: raise ValueError("Quantum must be positive")
        checks["sign"] = a.is_signed() == e.is_signed() or a == e == 0
        checks["final_number"] = a == 0 if expected.get("exact_zero") else (
            (a / q).quantize(Decimal(1), rounding=ROUND_HALF_UP) ==
            (e / q).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        checks["unit_scale_valid"] = True
    except (KeyError, TypeError, ValueError, ArithmeticError):
        checks.update(sign=False, final_number=False, unit_scale_valid=False)
    checks["pass"] = all(checks.values())
    return checks


def citation_check(pointer: dict, included_pages: dict[int, str]) -> bool:
    page = pointer.get("page_id")
    span = pointer.get("span")
    normalize = lambda s: re.sub(r"\s+", " ", s).strip()
    return (type(page) is int and page >= 0 and page in included_pages and isinstance(span, str)
            and bool(normalize(span)) and normalize(span) in normalize(included_pages[page]))


def check_private_key(key_path: Path, pdf_root: Path, tasks_path: Path, *, freeze: bool = False) -> dict:
    """Read-only audit. Source PDF hashes/counts and original task bytes must match.

    Freeze refuses unresolved source/reference issues or absent reviewer decisions.
    It never invents agreement or changes upstream labels.
    """
    from pypdf import PdfReader
    key = json.loads(key_path.read_text(encoding="utf-8"))
    if hashlib.sha256(tasks_path.read_bytes()).hexdigest() != key["tasks_sha256"]:
        raise ValueError("Original task checksum mismatch")
    tasks = {t["task_id"]: t for t in (json.loads(l) for l in tasks_path.read_text(encoding="utf-8").splitlines() if l)}
    items = key["items"]
    if len(items) != 24 or len({i['task_id'] for i in items}) != 24 or set(tasks) != {i["task_id"] for i in items}:
        raise ValueError("Expected exactly the original 24 tasks")
    for source in key["sources"]:
        path = pdf_root / source["filename"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"PDF checksum mismatch: {source['filename']}")
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("Empty-password decryption failed")
        if len(reader.pages) != source["page_count"]:
            raise ValueError("PDF page count mismatch")
    source_ids = {s["doc_id"] for s in key["sources"]}
    source_counts = {s["doc_id"]:s['page_count'] for s in key['sources']}
    for item in items:
        task = tasks[item["task_id"]]
        if item["doc_id"] != task["doc_id"] or item["doc_id"] not in source_ids or item["upstream_answers"] != task["answers"] or item["upstream_evidence_pages"] != task["evidence_pages"]:
            raise ValueError("Upstream labels or report identity changed")
        if not item["source_review"] or not item["support_requirements"]:
            raise ValueError("Missing source/support review")
        if item.get('question') != task.get('question'):
            raise ValueError('Question changed')
        if any(type(p) is not int or p < 0 or p >= source_counts[item['doc_id']] for p in item.get('source_pages', [])):
            raise ValueError('Source page outside zero-based report bounds')
        for calculation in item.get('calculations', []):
            operands = {q['id']: decimal_string(q['value']) for q in item['quantities']}
            found = arithmetic(calculation['expression'], {k:operands[k] for k in calculation['operand_ids']})
            if found != Decimal(calculation['unrounded_value']):
                raise ValueError('Private expected arithmetic does not reconcile')
    if any(i['adjudication_status'] not in {'ready','hold','unscorable'} for i in items):
        raise ValueError('Unknown adjudication status')
    unscorable = [i['task_id'] for i in items if i['adjudication_status']=='unscorable']
    if any(i['adjudication_status']=='unscorable' and not i.get('resolution') for i in items):
        raise ValueError('Prospective unscorable decision requires a recorded resolution')
    held = [i["task_id"] for i in items if i["adjudication_status"] == "hold"]
    reviewers = key.get("reviewer_signoff", {})
    if freeze and (held or not reviewers.get("reviewer") or not reviewers.get("decisions_sha256")):
        raise ValueError("Private freeze blocked: resolve held items and record researcher source-review signoff first")
    return {"kind": "evaluator_preparation", "tasks": 24, "sources": len(key["sources"]),
            "page_index_base": 0, "held_items": held, "unscorable_items":unscorable,
            "freeze_ready": not held and bool(reviewers.get("reviewer")) and bool(reviewers.get('decisions_sha256')),
            "private_key_sha256": hashlib.sha256(key_path.read_bytes()).hexdigest(),
            "generation_executed": False}
