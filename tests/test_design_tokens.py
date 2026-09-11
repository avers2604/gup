from getpass_design import tokens as shared
from getpass_ui import tokens as legacy


def test_get_brand_colors_are_unchanged():
    assert shared.BRAND == {
        "navy": "#24305E",
        "teal": "#009CBC",
        "red": "#E4032E",
        "yellow": "#FBBA00",
        "lime": "#AFCB37",
        "mint": "#8ACBC1",
        "grey": "#DADADA",
    }


def test_legacy_tk_tokens_reexport_shared_objects():
    assert legacy.BRAND is shared.BRAND
    assert legacy.LIGHT is shared.LIGHT
    assert legacy.DARK is shared.DARK
    assert legacy.PALETTES is shared.PALETTES
    assert legacy.SPACE is shared.SPACE
    assert legacy.RADIUS is shared.RADIUS
    assert legacy.TYPE is shared.TYPE
