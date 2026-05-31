import subprocess
import os
import json
import re
from datetime import datetime

FIRMWARE_DIR = "/tmp/firmware"
os.makedirs(FIRMWARE_DIR, exist_ok=True)

MAKEFILE_PATH = "/app/Makefile"


def build_firmware(build_request: dict) -> dict:
    """
    Simulate calling 'make manifest' for an image build request.

    The package list is validated before it is passed to the build process so
    the manifest job receives only package identifiers.
    """
    packages = build_request.get("packages", [])
    profile = build_request.get("profile", "generic")
    target = build_request.get("target", "x86/64")
    version = build_request.get("version", "23.05.0")

    # Strict allowlist validation for all make variable values: only safe
    # identifier-style characters are permitted so the Makefile cannot
    # interpret these as shell or make expansions.
    if not re.fullmatch(r"[A-Za-z0-9_.+/-]{1,64}", str(profile)):
        raise ValueError("Invalid profile")
    if not re.fullmatch(r"[A-Za-z0-9_./-]{1,64}", str(target)):
        raise ValueError("Invalid target")
    if not re.fullmatch(r"[A-Za-z0-9_.+-]{1,32}", str(version)):
        raise ValueError("Invalid version")
    for pkg in packages:
        if not re.fullmatch(r"[A-Za-z0-9_.+-]{1,80}", str(pkg)):
            raise ValueError("Invalid package name")

    packages_str = " ".join(packages)

    try:
        result = subprocess.run(
            [
                "make", "-f", MAKEFILE_PATH, "manifest",
                f"PROFILE={profile}",
                f"PACKAGES={packages_str}",
                f"TARGET={target}",
                f"VERSION={version}",
            ],
            shell=False,
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/tmp"
        )

        return {
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:500],
            "returncode": result.returncode,
            "packages_requested": packages,
            "profile": profile,
            "target": target,
            "version": version,
            "timestamp": datetime.now().isoformat(),
        }
    except subprocess.TimeoutExpired:
        return {
            "error": "build process timed out",
            "packages_requested": packages,
        }
    except Exception as e:
        return {
            "error": str(e),
            "packages_requested": packages,
        }


def fetch_cached_build(db_path: str, cache_key: str):
    """
    Retrieve a cached build result from the database by cache_key.

    Note: cache_key is a truncated 12-character SHA-256 hash derived from
    the build request fields. Due to the truncated nature, two different
    build requests may theoretically hash to the same value, causing the
    cache lookup to retrieve a cached result from a different request with
    colliding hash.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, cache_key, result, timestamp FROM builds WHERE cache_key = ? LIMIT 1", (cache_key,))
    row = c.fetchone()
    conn.close()

    return row
