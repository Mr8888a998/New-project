from handicap_ai.names import normalize_team_name


def test_normalize_team_name_collapses_case_spaces_and_punctuation():
    assert normalize_team_name("  Côte-d'Ivoire  ") == "cote divoire"
    assert normalize_team_name("ENGLAND") == "england"
