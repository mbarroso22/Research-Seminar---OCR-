"""Explicit stages for the separately frozen larger exploratory retrieval study."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import struct
import sys


def runtime_check(args):
    from finocr.io import read_json, write_json
    from finocr.pipelines.ocr_data import require
    from finocr.pipelines.ocr_smoke import verified_models
    from finocr.pipelines.report_rendering import file_identity, renderer_identity
    from finocr.pipelines.larger_spec import SPEC
    output = Path(args.output)
    require(not output.exists(), 'Runtime record exists; preserve it')
    result = {'status':'failed', 'interpretation':'setup only; no OCR/encoder/LLM inference'}
    try:
        require(sys.platform == 'win32' and sys.version_info[:3] == (3,12,10)
                and struct.calcsize('P') == 8, 'Require existing Windows Python 3.12.10 x64 GPU environment')
        import finocr
        require(Path(finocr.__file__).resolve().parents[2] == Path(args.repository_root).resolve(), 'Wrong editable checkout')
        require(file_identity(args.lock)['sha256'] == SPEC['gpu_lock_sha256'], 'GPU lock changed')
        pins = {}
        for line in Path(args.lock).read_text().splitlines():
            if not line.strip() or line.startswith('#'): continue
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s]+)\s+--hash=sha256:[0-9a-f]{64}', line)
            require(match is not None, 'Malformed preserved GPU lock')
            name = re.sub(r'[-_.]+','-',match[1]).lower()
            require(name not in pins, 'Duplicate GPU package pin')
            pins[name] = match[2]
        actual = {re.sub(r'[-_.]+','-',d.metadata['Name']).lower():d.version for d in importlib.metadata.distributions()}
        differences = {k:{'expected':v,'actual':actual.get(k)} for k,v in pins.items() if actual.get(k) != v}
        unexpected = {k:v for k,v in actual.items() if k not in pins and k != 'financial-ocr-research'}
        result.update(packages=actual, package_differences=differences, unexpected_packages=unexpected)
        require(not differences and not unexpected and 'paddlepaddle' not in actual, 'GPU package closure changed; no automatic installation')
        require(file_identity(args.reference)['sha256'] == 'c79e71c736ca6fe1f33d3fc7cdae039f212d01a094a209c3cd9eb17324afcf0d', 'Original GPU provenance reference changed')
        reference = read_json(args.reference)
        renderer = renderer_identity(args.renderer)
        old = reference['contract']['render_contract']['renderer']
        require(all(renderer[k] == old[k] for k in ('version_output','binary_identities')), 'Pinned renderer/DLL identities changed')
        _, model_id = verified_models(args.models_dir)
        require(model_id['sha256'] == SPEC['ocr_model_manifest_sha256'], 'OCR assets changed')
        import paddle
        require(paddle.is_compiled_with_cuda() and paddle.version.cuda() == '11.8', 'Require existing CUDA 11.8 build')
        paddle.set_device('gpu:0')
        paddle.utils.run_check()
        paddle.device.synchronize('gpu:0')
        result.update(status='setup_complete', device=paddle.device.get_device(), cuda=paddle.version.cuda(),
                      renderer=renderer, model_manifest=model_id, python=sys.version, executable=sys.executable)
    except BaseException as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        write_json(output, result)
    return result


def validate(args):
    import math
    import numpy as np
    from finocr.io import read_json, read_jsonl
    from finocr.pipelines.ocr_data import require, inside
    from finocr.pipelines.report_rendering import file_identity
    from finocr.pipelines.larger_cohort import read_freeze, study_policy, totals
    from finocr.pipelines.larger_hybrid import uncertainty_summary, company_summary
    from finocr.pipelines.native_baseline import load_evidence_labels
    from finocr.retrieval.semantic import semantic_rank, reciprocal_rank_fusion
    from finocr.evaluation.retrieval import evaluate_retrieval
    root = Path(args.output_dir).resolve()
    frozen, documents, _ = read_freeze(args.freeze_dir, {})
    manifest = read_json(root / 'run_manifest.json')
    require(manifest['status'] == 'complete' and manifest['stage'] == 'finished'
            and manifest['manifest_totals'] == totals() and manifest['policy'] == study_policy()
            and manifest['promotion_gate'] is None
            and manifest['expansion_control_reproduced'] == {'native':True,'ocr':True}, 'Incomplete or wrong larger run')
    for name, identity in manifest['artifacts'].items():
        require(file_identity(inside(root,name)) == identity, 'Run artifact checksum changed: ' + name)
    preservation = read_json(root / 'input_preservation.json')
    require(preservation['all_match'], 'Input preservation failed')
    for row in preservation['files']:
        require(file_identity(row['path']) == {k:row[k] for k in ('sha256','size_bytes')}, 'Preserved input changed since run')
    scorer = Path(args.freeze_dir) / 'scorer-tasks.jsonl'
    require(file_identity(scorer) == frozen['artifacts'][scorer.name], 'Scorer bytes changed')
    labels = load_evidence_labels(scorer)
    metrics = read_json(root / 'comparison_metrics.json')
    queries = read_jsonl(root / 'encoder_queries.jsonl')
    vectors = np.load(root / 'query_vectors.npy', allow_pickle=False)
    require(vectors.shape == (totals()['questions'],384) and np.isfinite(vectors).all(), 'Query vector coverage changed')
    require(len(queries)==len({q['task_id'] for q in queries})==totals()['questions'], 'Encoder query coverage changed')
    qv = {q['task_id']:v for q,v in zip(queries,vectors)}
    costs = read_json(root / 'cost_summary.json')
    for c in ('native','ocr'):
        sets = {}
        for method in ('bm25','semantic','hybrid'):
            rows = read_jsonl(root / f'{c}_{method}_predictions.jsonl')
            require(evaluate_retrieval(rows,labels,ks=(1,3,5)) == metrics[c][method], 'Saved metrics do not rescore')
            require(all(r['run_id']==manifest['run_id'] and r['condition']==c+'_'+method for r in rows), 'Prediction run identity differs')
            sets[method] = {r['task_id']:r for r in rows}
        cache = {}
        for report in costs[c]['reports']:
            p = inside(root,report['vector_path'])
            v=np.load(p,allow_pickle=False);w=read_jsonl(p.with_name(p.stem+'_windows.jsonl'))
            require(v.shape==(len(w),384) and np.isfinite(v).all(), 'Source vector coverage changed')
            cache[report['doc_id']] = (v,w)
        for tid, row in sets['semantic'].items():
            v,w=cache[row['doc_id']]
            replay=semantic_rank(qv[tid],v,w,row['page_count'])
            require([p['page_index'] for p in replay]==[p['page_index'] for p in row['ranked_pages']], 'Semantic vector replay order differs')
            require(all(math.isclose(a['score'],b['score'],abs_tol=2e-7)
                        and a['empty']==b['empty'] and a['best_window_index']==b['best_window_index']
                        for a,b in zip(replay,row['ranked_pages'])), 'Semantic scores/window replay differs')
            require(reciprocal_rank_fusion(sets['bm25'][tid]['ranked_pages'],row['ranked_pages'])
                    == sets['hybrid'][tid]['ranked_pages'], 'RRF replay differs')
    require(metrics['uncertainty']==uncertainty_summary(metrics,documents)
            and metrics['company_weighted']==company_summary(metrics,documents), 'Cluster uncertainty/sensitivity replay differs')
    return {'status':'completion_checks_pass', 'logical_full_rankings':totals()['questions']*6, 'promotion_gate':None,
            'primary':metrics['uncertainty']['native_vs_ocr']['bm25']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    f=sub.add_parser('freeze')
    for key in ('study-dir','data-root','output-dir','repository-root'):f.add_argument('--'+key,required=True)
    rt=sub.add_parser('check-runtime')
    for key in ('lock','reference','renderer','models-dir','output','repository-root'):rt.add_argument('--'+key,required=True)
    for command in ('controls','compare'):
        p=sub.add_parser(command)
        for key in ('freeze-dir','native-dir','ocr-dir','output-dir','repository-root'):p.add_argument('--'+key,required=True)
        if command=='compare':
            for key in ('reference-dir','models-dir'):p.add_argument('--'+key,required=True)
            p.add_argument('--check-only',action='store_true')
    v=sub.add_parser('validate')
    for key in ('freeze-dir','output-dir'):v.add_argument('--'+key,required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='freeze':
            from finocr.pipelines.larger_cohort import freeze
            result=freeze(args.study_dir,args.data_root,args.output_dir,args.repository_root)
        elif args.command=='check-runtime':result=runtime_check(args)
        elif args.command=='controls':
            from finocr.pipelines.larger_cohort import bind_controls
            result=bind_controls(args.freeze_dir,args.native_dir,args.ocr_dir,args.output_dir,args.repository_root)
        elif args.command=='compare':
            from finocr.pipelines.larger_hybrid import compare_larger
            result=compare_larger(args.freeze_dir,args.native_dir,args.reference_dir,args.ocr_dir,
                Path(args.freeze_dir)/'scorer-tasks.jsonl',args.models_dir,args.output_dir,
                repository_root=args.repository_root,check_only=args.check_only,
                progress=lambda message:print(message,flush=True))
        else:result=validate(args)
        print(json.dumps(result,indent=2));return 0
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
