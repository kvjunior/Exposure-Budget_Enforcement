#!/usr/bin/env bash
# Run both diagnostic suites. Exit nonzero if ANY suite reports an unexpected outcome.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"
rc=0
echo "## adspre_diag (pure Python, no third-party deps) ##"
python3 adspre_diag.py || rc=1
echo
echo "## scope_exposure (needs umbral==0.3.0, cryptography==3.4.8) ##"
python3 scope_exposure.py || rc=1
echo
echo "Aggregate exit status: $rc  (0 = all outcomes as expected)"
exit $rc
