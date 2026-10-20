"""Read-only qualification approval verification. No issuer, seal or allowance API.

The fixed, operator-controlled approval file is the trust input. Hash checking
establishes binding/integrity; it cannot independently establish human consent.
Neither this module nor the CLI creates that file or an authorization record.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from finocr_answer.contract import digest, strict_json
from finocr_answer.pause import require_inference_authorized
from .evidence import CASES
from .preparation import CAMPAIGN, VERSION, frozen_reference, implementation
from .probe import sha_lf

AUTHORIZATION_VERSION = 'qualification-authorization-binding-v1'
LIMITS = {'campaigns': 1, 'maximum_completion_attempts': 6, 'retries': 0,
          'resume': False, 'case_order': list(CASES), 'output_tokens_per_attempt': 1024,
          'request_deadline_seconds': 180, 'financebench_requests': 0}


class AuthorizationRejected(ValueError):
    """No claim/submission is permitted on this invocation."""


def approval_paths() -> tuple[Path, Path]:
    """Fixed external trust location; no CLI/environment/path override or mkdir."""
    directory = (Path.home()/'financial-ocr-data'/'answer-generation'/
                 'qwen3-4b-instruct-2507-v1'/'authorizations')
    return (directory/(CAMPAIGN+'.approval.json'),
            directory/(CAMPAIGN+'.authorization.json'))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _time(value) -> datetime:
    if not isinstance(value, str) or not value.endswith('Z'):
        raise AuthorizationRejected('Require an explicit UTC timestamp ending in Z')
    try:
        return datetime.fromisoformat(value[:-1]+'+00:00')
    except ValueError as exc:
        raise AuthorizationRejected('Invalid authorization timestamp') from exc


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise AuthorizationRejected('Missing explicit approval reference/identity')


def _regular(path: Path) -> Path:
    path = path.absolute()
    for component in (path, *path.parents):
        if component.is_symlink() or getattr(component, 'is_junction', lambda: False)():
            raise AuthorizationRejected('Approval inputs cannot use links or junctions')
    if not path.is_file():
        raise AuthorizationRejected('Required existing approval input missing: '+str(path))
    return path.resolve(strict=True)


def _read(path: Path) -> tuple[bytes, dict]:
    raw = _regular(path).read_bytes()
    value = strict_json(raw.decode('utf-8-sig'))
    if not isinstance(value, dict):
        raise AuthorizationRejected('Approval inputs must contain JSON objects')
    return raw, value


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exact(value: dict, keys: set[str]):
    if set(value) != keys:
        raise AuthorizationRejected('Missing or additional approval fields')


def _bindings(preparation: Path, raw: bytes, report: dict, repository: Path, ref: dict) -> dict:
    build_raw, build = _read(Path(report['native_build']))
    return {'preparation_path': str(preparation.resolve(strict=True)),
            'preparation_file_sha256': _sha(raw), 'preparation_canonical_sha256': digest(report),
            'implementation_fingerprint': report['implementation']['fingerprint'],
            'implementation_record_sha256': digest(report['implementation']),
            'frozen_reference_lf_sha256': sha_lf(repository/'docs/QUALIFICATION_FROZEN_IDENTITIES.json'),
            'plan_lf_sha256': ref['plan_lf_sha256'], 'campaign_root': report['campaign_root'],
            'historical_v2_setup_sha256': ref['historical_v2_setup_sha256'],
            'runtime_sha256': digest(report['runtime']), 'execution_sha256': digest(ref['execution']),
            'contract_sha256': digest(ref['contract']), 'prompt_controls_sha256': digest(ref['prompts']),
            'model_sha256': ref['model']['sha256'], 'server_sha256': ref['server']['sha256'],
            'native_build_file_sha256': _sha(build_raw),
            'native_executable_sha256': build['executable_sha256'],
            'protected_inventory_sha256': digest(report['protected'])}


@dataclass(frozen=True)
class VerifiedAuthorization:
    preparation_path: Path
    approval_path: Path
    authorization_path: Path
    preparation_bytes: bytes
    approval_bytes: bytes
    authorization_bytes: bytes

    @property
    def report(self):
        return strict_json(self.preparation_bytes.decode('utf-8-sig'))

    @property
    def identity(self):
        record = strict_json(self.authorization_bytes.decode('utf-8-sig'))
        return {'authorization_id': record['authorization_id'],
                'approval_reference': record['approval_reference'],
                'authorization_file_sha256': _sha(self.authorization_bytes),
                'approval_file_sha256': _sha(self.approval_bytes),
                'preparation_file_sha256': _sha(self.preparation_bytes),
                'preparation_canonical_sha256': digest(self.report),
                'bindings': record['bindings'], 'limits': record['limits']}

    @property
    def protected(self):
        return {str(path): {'kind': 'file', 'sha256': _sha(raw)} for path, raw in (
            (self.preparation_path, self.preparation_bytes), (self.approval_path, self.approval_bytes),
            (self.authorization_path, self.authorization_bytes))}


def verify_authorization(preparation: Path, repository: Path,
                         authorization: Path | None) -> VerifiedAuthorization:
    # Preserve the real pause without reading any preparation/authorization on
    # absent authorization or absent operator approval. No directory is created.
    if authorization is None:
        require_inference_authorized()
    approved_path, record_path = approval_paths()
    if not approved_path.exists() and not approved_path.is_symlink():
        require_inference_authorized()
    try:
        if authorization.absolute() != record_path.absolute():
            raise AuthorizationRejected('Only the fixed reviewed authorization path is accepted')
        preparation, repository = preparation.absolute(), repository.resolve(strict=True)
        approval_raw, approval = _read(approved_path)
        record_raw, record = _read(record_path)
        preparation_raw, report = _read(preparation)
        _exact(approval, {'kind','version','approval_reference','authorization_path',
                         'authorization_file_sha256','approved_at_utc'})
        _exact(record, {'kind','version','authorization_id','approval_reference',
                       'issued_at_utc','expires_at_utc','explicit_human_authorization','bindings','limits'})
        if (approval['kind'] != 'qualification_operator_approval' or
            record['kind'] != 'qualification_explicit_authorization' or
            approval['version'] != AUTHORIZATION_VERSION or record['version'] != AUTHORIZATION_VERSION or
            record['explicit_human_authorization'] is not True):
            raise AuthorizationRejected('Require separately reviewed explicit qualification approval')
        for value in (record['authorization_id'], record['approval_reference'], approval['approval_reference']):
            _text(value)
        if (approval['approval_reference'] != record['approval_reference'] or
            approval['authorization_path'] != str(record_path.resolve(strict=True)) or
            approval['authorization_file_sha256'] != _sha(record_raw)):
            raise AuthorizationRejected('Operator approval does not pin this exact authorization record')
        issued, expires, approved = (_time(record['issued_at_utc']), _time(record['expires_at_utc']),
                                     _time(approval['approved_at_utc']))
        if not issued <= approved <= _now() < expires:
            raise AuthorizationRejected('Authorization is expired, future-dated or inconsistently dated')
        if digest(record['limits']) != digest(LIMITS):
            raise AuthorizationRejected('Campaign/order/attempt/decoder limits differ from the frozen plan')
        if (report['kind'] != 'qualification_offline_preparation_not_authorization' or
            report['version'] != VERSION or report['status'] != 'offline_ready_for_separate_review_not_authorization' or
            report['execution_enabled'] is not False or report['benchmark_generation_enabled'] is not False or
            any(type(report[k]) is not int or report[k] != 0 for k in (
                'inference_executed','additional_inference_authorized','remaining_authorized_requests')) or
            report['preservation_pass'] is not True or report['protected'] != report['preserved_after'] or
            report['historical'] != {'requests_spent':12,'remaining_authorized':0,'v2_mechanical_pass':'1/6'}):
            raise AuthorizationRejected('Require the final passing offline preparation, retaining historical spending')
        ref = frozen_reference(repository)
        if (report['frozen_reference'] != ref or report['runtime'] != ref['runtime'] or
            report['implementation'] != implementation(repository) or
            Path(report['repository']).resolve() != repository):
            raise AuthorizationRejected('Final implementation/Git/runtime/reference binding changed')
        closeout=report.get('preservation_closeout')
        if (not isinstance(closeout,dict) or closeout.get('tracked_files')!=184 or
            closeout.get('environment_inventories')!=3):
            raise AuthorizationRejected('Final preparation must bind the complete preservation closeout')
        root = approved_path.parent.parent/'followups'/CAMPAIGN
        if Path(report['campaign_root']).resolve() != root.resolve():
            raise AuthorizationRejected('Authorization cannot select an alternate campaign location')
        if root.exists() or root.is_symlink():
            raise AuthorizationRejected('Campaign anchor is already consumed; no retry, restart or resume')
        if record['bindings'] != _bindings(preparation,preparation_raw,report,repository,ref):
            raise AuthorizationRejected('Authorization does not bind this exact final preparation and implementation')
        return VerifiedAuthorization(_regular(preparation),_regular(approved_path),_regular(record_path),
                                     preparation_raw,approval_raw,record_raw)
    except AuthorizationRejected:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise AuthorizationRejected('Invalid or unavailable approval evidence: '+str(exc)) from exc


def revalidate_authorization(verified: VerifiedAuthorization, report: dict,
                             repository: Path) -> VerifiedAuthorization:
    if not isinstance(verified, VerifiedAuthorization):
        raise AuthorizationRejected('Require a verified binding; an arbitrary reference is insufficient')
    current = verify_authorization(verified.preparation_path,repository,verified.authorization_path)
    if current != verified or digest(report) != digest(current.report):
        raise AuthorizationRejected('Approval/preparation changed since verification')
    return current


def guard_authorization_window(verified: VerifiedAuthorization) -> None:
    """No new submission after expiry, including time spent in backend preflight."""
    record = strict_json(verified.authorization_bytes.decode('utf-8-sig'))
    if not _time(record['issued_at_utc']) <= _now() < _time(record['expires_at_utc']):
        raise AuthorizationRejected('Approval window closed; stop with unused cases forfeited')
