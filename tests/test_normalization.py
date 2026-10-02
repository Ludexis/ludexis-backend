import pytest

from app.utils.normalization import parse_archive_name


@pytest.mark.parametrize(
    ("name", "title", "version"),
    [
        ("Portal_2_v1.3-FLT.zip", "Portal 2", "1.3"),
        ("Cyberpunk.2077.DODI.Repack.7z", "Cyberpunk 2077", None),
        ("SomeGameTitle-v1.2.3c-pc-compressed.zip", "Some Game Title", "1.2.3c"),
        ("Another_Game.v.0.73-pc.zip", "Another Game", "0.73"),
        ("QuietHarbor-Patch_12-pc.zip", "Quiet Harbor", "12"),
        ("Long_Story-V0.22_BETA-hotfix-win64.rar", "Long Story", "0.22"),
        ("Example_Title-V0.22-BETA-Authors-Mod.rar", "Example Title", "0.22"),
        ("Saga.Episode3.0.4.1-patreon-pc.zip", "Saga Episode 3", "0.4.1"),
        ("Grand Theft Auto IV (GOG)", "Grand Theft Auto IV", None),
        ("The.Witcher.3.Wild.Hunt.GOTY-v4.04.iso", "The Witcher 3 Wild Hunt", "4.04"),
    ],
)
def test_parse_archive_name(name, title, version):
    parsed = parse_archive_name(name)
    assert parsed.title == title
    assert parsed.version == version


@pytest.mark.parametrize(
    ("name", "title", "version"),
    [
        ("Harbor Tales v21.0.0 wip-5168", "Harbor Tales", "21.0.0"),
        ("Harbor Tales v1.4 build 902", "Harbor Tales", "1.4"),
        ("Quiet.Meadow.v0.4.1.Public", "Quiet Meadow", "0.4.1"),
        ("Lantern Town [v1.0e]", "Lantern Town", "1.0e"),
        ("Lantern Town (v0.4)", "Lantern Town", "0.4"),
        ("Lantern Town (2019)", "Lantern Town", None),
        ("Paper Moon v2.0 Final", "Paper Moon", "2.0"),
        ("Final Light v1.1", "Final Light", "1.1"),
        ("Copper Road v3.0 Uncensored R18", "Copper Road", "3.0"),
        ("Being a HERO", "Being a HERO", None),
        ("tale of the north wind", "Tale of the North Wind", None),
        ("The Long Night", "The Long Night", None),
        ("Alpha Story v1.0", "Alpha Story", "1.0"),
        ("Early Light Demo v0.1", "Early Light", "0.1"),
    ],
)
def test_noise_and_bracketed_versions(name, title, version):
    parsed = parse_archive_name(name)
    assert parsed.title == title
    assert parsed.version == version


@pytest.mark.parametrize(
    ("name", "episode", "season", "part", "series_title"),
    [
        ("Moonlit Ep 3 v0.5", 3, None, None, "Moonlit"),
        ("Moonlit.Ep.3.v0.5", 3, None, None, "Moonlit"),
        ("Moonlit EP03", 3, None, None, "Moonlit"),
        ("MoonlitEp3-v0.5-pc", 3, None, None, "Moonlit"),
        ("Moonlit Episode 12", 12, None, None, "Moonlit"),
        ("Tale of the Lake Chapter 2", 2, None, None, "Tale of the Lake"),
        ("Tale of the Lake Ch.2", 2, None, None, "Tale of the Lake"),
        ("Bright Days Part 2 v0.3", None, None, 2, "Bright Days"),
        ("Bright Days Season 1 Episode 4", 4, 1, None, "Bright Days"),
        ("Bright Days S01E03", 3, 1, None, "Bright Days"),
        ("Iron Book 2", 2, None, None, "Iron"),
        ("Plain Title v1.0", None, None, None, None),
    ],
)
def test_installments(name, episode, season, part, series_title):
    parsed = parse_archive_name(name)
    assert (parsed.episode, parsed.season, parsed.part) == (episode, season, part)
    assert parsed.series_title == series_title


def test_installment_words_stay_in_the_title():
    # Each episode keeps its own title; only series_title drops the installment.
    assert parse_archive_name("Moonlit Ep 3 v0.5").title == "Moonlit Ep 3"


def test_dlsite_codes_become_external_ids():
    parsed = parse_archive_name("[RJ01234567] Silver Bell v1.2")
    assert parsed.title == "Silver Bell"
    assert parsed.version == "1.2"
    assert parsed.external_ids == {"dlsite": "RJ01234567"}
    assert parse_archive_name("Silver Bell").external_ids == {}


def test_folder_names_keep_dotted_words():
    # Only real archive extensions are stripped, so folder names are not truncated.
    assert parse_archive_name("Studio.Game.Name").title == "Studio Game Name"
