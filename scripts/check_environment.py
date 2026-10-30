"""Capture and print the actual execution environment. Does not claim constrained hardware."""
import json, platform, sys, os


def env():
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
    }
    for pkg in ("cryptography", "hpke", "umbral"):
        try:
            import importlib.metadata as md
            info[pkg] = md.version(pkg)
        except Exception:
            info[pkg] = None
    # memory, best-effort
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    info["mem_total"] = line.split()[1] + " kB"; break
    except Exception:
        pass
    info["note"] = ("General-purpose container. Any timing is wall-clock on this host; "
                    "NOT physical sensor / constrained-device performance.")
    return info


if __name__ == "__main__":
    print(json.dumps(env(), indent=2))
