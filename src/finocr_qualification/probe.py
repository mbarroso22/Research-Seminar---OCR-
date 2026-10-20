"""Build/use a standalone converter with an already installed C++ compiler only."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
from finocr_answer.conformance import PINNED_COMMIT, compile_schema
from finocr_answer.setup import sha
from .evidence import write_json, write_bytes


def pinned_source(source: Path):
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all'], text=True)
    if commit != PINNED_COMMIT or dirty.strip():
        raise ValueError('Use the unchanged existing clean pinned b6500 source')


def build_probe(repository: Path, source: Path, output: Path, compiler: str) -> dict:
    repository, source, output = (p.resolve() for p in (repository, source, output))
    if any(output == p or p in output.parents or output in p.parents for p in [repository, source]):
        raise ValueError('Build output must be outside repository and pinned source')
    pinned_source(source)
    found = shutil.which(compiler)
    if not found or Path(found).stem.lower() not in {'clang++','g++','cl'}:
        raise ValueError('An existing clang++, g++ or cl compiler is required; do not install one implicitly')
    output.mkdir()
    executable = output / ('schema-probe.exe' if os.name == 'nt' else 'schema-probe')
    wrapper = repository / 'tools/qualification_schema_probe.cpp'
    includes = [source/'common', source/'vendor', source/'include', source/'ggml/include']
    cpp = source/'common/json-schema-to-grammar.cpp'
    if Path(found).stem.lower() == 'cl':
        command = [found, '/nologo','/std:c++17','/EHsc','/utf-8',*[f'/I{p}' for p in includes],
                   str(wrapper),str(cpp),f'/Fe:{executable}']
    else:
        command = [found,'-std=c++17','-O1',*[f'-I{p}' for p in includes],str(wrapper),str(cpp),'-o',str(executable)]
    with (output/'build.log').open('xb') as log:
        result = subprocess.run(command,cwd=output,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    if result.returncode:
        raise ValueError('Standalone converter build failed; preserve build.log')
    record = {'kind':'offline_converter_build_no_inference','commit':PINNED_COMMIT,
              'command':command,'compiler_sha256':sha(Path(found)),
              'wrapper_lf_sha256':sha_lf(wrapper),'cpp_lf_sha256':sha_lf(cpp),
              'executable':str(executable),'executable_sha256':sha(executable),
              'inference_executed':0,'additional_inference_authorized':0}
    write_json(output/'build.json',record)
    return record


def sha_lf(path):
    import hashlib
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def compare_native(repository: Path, source: Path, build: dict, schema: Path, expected: bytes) -> dict:
    pinned_source(source)
    executable = Path(build['executable'])
    if (build['commit'] != PINNED_COMMIT or sha(executable) != build['executable_sha256'] or
        sha_lf(repository/'tools/qualification_schema_probe.cpp') != build['wrapper_lf_sha256'] or
        sha_lf(source/'common/json-schema-to-grammar.cpp') != build['cpp_lf_sha256']):
        raise ValueError('Native converter/source/helper identity changed')
    result = subprocess.run([str(executable),str(schema)],capture_output=True,timeout=30)
    actual = result.stdout.replace(b'\r\n',b'\n')
    if result.returncode or result.stderr.strip() or actual != expected or compile_schema(source,schema) != expected:
        raise ValueError('Native/Python effective grammar conversion mismatch or warning')
    return {'native_matches':True,'python_matches':True,'native_build':build,
            'grammar_bytes':len(actual),'model_or_backend_initialized':False}
