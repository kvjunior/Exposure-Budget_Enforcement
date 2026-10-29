"""
RETIRED controller (review Sec 8). EARP is not a proposed method.

Proof it was provably greedy: for any pending request, DEFER is feasible at immediate cost M, and
ROLL costs M + R with R > 0, so ROLL never minimizes immediate cost; its tie-break is unreachable.
Removing ROLL leaves ADMIT/DEFER/REJECT, on which EARP and greedy use identical feasibility checks
and the same preference (ADMIT over DEFER over REJECT at equal cost). Hence EARP == greedy under
positive rollover cost. With no request, neither enumerates a rollover. The EARP tie-break can never
take effect. See docs/controller_findings.md.

No controller is proposed in slice 2.1. This module is kept only to preserve the negative result and
to prevent accidental re-use.
"""
def earp_controller(*args, **kwargs):
    raise NotImplementedError(
        "EARP is retired: provably equal to greedy under positive rollover cost. "
        "See docs/controller_findings.md. No controller is proposed in slice 2.1.")
