"""The two completed campaigns exhausted the authorized twelve requests."""


class InferencePausedError(ValueError):
    pass


def require_inference_authorized() -> None:
    """No flag, environment override, budget ticket or opt-in in this revision."""
    raise InferencePausedError(
        'Inference is paused; the 12-request allowance is exhausted. '
        'Preserve the v1 and v2 runs/ledgers. This revision permits offline checks only; '
        'no new setup seal, follow-up ticket or generation is authorized.'
    )
