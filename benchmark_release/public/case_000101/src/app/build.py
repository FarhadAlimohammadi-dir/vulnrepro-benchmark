import subprocess
import os
import json
from datetime import datetime

FIRMWARE_DIR = "/tmp/firmware"
os.makedirs(FIRMWARE_DIR, exist_ok=True)

MAKEFILE_PATH = "/app/Makefile"


def build_firmware(build_request: dict) -> dict:
    """
    Simulate calling 'make manifest' with user-supplied PACKAGES.

    This function invokes the Makefile manifest target, which is how
    OpenWrt ASU builds firmware images. The PACKAGES variable is user-controlled
    and passed directly to make for expansion in the build environment.

    The PACKAGES variable is joined from user input and expanded by the make
    process. The Makefile expands $(PACKAGES) as part of the build target
    execution, allowing shell metacharacter evaluation such as backticks and
    variable expansion within the make recipe context.

    Reference: OpenWrt ASU asu/build.py line 217-226
    """
    packages = build_request.get("packages", [])
    profile = build_request.get("profile", "generic")
    target = build_request.get("target", "x86/64")
    version = build_request.get("version", "23.05.0")

    # TODO: validate profile against target-specific profiles
    # TODO: check package availability in version repositories

    # packages are joined and passed directly to make for environment expansion
    # The build process expands package list variables in the manifest recipe
    packages_str = " ".join(packages)

    # Invoke make manifest PROFILE=<p> PACKAGES=<pkgs>
    # The Makefile expands $(PACKAGES) inside the manifest target during execution
    cmd = f"make -f {MAKEFILE_PATH} manifest PROFILE='{profile}' PACKAGES='{packages_str}' TARGET='{target}' VERSION='{version}'"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
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