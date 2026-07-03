from handicap_ai.models import HandicapCover, Result1X2, TotalCover
from handicap_ai.settlement import settle_handicap, settle_one_x_two, settle_total


def test_settle_one_x_two():
    assert settle_one_x_two(home_score=2, away_score=0) == Result1X2.HOME_WIN
    assert settle_one_x_two(home_score=1, away_score=1) == Result1X2.DRAW
    assert settle_one_x_two(home_score=0, away_score=2) == Result1X2.AWAY_WIN


def test_settle_handicap_quarter_line_from_home_side():
    assert settle_handicap(home_score=3, away_score=1, home_line=-1.75) == HandicapCover.HOME_HALF_WIN
    assert settle_handicap(home_score=1, away_score=0, home_line=-1.75) == HandicapCover.AWAY_WIN
    assert settle_handicap(home_score=2, away_score=0, home_line=-2.0) == HandicapCover.PUSH


def test_settle_total_quarter_line_from_over_side():
    assert settle_total(home_score=2, away_score=1, total_line=2.75) == TotalCover.OVER_HALF_WIN
    assert settle_total(home_score=1, away_score=1, total_line=2.25) == TotalCover.UNDER_HALF_WIN
    assert settle_total(home_score=1, away_score=1, total_line=2.0) == TotalCover.PUSH
