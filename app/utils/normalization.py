import re


def normalize_archive_name(name: str) -> str:
    """Normalize an archive filename or folder name into a searchable title."""
    name = name.strip()
    # Remove extension
    name = re.sub(r"\.[^.\\/:]+$", "", name)
    # Replace separators with spaces
    name = re.sub(r"[._\-]+", " ", name)
    # Remove common version prefixes and tags
    name = re.sub(r"\bv?\d+(?:[._]\d+){1,}([._]\w+)?\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b(?:rev|release|version|v)\s*\d+[A-Za-z0-9]*\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\[[^\]]+\]", "", name)
    name = re.sub(r"\([^\)]+\)", "", name)
    name = re.sub(r"\b(steam|gog|igdb|manual|x64|x86|win64|win32)\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s{2,}", " ", name)
    return name.strip().title()
