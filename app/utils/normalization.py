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
    "wip", "public", "uncensored", "censored", "r18", "18+",
}
# Release-status words that are only noise at the end of a name ("Some Game Final", not "Final Saga").
TRAILING_NOISE = {"final", "fixed", "build", "release", "full", "completed"}
# Small words stay lowercase in titles unless they come first.
SMALL_WORDS = {"a", "an", "the", "of", "and", "or", "in", "on", "to", "for", "with", "at", "by"}
# Installment words: "Episode 3", "Ch.2", "Part 2", "Season 1", "Book 2".
INSTALLMENT_WORDS = {
    "ep": "episode", "episode": "episode", "chapter": "episode", "ch": "episode", "book": "episode",
    "part": "part", "pt": "part",
    "season": "season",
}

ARCHIVE_EXTENSION = re.compile(r"\.(zip|rar|7z|iso|exe|tar\.gz|tar\.bz2)$", re.IGNORECASE)
SEPARATOR = r"[\s._\-]"
# Dotted versions with an optional v/V prefix and one trailing letter: v1.2, V0.22, 1.03a, v.0.73, 0.5.5c.
DOTTED_VERSION = re.compile(rf"(?:^|{SEPARATOR})v?\.?(\d+(?:[._]\d+)+[a-z]?)(?={SEPARATOR}|$)", re.IGNORECASE)
# Numbered releases without dots: v12, Patch_19, Build 7, Update-3.
NUMBERED_VERSION = re.compile(rf"(?:^|{SEPARATOR})(?:v|rev|release|version|patch|update|build){SEPARATOR}?(\d+[a-z]?)(?={SEPARATOR}|$)", re.IGNORECASE)
# A version alone in brackets: [v1.0e], (v0.4), [0.5.2]. A bare number like (2019) is a year, not a version.
BRACKETED_VERSION = re.compile(r"[\[(]\s*(?:v\.?\s*(\d+(?:[._]\d+)*[a-z]?)|(\d+(?:[._]\d+)+[a-z]?))\s*[\])]", re.IGNORECASE)
# Build counters left beside a real version: "wip-5168", "build 5168".
BUILD_NUMBER = re.compile(rf"(?:^|{SEPARATOR})(?:wip|build){SEPARATOR}?\d+(?={SEPARATOR}|$)", re.IGNORECASE)
# DLsite product codes: RJ123456, VJ01000000, BJ123456.
SEASON_EPISODE = re.compile(r"s(\d{1,2})e(\d{1,3})", re.IGNORECASE)
DLSITE_CODE = re.compile(r"(?<![A-Za-z0-9])((?:RJ|VJ|BJ)\d{6,8})(?!\d)", re.IGNORECASE)


def title_key(text: str) -> str:
    """Letters and digits only, lowercased: the form two spellings of one title share."""
    return "".join(re.findall(r"[a-z0-9]+", text.lower()))


@dataclass
class _Installment:
    episode: int | None = None
    season: int | None = None
    part: int | None = None
    series_words: list[str] = field(default_factory=list)


def _find_installment(words: list[str]) -> _Installment:
    found = _Installment()
    index = 0
    while index < len(words):
        word = words[index].lower()
        following = words[index + 1] if index + 1 < len(words) else ""
        season_episode = SEASON_EPISODE.fullmatch(word)
        if season_episode:
            found.season, found.episode = int(season_episode.group(1)), int(season_episode.group(2))
            index += 1
            continue
        kind = INSTALLMENT_WORDS.get(word)
        if kind and following.isdigit() and getattr(found, kind) is None:
            setattr(found, kind, int(following))
            index += 2
            continue
        found.series_words.append(words[index])
        index += 1
    return found


def _title_case(words: list[str]) -> str:
    cased = []
    for index, word in enumerate(words):
        if index > 0 and word.lower() in SMALL_WORDS and not word.isupper():
            cased.append(word.lower())
        elif word.islower():
            cased.append(word[0].upper() + word[1:])
        else:
            cased.append(word)
    return " ".join(cased)


def _split_title_and_version(name: str) -> tuple[str, str | None]:
    title, version, _, _ = _parse_name(name)
    return title, version


def _parse_name(name: str) -> tuple[str, str | None, _Installment, dict[str, str]]:
    name = ARCHIVE_EXTENSION.sub("", name.strip())

    external_ids = {}
    code = DLSITE_CODE.search(name)
    if code:
        external_ids["dlsite"] = code.group(1).upper()
        name = DLSITE_CODE.sub(" ", name)

    bracketed = BRACKETED_VERSION.search(name)
    bracketed_version = (bracketed.group(1) or bracketed.group(2)).replace("_", ".") if bracketed else None
    name = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", name)

    version = None
    match = DOTTED_VERSION.search(name) or NUMBERED_VERSION.search(name)
    if match:
        version = match.group(1).replace("_", ".")
        name = name[:match.start()] + " " + name[match.end():]
    version = version or bracketed_version
    name = BUILD_NUMBER.sub(" ", name)

    tokens = [token for token in re.split(r"[\s._\-]+", name) if token]
    # "Author Mod" tags name the mod's author, not the game.
    for index, token in enumerate(tokens):
        if token.lower() == "mod" and index > 0:
            tokens[index - 1] = ""

    words: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if not token or lowered in NOISE_TOKENS or token.upper() in KNOWN_RELEASE_GROUPS:
            continue
        # A flag word that opens the name is part of the title ("Alpha Protocol"), not a release tag.
        if token.upper() in KNOWN_FLAGS and words:
            continue
        if SEASON_EPISODE.fullmatch(token):
            words.append(token.upper())
            continue
        # Archive names often drop spaces: "SomeGameTitle" -> "Some Game Title", "Episode5" -> "Episode 5".
        token = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", token)
        words.extend(token.split())
    while len(words) > 1 and words[-1].lower() in TRAILING_NOISE:
        words.pop()

    return _title_case(words), version, _find_installment(words), external_ids


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
    episode: int | None = None
    season: int | None = None
    part: int | None = None
    # The title without its installment words, shared by every episode of a series.
    series_title: str | None = None
    external_ids: dict[str, str] = field(default_factory=dict)


def parse_archive_name(name: str) -> ParsedArchive:
    """Parse an archive filename or folder name into structured metadata."""
    raw_name = name.strip()
    title, version, installment, external_ids = _parse_name(raw_name)
    is_installment = any(value is not None for value in (installment.episode, installment.season, installment.part))

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
        episode=installment.episode,
        season=installment.season,
        part=installment.part,
        series_title=(_title_case(installment.series_words) or None) if is_installment else None,
        external_ids=external_ids,
    )
