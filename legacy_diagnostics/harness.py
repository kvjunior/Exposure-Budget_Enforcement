"""
Result harness for the diagnostic package.

Every check declares, before it runs:
  - an expected outcome (True or False; some correct outcomes are False),
  - a category saying what KIND of evidence it is,
  - what it establishes, and what it does NOT establish.

Categories
  OBSERVATION      Executable observation on the stated inputs. Shows behaviour on those
                   inputs only; never proves the absence of an attack.
  TYPE-CHECK       A typing argument about the published algorithm, confirmed by a typed
                   implementation rejecting the operation. The argument is the evidence;
                   the exception is only a confirmation.
  IDENTITY         Numerical confirmation of an algebraic identity on random instances.
                   The identity follows from the algebra; the run guards against
                   transcription errors only.
  LIMITATION-DEMO  A deliberately constructed counterexample showing what a check cannot
                   detect. NOT an attack on any published or proposed scheme.

Exit status: 0 if every observed outcome equals its expected outcome, 1 otherwise.
Results are written as JSON to results/<suite>.json.
"""
import json, os, platform, sys, datetime

CATEGORIES = {"OBSERVATION", "TYPE-CHECK", "IDENTITY", "LIMITATION-DEMO"}


class Suite:
    def __init__(self, name, description):
        self.name, self.description, self.results = name, description, []

    def check(self, cid, category, expected, observed, establishes, not_established, detail=None):
        assert category in CATEGORIES, category
        assert isinstance(expected, bool) and isinstance(observed, bool), cid
        self.results.append(dict(
            id=cid, category=category, expected=expected, observed=observed,
            match=(expected == observed), establishes=establishes,
            not_established=not_established, detail=detail or {}))

    def finish(self):
        os.makedirs("results", exist_ok=True)
        meta = dict(suite=self.name, description=self.description,
                    python=sys.version.split()[0], platform=platform.platform(),
                    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
        try:
            import importlib.metadata as md
            meta["packages"] = {p: md.version(p) for p in ("umbral", "cryptography")
                                if _installed(md, p)}
        except Exception:
            pass
        out = dict(meta=meta, results=self.results,
                   summary=dict(total=len(self.results),
                                unexpected=[r["id"] for r in self.results if not r["match"]]))
        path = os.path.join("results", f"{self.name}.json")
        with open(path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n==== {self.name}: {self.description} ====")
        for r in self.results:
            flag = "ok " if r["match"] else "UNEXPECTED"
            print(f"[{flag}] {r['id']:<8} {r['category']:<15} expected={r['expected']!s:<5} "
                  f"observed={r['observed']!s:<5}  {r['establishes']}")
        bad = out["summary"]["unexpected"]
        print(f"---- {len(self.results)} checks, {len(bad)} unexpected; results -> {path}")
        sys.exit(1 if bad else 0)


def _installed(md, p):
    try:
        md.version(p); return True
    except Exception:
        return False
