import pandas as pd

from insightcopilot.grounding import numbers_in_text, ungrounded

df = pd.DataFrame({"city": ["Jakarta", "Batam"], "revenue": [400.0, 50.0]})


def test_grounded_numbers_pass():
    assert ungrounded("Jakarta made 400 of 450 total revenue.", df) == []


def test_invented_number_flagged():
    assert ungrounded("Revenue grew to 9,999.", df) == [9999.0]


def test_share_percentage_is_derivable():
    assert ungrounded("Jakarta is 89% of revenue.", df) == []


def test_suffix_parsing():
    assert numbers_in_text("1.2M and 5k") == [1_200_000.0, 5000.0]
