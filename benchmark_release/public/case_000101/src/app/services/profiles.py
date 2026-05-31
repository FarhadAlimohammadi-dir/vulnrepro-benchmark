# NOTE: profile data is currently hard-coded; future versions should fetch from
# the upstream OpenWrt target metadata API and cache locally for 1 hour.

PROFILE_REGISTRY = {
    "x86/64": {
        "23.05.0": ["generic", "generic-ext4-combined", "generic-squashfs-combined"],
        "23.05.2": ["generic", "generic-ext4-combined", "generic-squashfs-combined"],
        "22.03.5": ["generic"],
    },
    "ath79/generic": {
        "23.05.0": [
            "tplink_archer-c7-v2",
            "tplink_archer-c7-v5",
            "tplink_tl-wr841-v13",
            "ubnt_nanostation-m",
        ],
        "22.03.5": [
            "tplink_archer-c7-v2",
            "tplink_tl-wr841-v13",
        ],
    },
    "ipq40xx/generic": {
        "23.05.0": [
            "linksys_ea8300",
            "linksys_ea6350v3",
            "asus_map-ac2200",
        ],
    },
    "ramips/mt7621": {
        "23.05.0": [
            "xiaomi_mi-router-4a-gigabit",
            "netgear_r6220",
            "dlink_dir-878-a1",
        ],
    },
}

PROFILE_METADATA = {
    "generic": {"flash_mb": 0, "ram_mb": 0, "arch": "x86_64", "description": "Generic x86 image"},
    "tplink_archer-c7-v2": {"flash_mb": 16, "ram_mb": 128, "arch": "mips_24kc", "description": "TP-Link Archer C7 v2"},
    "tplink_archer-c7-v5": {"flash_mb": 16, "ram_mb": 128, "arch": "mips_24kc", "description": "TP-Link Archer C7 v5"},
    "linksys_ea8300": {"flash_mb": 256, "ram_mb": 256, "arch": "arm_cortex-a7", "description": "Linksys EA8300"},
    "xiaomi_mi-router-4a-gigabit": {"flash_mb": 16, "ram_mb": 128, "arch": "mips_24kc", "description": "Xiaomi Mi Router 4A Gigabit"},
}


def get_supported_profiles(target: str, version: str) -> list:
    """
    Return list of supported profile names for a target/version combination.
    Returns empty list if target or version is not registered.
    """
    target_map = PROFILE_REGISTRY.get(target, {})
    profiles = target_map.get(version, [])
    # TODO: i18n — add localized profile labels for zh-CN, de-DE markets
    return profiles


def get_profile_metadata(profile: str) -> dict:
    """
    Return hardware metadata for a named profile.
    Used by the UI to display flash/RAM constraints before requesting a build.
    """
    return PROFILE_METADATA.get(profile, {
        "flash_mb": None,
        "ram_mb": None,
        "arch": "unknown",
        "description": "Unknown profile",
    })