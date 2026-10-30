import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_crypto import hybrid as C
from delegation_model.loader import load_event
FAIL=[]
def expect(cid,cond,msg):
    ok=bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<16} {msg}");
    if not ok: FAIL.append(cid)
# 1. tampered ciphertext -> open must raise
psk,ppk=C.gen_signing_key(); rsk,rpk=C.gen_recipient_key()
env=C.produce_record(psk,"D","g",0,"g.e0.k0",rpk,b"x")
bad=C.Envelope(env.hdr, env.ct+b"\x00", env.edek, env.enc, env.sig, env.recipient_fp)
raised=False
try: C.open_record(bad,rsk,ppk,"g.e0.k0")
except Exception: raised=True
expect("tamper_raises", raised, "tampered ciphertext is rejected")
# 2. malformed event dict -> loader must raise
raised=False
try: load_event({"type":"NoSuchEvent","t":0})
except ValueError: raised=True
expect("bad_event_raises", raised, "unknown event type is rejected")
# 3. wrong recipient key -> open must raise
rsk2,_=C.gen_recipient_key(); raised=False
try: C.open_record(env, rsk2, ppk, "g.e0.k0")
except Exception: raised=True
expect("wrong_recipient_raises", raised, "wrong recipient key cannot open")
print(f"\n{len(FAIL)} failures"); sys.exit(1 if FAIL else 0)
