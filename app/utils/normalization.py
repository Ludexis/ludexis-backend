from dataclasses import dataclass, field
import re


KNOWN_RELEASE_GROUPS = {
    "RUNE",
    "FLT",
    "CODEX",
    "SKIDROW",
    "FITGIRL",
    "DODI",
    "ELAMIGOS",
    "XATAB",
    "STEAMRIP",
    "RG",
    "MECHANICS",
}

KNOWN_FLAGS = {
    "BETA",
    "ALPHA",
    "MOD",
    "MODDED",
    "REPACK",
    "PORTABLE",
    "DEMO",
    "PATCH",
    "HOTFIX",
    "UPDATE",
    "EARLY",
    "ACCESS",
}

# Packaging, platform and distribution tags that never belong to a game's title.
NOISE_TOKENS = {
    "pc", "win", "windows", "win32", "win64", "x64", "x86", "mac", "osx", "linux", "android",
    "compressed", "wincompress", "patreon", "steam", "gog", "igdb", "manual", "dlc",
    "ultimate", "gold", "complete", "definitive", "enhanced", "goty", "edition",
}

ARCHIVE_EXTENSION = re.compile(r"\.(zip|rar|7z|iso|exe|tar\.gz|tar\.bz2)$", re.IGNORECASE)
SEPARATOR = r"[\s._\-]"
# Dotted versions with an optional v/V prefix and one trailing letter: v1.2, V0.22, 1.03a, v.0.73, 0.5.5c.
DOTTED_VERSION = re.compile(rf"(?:^|{SEPARATOR})v?\.?(\d+(?:[._]\d+)+[a-z]?)(?={SEPARATOR}|$)", re.IGNORECASE)
# Numbered releases without dots: v12, Patch_19, Build 7, Update-3.
NUMBERED_VERSION = re.compile(rf"(?:^|{SEPARATOR})(?:v|rev|release|version|patch|update|build){SEPARATOR}?(\d+[a-z]?)(?={SEPARATOR}|$)", re.IGNORECASE)


def _split_title_and_version(name: str) -> tuple[str, str | None]:
    name = ARCHIVE_EXTENSION.sub("", name.strip())
    name = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", name)

    version = None
    match = DOTTED_VERSION.search(name) or NUMBERED_VERSION.search(name)
    if match:
        version = match.group(1).replace("_", ".")
        name = name[:match.start()] + " " + name[match.end():]

    tokens = [token for token in re.split(r"[\s._\-]+", name) if token]
    # "Author Mod" tags name the mod's author, not the game.
    for index, token in enumerate(tokens):
        if token.lower() == "mod" and index > 0:
            tokens[index - 1] = ""

    words: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if not token or lowered in NOISE_TOKENS or token.upper() in KNOWN_FLAGS or token.upper() in KNOWN_RELEASE_GROUPS:
            continue
        # Archive names often drop spaces: "SomeGameTitle" -> "Some Game Title", "Episode5" -> "Episode 5".
        token = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", token)
        words.extend(token.split())

    title = " ".join(word[0].upper() + word[1:] if word.islower() else word for word in words)
    return title, version


def normalize_archive_name(name: str) -> str:
    """Normalize an archive filename or folder name into a searchable title."""
    return _split_title_and_version(name)[0]


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
    title, version = _split_title_and_version(raw_name)

    release_group = None
    for group in KNOWN_RELEASE_GROUPS:
        if re.search(
            rf"\b{re.escape(group)}\b",
            raw_name,
            flags=re.IGNORECASE,
        ):
            release_group = group
            break

    archive_type = None
    archive_match = ARCHIVE_EXTENSION.search(raw_name)
    if archive_match:
        archive_type = archive_match.group(1).upper()

    flags = []
    for flag in KNOWN_FLAGS:
        if re.search(
            rf"(?<![A-Za-z]){re.escape(flag)}(?![A-Za-z])",
            raw_name,
            flags=re.IGNORECASE,
        ):
            flags.append(flag)

    return ParsedArchive(
        raw_name=raw_name,
        title=title or raw_name,
        version=version,
        release_group=release_group,
        archive_type=archive_type,
        flags=flags,
    )
