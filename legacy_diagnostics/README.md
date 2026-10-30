# Legacy diagnostics (historical evidence; not the new service)

Preserved from the prior round: the ADS-PRE self-contained diagnostic (adspre_diag.py) and the
Umbral scope-exposure diagnostic (scope_exposure.py) plus harness.py. Runs in the legacy venv
(cryptography 3.4.8 + umbral 0.3.0). These are kept UNCHANGED as evidence. The new codebase does
NOT inherit their two interpretation issues:
  - EX-4 was counted as a passing executable check though it is an assumption -> in the new
    codebase the equivalent (ADV-4) is printed as [assumption] and excluded from pass counts.
  - the cross-scope claim omitted excluding authorized cfrag decryption -> new ADV-R3b states it.
