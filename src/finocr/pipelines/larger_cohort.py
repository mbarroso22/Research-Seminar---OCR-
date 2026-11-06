"""Freeze and validate one larger exploratory cohort without opening labels in retrieval."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from itertools import groupby
from pathlib import Path
import hashlib
import json
import shutil
import uuid

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.larger_spec import SPEC
from finocr.pipelines.native_baseline import code_provenance
from finocr.pipelines.ocr_data import coverage, full_render, inside, require, validate_text_record
from finocr.pipelines.ocr_device import device_condition
from finocr.pipelines.report_ocr import validate_commit
from finocr.pipelines.report_rendering import file_identity
from finocr.pipelines.section_comparison import _by_task, _check_saved, _validate_pages
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, TOKENIZER_VERSION, TOKEN_PATTERN
from finocr.retrieval.query_expansion import expand_query, policy_record as expansion_policy
from finocr.retrieval.semantic import policy_record as encoder_policy
from finocr.retrieval.stopwords import tokenize_without_stopwords


def study_policy():
    encoder = encoder_policy()
    require(encoder['sha256'] == '6e151c7af4624e633876c4e500fd56a63444e04a6faff971f43740e82b5d3b96'
            and expansion_policy()['sha256'] == '80414d370839eceef3dc5c8574b57d65a22f7551ddad520c263dc4c15c67f1a3',
            'Previously fixed encoder or expansion policy changed')
    record = {
        'study': SPEC['experiment'], 'group': SPEC['group'], 'totals': SPEC['totals'],
        'encoder_settings': {k: v for k, v in encoder.items() if k not in {'cohort', 'sha256'}},
        'encoder_settings_original_policy_sha256': encoder['sha256'],
        'expansion': expansion_policy(), 'primary_k': 5, 'diagnostic_ks': [1, 3],
        'primary': 'question-weighted macro Recall@5: GPU OCR minus native, frozen expansion-v1 BM25',
        'bootstrap': {**SPEC['bootstrap'], 'cluster': 'company', 'interval': '95% percentile',
                      'estimands': ['question-weighted paired delta', 'equal-company paired delta']},
        'gate': None, 'interpretation': 'separate exploratory study; original-pilot gate failure unchanged',
    }
    record['sha256'] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return record


def totals():
    return {k: SPEC['totals'][k] for k in ('documents', 'pages', 'questions')}


def new_output(path, repository, inputs=()):
    path, repository = Path(path).resolve(), Path(repository).resolve()
    require(path != repository and repository not in path.parents, 'Output must be outside the code checkout')
    for source in map(lambda p: Path(p).resolve(), inputs):
        require(path != source and source not in path.parents and path not in source.parents,
                'Output must be separate from each saved input')
    require(not path.exists(), 'Existing output must be preserved; no overwrite or automatic retry')
    return path


def freeze(study_dir, data_root, output_dir, repository_root):
    """Only this preparation boundary reads source evidence, into scorer-only tasks."""
    from pypdf import PdfReader
    study, data = Path(study_dir).resolve(), Path(data_root).resolve()
    output = new_output(output_dir, repository_root,
                        (study, data / 'raw/financebench/data', data / 'raw/financebench/pdfs'))
    for name, expected in SPEC['anchors'].items():
        require(file_identity(study / name) == expected, f'Pinned intake artifact changed: {name}')
    proposal = read_json(study / 'cohort-proposal.json')
    require(proposal['totals'] == SPEC['totals'], 'Proposed cohort totals changed')
    require(proposal['excluded_companies'] == SPEC['excluded_companies'], 'Company exclusions changed')
    source = data / 'raw/financebench/data'
    for name, expected in proposal['source_files'].items():
        require(file_identity(source / name) == expected, f'Dataset source changed: {name}')
    def release_rows(path):
        return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    raw_questions = release_rows(source / 'financebench_open_source.jsonl')
    by_id = {r['financebench_id']: r for r in raw_questions}
    require(len(by_id) == len(raw_questions), 'Duplicate source question IDs')
    queries = read_jsonl(study / 'retrieval-queries.jsonl')
    require(len(queries) == len({r['task_id'] for r in queries}) == SPEC['totals']['questions'], 'Question count changed')
    require(all(set(r) == {'task_id', 'doc_id', 'question'} for r in queries), 'Query allowlist violated')
    by_doc = {r['doc_id']: r for r in proposal['documents']}
    require(len(by_doc) == len(proposal['documents']) == SPEC['totals']['documents'], 'Duplicate/missing reports')
    companies = {r['company'] for r in by_doc.values()}
    require(len(companies) == SPEC['totals']['companies'] and not companies.intersection(SPEC['excluded_companies']),
            'Excluded or wrong company cohort')
    require({q['doc_id'] for q in queries} == set(by_doc), 'Question/report cohort mismatch')
    metadata = release_rows(source / 'financebench_document_information.jsonl')
    annual = {r['doc_name'] for r in metadata if r['company'] in companies
              and r['doc_type'].lower() in {'10k', '10k_annualreport'}}
    require({'financebench:' + r['financebench_id'] for r in raw_questions if r['doc_name'] in annual}
            == {q['task_id'] for q in queries}, 'Whole-company annual question coverage changed')
    documents, tasks, pdf_checks = [], [], []
    for d in proposal['documents']:
        require(Path(d['pdf_basename']).name == d['pdf_basename'] and '\\' not in d['pdf_basename'], 'Unsafe PDF basename')
        pdf = data / 'raw/financebench/pdfs' / d['pdf_basename']
        identity = file_identity(pdf)
        require(identity == d['pdf_identity'], f'PDF identity changed: {d["doc_id"]}')
        with pdf.open('rb') as handle:
            reader = PdfReader(handle, strict=False)
            if reader.is_encrypted:
                require(bool(reader.decrypt('')), 'Cannot decrypt source with empty password')
            require(len(reader.pages) == d['page_count'], 'Physical page count changed')
        require(file_identity(pdf) == identity, 'PDF changed during preflight')
        documents.append({'dataset': 'financebench', 'doc_id': d['doc_id'], 'pdf_path': str(pdf),
                          'source_path': str(pdf), 'source_format': 'pdf', 'split': SPEC['group'],
                          'page_count': d['page_count'], 'metadata': {'company': d['company'],
                          'doc_type': '10k', 'sha256': identity['sha256']}})
        pdf_checks.append({'doc_id': d['doc_id'], 'page_count': d['page_count'], **identity})
    for query in queries:
        require(query['task_id'].startswith('financebench:'), 'Invalid question namespace')
        raw = by_id[query['task_id'].removeprefix('financebench:')]
        d = by_doc[query['doc_id']]
        require(raw['doc_name'] == d['doc_name'] and raw['question'] == query['question'], 'Question projection changed')
        evidence = raw['evidence']
        require(isinstance(evidence, list) and evidence, f'Empty evidence: {query["task_id"]}')
        require(all(e.get('evidence_doc_name', e.get('doc_name', d['doc_name'])) == d['doc_name'] for e in evidence),
                f'Cross-report annotation requires review before execution: {query["task_id"]}')
        pages = [e['evidence_page_num'] for e in evidence]
        require(all(type(p) is int and 0 <= p < d['page_count'] for p in pages),
                f'Invalid zero-based evidence pages: {query["task_id"]}')
        tasks.append({**query, 'evidence_pages': sorted(set(pages))})
    require(sum(d['page_count'] for d in documents) == SPEC['totals']['pages'], 'Total pages changed')
    require(Counter(q['doc_id'] for q in queries) == Counter({k: d['question_count'] for k, d in by_doc.items()}),
            'Question allocation changed')
    for name, expected in proposal['source_files'].items():
        require(file_identity(source / name) == expected, 'Dataset changed during freeze')
    output.mkdir(parents=True)
    write_jsonl(output / 'documents.jsonl', documents)
    shutil.copyfile(study / 'retrieval-queries.jsonl', output / 'retrieval-queries.jsonl')
    write_jsonl(output / 'scorer-tasks.jsonl', tasks)
    for name in ('cohort-proposal.json', 'exploratory-design.json'):
        shutil.copyfile(study / name, output / name)
    manifest = {'schema_version': 1, 'status': 'frozen', 'experiment': SPEC['experiment'],
                'experimental_group': SPEC['group'], 'totals': SPEC['totals'], 'policy': study_policy(),
                'page_index_base': 0, 'pdf_checks': pdf_checks, 'code': code_provenance(Path(repository_root)),
                'frozen_utc': datetime.now(timezone.utc).isoformat(), 'artifacts': {
                    p.name: file_identity(p) for p in sorted(output.iterdir())}}
    write_json(output / 'cohort-freeze.json', manifest)
    return {'status': 'frozen', 'output_dir': str(output), 'totals': SPEC['totals']}


def read_freeze(freeze_dir, identities):
    root = Path(freeze_dir).resolve()
    def verify(path, expected=None):
        path = Path(path).resolve(); result = file_identity(path)
        require(expected is None or result == expected, f'Input artifact checksum changed: {path}')
        identities[path] = result
        return result
    verify(root / 'cohort-freeze.json')
    frozen = read_json(root / 'cohort-freeze.json')
    require(frozen['status'] == 'frozen' and frozen['experiment'] == SPEC['experiment']
            and frozen['totals'] == SPEC['totals'] and frozen['policy'] == study_policy()
            and frozen['experimental_group'] == SPEC['group'], 'Wrong larger-study frozen contract')
    require(set(frozen['artifacts']) == {'documents.jsonl', 'retrieval-queries.jsonl', 'scorer-tasks.jsonl',
                                       'cohort-proposal.json', 'exploratory-design.json'}, 'Frozen artifact inventory changed')
    for name, expected in frozen['artifacts'].items():
        verify(inside(root, name), expected)
    for name, expected in SPEC['anchors'].items():
        require(frozen['artifacts'][name] == expected, f'Wrong fixed intake identity: {name}')
    proposal = read_json(root / 'cohort-proposal.json')
    require(proposal['totals'] == SPEC['totals'], 'Proposal totals changed')
    documents = read_jsonl(root / 'documents.jsonl')
    require(len(documents) == SPEC['totals']['documents'] and len({d['doc_id'] for d in documents}) == len(documents), 'Document coverage changed')
    expected = {d['doc_id']: (d['page_count'], d['pdf_identity']['sha256'], d['company']) for d in proposal['documents']}
    require({d['doc_id']: (d['page_count'], d['metadata']['sha256'], d['metadata']['company']) for d in documents} == expected,
            'Frozen documents differ from proposal')
    return frozen, documents, verify


def load_sources(freeze_dir, native_dir, ocr_dir, identities):
    frozen, documents, verify = read_freeze(freeze_dir, identities)
    fr, nr, ore = map(lambda p: Path(p).resolve(), (freeze_dir, native_dir, ocr_dir))
    native_id, ocr_id = verify(nr / 'run_manifest.json'), verify(ore / 'run_manifest.json')
    native, ocr = read_json(nr / 'run_manifest.json'), read_json(ore / 'run_manifest.json')
    require(native['status'] == 'complete' and native['condition'] == 'N_native_text_bm25'
            and native['manifest_totals'] == totals() and native['experimental_group'] == SPEC['group'], 'Wrong/incomplete larger native run')
    config = native['configuration']
    require(config['skip_evaluation'] is True and config['tokenizer_version'] == TOKENIZER_VERSION
            and config['token_pattern'] == TOKEN_PATTERN and config['full_ranking'] is True
            and config['k1'] == 1.2 and config['b'] == .75 and config['ks'] == [1, 3, 5]
            and config['query_fields'] == ['task_id', 'doc_id', 'question'], 'Native extraction/control settings changed')
    require(native['inputs']['documents']['sha256'] == frozen['artifacts']['documents.jsonl']['sha256']
            and native['inputs']['tasks']['sha256'] == frozen['artifacts']['retrieval-queries.jsonl']['sha256'],
            'Native run must use frozen documents and label-free queries')
    for name, expected in native['artifacts'].items(): verify(inside(nr, name), expected)
    require(ocr['status'] == 'complete' and ocr['mode'] == 'full' and ocr['full_ocr_coverage'] is True
            and ocr['cohort_totals'] == {k: totals()[k] for k in ('documents', 'pages')}, 'Incomplete larger OCR cache')
    for name, expected in ocr.get('artifacts', {}).items(): verify(inside(ore, name), expected)
    configuration, pins = device_condition(SPEC.get('ocr_device', 'gpu:0'))
    require(ocr['contract']['configuration'] == configuration and ocr['contract']['package_pins'] == pins
            and ocr['contract']['model_manifest']['sha256'] == SPEC['ocr_model_manifest_sha256'], 'OCR condition/model changed')
    render, plans, render_ids = full_render(ore / 'source-render', verify_images=False)
    for name, expected in render_ids.items(): require(ocr['contract'][name] == expected, 'OCR/render identity changed')
    verify(ore / 'source-render/run_manifest.json', render_ids['render_manifest'])
    verify(ore / 'source-render/render_pages.jsonl', render_ids['render_pages'])
    require(ocr['contract']['render_contract'] == render['contract'], 'OCR/render contract differs')
    require(render['contract']['inputs']['native_manifest'] == native_id
            and render['contract']['inputs']['document_manifest'] == frozen['artifacts']['documents.jsonl'],
            'Render/native/frozen document lineage differs')
    expected_docs = [(d['doc_id'], d['page_count'], d['metadata']['sha256']) for d in documents]
    require([(d['doc_id'], d['page_count'], d['pdf_sha256']) for d in render['contract']['documents']] == expected_docs,
            'Rendered PDF identity/order changed')
    summary = read_json(nr / 'extraction_summary.json')
    docs = {d['doc_id']: d for d in summary['documents']}
    require(len(docs) == len(documents) and {k: (d['expected_page_count'], d['expected_sha256']) for k,d in docs.items()}
            == {d['doc_id']: (d['page_count'], d['metadata']['sha256']) for d in documents}, 'Native PDF identity differs')
    native_pages = read_jsonl(nr / 'native_pages.jsonl')
    require([(r['doc_id'], r['page_index']) for r in native_pages]
            == [(d['doc_id'], p) for d in documents for p in range(d['page_count'])], 'Native order/coverage differs')
    for doc_id, grouped in groupby(native_pages, lambda r: r['doc_id']): _validate_pages(list(grouped), docs[doc_id], native)
    ocr_pages = read_jsonl(ore / 'ocr_pages.jsonl')
    require([(r['doc_id'], r['page_index']) for r in ocr_pages] == [(r['doc_id'], r['page_index']) for r in plans], 'OCR coverage/order changed')
    for row, plan in zip(ocr_pages, plans):
        validate_text_record(row)
        require(row['status'] in {'ok', 'blank_ocr_text'} and row['page_index_base'] == 0, 'Unfinished OCR page')
        path = inside(ore, row['record_path']); verify(path, row['record_identity'])
        require(validate_commit(ore, path, plan, ocr['contract'], ocr['run_id']) == row, 'OCR raw/commit/aggregate differs')
        for name, expected in row['attempt_artifacts'].items(): verify(path.parent / name, expected)
    require(coverage(ocr_pages) == ocr['coverage'], 'OCR coverage declaration differs')
    queries = read_jsonl(fr / 'retrieval-queries.jsonl')
    require(queries == read_jsonl(nr / 'retrieval_queries.jsonl')
            and all(set(q) == {'task_id', 'doc_id', 'question'} for q in queries), 'Question allowlist/identity changed')
    expanded, audit = [], []
    for q in queries:
        e, a = expand_query(RetrievalQuery.from_record(q)); expanded.append(e); audit.append(a)
    return {'frozen': frozen, 'documents': documents, 'native': native, 'ocr': ocr, 'render': render,
            'docs': docs, 'summary': summary, 'pages': {'native': native_pages, 'ocr': ocr_pages},
            'queries': queries, 'expanded': expanded, 'audit': audit, 'verify': verify,
            'input_ids': {'freeze_manifest': identities[fr / 'cohort-freeze.json'],
                          'native_manifest': native_id, 'ocr_manifest': ocr_id,
                          'tasks': frozen['artifacts']['scorer-tasks.jsonl']}}


def bind_controls(freeze_dir, native_dir, ocr_dir, output_dir, repository_root):
    output = new_output(output_dir, repository_root, (freeze_dir, native_dir, ocr_dir))
    identities = {}; data = load_sources(freeze_dir, native_dir, ocr_dir, identities)
    output.mkdir(parents=True)
    manifest = {'status': 'running', 'stage': 'bm25_controls', 'experiment': SPEC['experiment'],
                'run_id': uuid.uuid4().hex, 'manifest_totals': totals(), 'inputs': data['input_ids'],
                'configuration': {'k1': 1.2, 'b': .75, 'ks': [1,3,5], 'expansion_policy': expansion_policy()},
                'policy': study_policy(), 'labels_parsed': False, 'artifacts': {}}
    write_json(output / 'run_manifest.json', manifest)
    try:
        for c in ('native', 'ocr'):
            predictions = {}
            for doc_id, grouped in groupby(data['pages'][c], lambda r: r['doc_id']):
                pages = list(grouped)
                index = BM25Index(doc_id, [(r['page_index'], r['search_text']) for r in pages], k1=1.2, b=.75, tokenizer=tokenize_without_stopwords)
                for query in data['expanded']:
                    if query.doc_id != doc_id: continue
                    ranking = index.rank(query)
                    predictions[query.task_id] = {'schema_version': 1, 'run_id': manifest['run_id'],
                        'condition': c + '_expansion_v1', 'task_id': query.task_id, 'doc_id': doc_id,
                        'page_count': len(pages), 'page_index_base': 0, 'status': 'ok', 'error': None,
                        'no_match': ranking[0]['score'] == 0,
                        'positive_score_page_count': sum(r['score'] > 0 for r in ranking), 'ranked_pages': ranking}
            require(set(predictions) == {q.task_id for q in data['expanded']}, 'Control question coverage differs')
            write_jsonl(output / f'{c}_predictions.jsonl', [predictions[q.task_id] for q in data['expanded']])
        write_jsonl(output / 'retrieval_queries.jsonl', data['queries'])
        write_jsonl(output / 'expanded_retrieval_queries.jsonl', [q.to_dict() for q in data['expanded']])
        write_jsonl(output / 'query_expansion_audit.jsonl', data['audit'])
        for path, expected in identities.items(): require(file_identity(path) == expected, 'Control input changed')
        manifest.update(status='controls_prepared_no_encoder_no_labels', stage='finished')
    except BaseException as exc:
        manifest.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        manifest['artifacts'] = {p.name: file_identity(p) for p in output.iterdir() if p.name != 'run_manifest.json'}
        write_json(output / 'run_manifest.json', manifest)
    return {'status': manifest['status'], 'output_dir': str(output), 'manifest_totals': totals()}


def load_inputs(freeze_dir, native_dir, reference_dir, ocr_dir, tasks_path, identities):
    data = load_sources(freeze_dir, native_dir, ocr_dir, identities)
    reference_root, tasks = Path(reference_dir).resolve(), Path(tasks_path).resolve()
    verify = data['verify']; verify(reference_root / 'run_manifest.json')
    reference = read_json(reference_root / 'run_manifest.json')
    require(reference['status'] == 'controls_prepared_no_encoder_no_labels' and reference['experiment'] == SPEC['experiment']
            and reference['inputs'] == data['input_ids'] and reference['manifest_totals'] == totals()
            and reference['policy'] == study_policy() and reference['labels_parsed'] is False, 'Wrong larger control lineage')
    require(reference['configuration'] == {'k1':1.2, 'b':.75, 'ks':[1,3,5], 'expansion_policy': expansion_policy()}, 'Lexical policy changed')
    for name, expected in reference['artifacts'].items(): verify(inside(reference_root, name), expected)
    require(verify(tasks) == data['frozen']['artifacts']['scorer-tasks.jsonl'], 'Scorer task bytes changed')
    for name, expected in [('retrieval_queries.jsonl', data['queries']),
                           ('expanded_retrieval_queries.jsonl', [q.to_dict() for q in data['expanded']]),
                           ('query_expansion_audit.jsonl', data['audit'])]:
        require(read_jsonl(reference_root / name) == expected, 'Saved expansion/query audit differs')
    ids = {q.task_id for q in data['expanded']}
    data['controls'] = {c: _by_task(read_jsonl(reference_root / f'{c}_predictions.jsonl'), ids) for c in ('native','ocr')}
    data['reference'] = {**reference,
        'prior_native_extraction_seconds': data['native']['stages']['extraction']['elapsed_seconds'],
        'prior_ocr_ingestion_timing': data['ocr']['timing'],
        'prior_rendering_timing': {'last_invocation_seconds': data['render']['elapsed_seconds'], 'attempts': data['render']['attempts']}}
    return data
