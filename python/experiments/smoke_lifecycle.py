"""
End-to-end smoke workload (brief sec 8 step 6). Runs in the PRODUCTION venv (real HPKE).

Covers in one deterministic run:
  - owner authorizes a stream and activates scope A;
  - a producer emits records with authenticated HPKE envelopes (key sealed to the owner);
  - a delegation request arrives while the owner is ONLINE -> fixed-epoch policy admits it,
    the conservative checker approves, and the owner REWRAPS each record's key envelope to
    the delegatee (payload ciphertext preserved); the delegatee opens the records;
  - a second request arrives while the owner is OFFLINE -> policy defers, checker confirms an
    offline controller cannot mint new grant authority;
  - an offline scope rollover is attempted WITHOUT preauth (rejected) and WITH preauth
    (allowed) -- demonstrating the authentic-preauthorization rule.

Outputs a structured JSON manifest (timings are MEASURED wall-clock for the crypto ops;
everything else is logged as structured observations). This is a SMOKE run: it is labelled
as such and is NOT a performance result.
"""
from __future__ import annotations
import json, os, sys, time, platform, hashlib, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_crypto import hybrid as C
from delegation_model.types import Grant, Scope, RecordRange, Record
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced,
                                      GrantIssued, OwnerAvailability)
from delegation_manager.manager import (project_observation, check_action, Action, ActionKind,
                                        PreAuth)
from delegation_manager.policies import fixed_epoch_policy, Request


def run():
    t0 = time.perf_counter()
    log = []
    def obs_log(**kw): log.append(kw)

    # keys: owner holds the "scope recipient" key for its own records (so it can rewrap);
    # producer signs; delegatee has its own key.
    owner_sk, owner_pk = C.gen_recipient_key()
    prod_sk, prod_pk = C.gen_signing_key()
    deleg_sk, deleg_pk = C.gen_recipient_key()
    deleg2_sk, deleg2_pk = C.gen_recipient_key()

    events = []
    events.append(StreamAuthorized(0, "O", "g", "D"))
    events.append(ScopeActivated(1, "O", Scope("g", 0), "g.e0.k0", 0))
    events.append(OwnerAvailability(2, "O", True))

    # produce 5 records, key sealed to the owner
    records = []
    produce_ms = []
    for seq in range(5):
        s = time.perf_counter()
        env = C.produce_record(prod_sk, "D", "g", seq, "g.e0.k0", owner_pk,
                               f"reading seq={seq}".encode())
        produce_ms.append((time.perf_counter() - s) * 1000)
        records.append(env)
        events.append(RecordProduced(3 + seq, Record("g", seq), 1.0))
    obs_log(step="produce", n=5, produce_ms_mean=statistics.mean(produce_ms))

    # delegation request #1 while owner ONLINE
    g1 = Grant("G1", "O", "R1", Scope("g", 0), RecordRange("g", 0, 5), 2, 3,
               ("p0", "p1", "p2"), valid_from=9, valid_to=None)
    obs = project_observation(events, cutoff=9)
    action = fixed_epoch_policy(obs, Request(9, g1))
    chk = check_action(action, obs, PreAuth())
    obs_log(step="request1", owner_online=obs.owner_online, action=action.kind.value,
            checker_ok=chk.ok, reason=chk.reason)
    assert action.kind == ActionKind.ADMIT_GRANT and chk.ok, "request1 should admit"
    events.append(GrantIssued(9, g1))

    # owner rewraps each record's key envelope to the delegatee; payload preserved
    rewrap_ms, open_ms = [], []
    for env in records:
        s = time.perf_counter()
        env2 = C.rewrap_edek(env, owner_sk, deleg_pk, "g.e0.k0")
        rewrap_ms.append((time.perf_counter() - s) * 1000)
        assert env2.ct == env.ct and env2.sig == env.sig, "payload/sig must be preserved"
        s = time.perf_counter()
        pt = C.open_record(env2, deleg_sk, prod_pk, "g.e0.k0")
        open_ms.append((time.perf_counter() - s) * 1000)
        assert pt.startswith(b"reading seq="), "delegatee must open"
    obs_log(step="rewrap_deliver", n=len(records),
            rewrap_ms_mean=statistics.mean(rewrap_ms), open_ms_mean=statistics.mean(open_ms),
            payload_bytes_reencrypted=0, note="only key envelope rewrapped; payload unchanged")

    # owner goes OFFLINE; request #2 must defer
    events.append(OwnerAvailability(20, "O", False))
    g2 = Grant("G2", "O", "R2", Scope("g", 0), RecordRange("g", 0, 5), 2, 3,
               ("p0", "p1", "p2"), valid_from=21, valid_to=None)
    obs = project_observation(events, cutoff=21)
    action = fixed_epoch_policy(obs, Request(21, g2))
    chk = check_action(action, obs, PreAuth())
    obs_log(step="request2_offline", owner_online=obs.owner_online, action=action.kind.value,
            checker_ok=chk.ok, reason=chk.reason)
    assert action.kind == ActionKind.DEFER, "request2 should defer while owner offline"

    # offline scope rollover: without preauth -> rejected; with preauth -> allowed
    # fresh rollover: new scope (g,1), new key id, start_seq past the already-produced records
    next_seq = obs.auth.produced.get("g", 0)
    roll = Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                  new_scope_key_id="g.e1.k0", start_seq=next_seq)
    chk_no = check_action(roll, obs, PreAuth())
    chk_yes = check_action(roll, obs, PreAuth({("O", "g", 1)}, verified=True))
    obs_log(step="offline_rollover", without_preauth_ok=chk_no.ok,
            with_preauth_ok=chk_yes.ok, reason_no=chk_no.reason, reason_yes=chk_yes.reason)
    assert not chk_no.ok and chk_yes.ok, "preauth rule must gate offline activation"

    manifest = {
        "run_kind": "smoke",
        "label": "NOT a performance result (single-process container; no device-performance claim)",
        "env": {"python": sys.version.split()[0], "platform": platform.platform(),
                "machine": platform.machine(), "logical_cpus_reported": os.cpu_count(),
                "cryptography": _ver("cryptography"), "hpke": _ver("hpke")},
        "suite": C.SUITE,
        "wall_time_s": round(time.perf_counter() - t0, 4),
        "observations": log,
        "measured_ops_ms": {
            "produce_mean": round(statistics.mean(produce_ms), 4),
            "rewrap_mean": round(statistics.mean(rewrap_ms), 4),
            "open_mean": round(statistics.mean(open_ms), 4),
        },
    }
    return manifest


def _ver(pkg):
    import importlib.metadata as md
    try: return md.version(pkg)
    except Exception: return None


if __name__ == "__main__":
    out = run()
    os.makedirs("results/manifests", exist_ok=True)
    path = "results/manifests/smoke_lifecycle.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    print(f"\n[smoke] wrote {path}  (labelled: not a performance result)")
