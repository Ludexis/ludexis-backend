from dataclasses import dataclass, field
import re


KNOWN_RELEASE_GROUPS = {
    "RUNE",
    "FLT",
    "CODEX",
    "SKIDROW",
    "FITGIRL",
    "DODI",
}

KNOWN_FLAGS = {
    "BETA",
    "ALPHA",
    "MOD",
    "REPACK",
    "PORTABLE",
    "DEMO",
}


def normalize_archive_name(name: str) -> str:
    """Normalize an archive filename or folder name into a searchable title."""
    name = name.strip()
    # Remove extension
    name = re.sub(r"\.[^.\\/:]+$", "", name)
    # Remove version strings
    name = re.sub(
        r"v?\d+(?:[._]\d+)+",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Replace separators with spaces
    name = re.sub(r"[._\-]+", " ", name)
    # Remove version/release markers
    name = re.sub(
        r"\b(?:rev|release|version|v)\s*\d+[A-Za-z0-9]*\b",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove bracketed content
    name = re.sub(r"\[[^\]]+\]", "", name)
    name = re.sub(r"\([^\)]+\)", "", name)
    # Remove platform/source tags
    name = re.sub(
        r"\b(steam|gog|igdb|manual|x64|x86|win64|win32)\b",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove known release groups
    for group in KNOWN_RELEASE_GROUPS:
        name = re.sub(
            rf"\b{re.escape(group)}\b",
            "",
            name,
            flags=re.IGNORECASE,
        )
    # Remove known flags
    for flag in KNOWN_FLAGS:
        name = re.sub(
            rf"\b{re.escape(flag)}\b",
            "",
            name,
            flags=re.IGNORECASE,
        )
    # Cleanup whitespace
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip().title()


@dataclass
class ParsedArchive:
    raw_name: str
    title: str
    version: str | None = None
    release_group: str | None = None
    archive_type: str | None = None
    flags: list[str] = field(default_factory=list)


def parse_archive_name(name: str) -> ParsedArchive:
    """Parse an archive filename or folder name into structured metadata."""
    raw_name = name.strip()
    title = normalize_archive_name(raw_name)

    # Version detection
    version_match = re.search(
        r"v?(\d+(?:[._]\d+)+)",
        raw_name,
        flags=re.IGNORECASE,
    )
    version = (
    version_match.group(1).replace("_", ".")
    if version_match
    else None
    )

    # Release group detection
    release_group = None
    for group in KNOWN_RELEASE_GROUPS:
        if re.search(
            rf"\b{re.escape(group)}\b",
            raw_name,
            flags=re.IGNORECASE,
        ):
            release_group = group
            break

    # Archive type detection
    archive_type = None
    archive_match = re.search(
        r"\.(zip|rar|7z|tar\.gz|tar\.bz2)$",
        raw_name,
        flags=re.IGNORECASE,
    )
    if archive_match:
        archive_type = archive_match.group(1).upper()

    # Flag detection
    flags = []
    for flag in KNOWN_FLAGS:
        if re.search(
            rf"\b{re.escape(flag)}\b",
            raw_name,
            flags=re.IGNORECASE,
        ):
            flags.append(flag)

    return ParsedArchive(
        raw_name=raw_name,
        title=title,
        version=version,
        release_group=release_group,
        archive_type=archive_type,
        flags=flags,
    )


if __name__ == "__main__":
    samples = [
        "Portal_2_v1.3-FLT.zip",
        "Cyberpunk.2077.DODI.Repack.7z",
        "Hollow_Echoes-V0.22-BETA-Fan-Mod.rar",
        "Factorio_v1.1.110.zip",
    ]

    for sample in samples:
        print(parse_archive_name(sample))