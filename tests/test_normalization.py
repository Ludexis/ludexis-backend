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


def test_folder_names_keep_dotted_words():
    # Only real archive extensions are stripped, so folder names are not truncated.
    assert parse_archive_name("Studio.Game.Name").title == "Studio Game Name"
