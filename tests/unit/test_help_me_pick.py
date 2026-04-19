"""Three yes/no questions map to one of T1..T5 with a 'recommended' badge."""
from __future__ import annotations

import io
import pytest
from bin.help_me_pick import recommend


@pytest.mark.parametrize("answers,expected", [
    # (pools_drugs, one_country_one_condition, rerunning_a_published_MA) -> template
    (("n", "n", "n"), "T5"),   # Living MA seed
    (("y", "n", "n"), "T1"),   # Pairwise mini-MA
    (("n", "y", "n"), "T3"),   # Burden snapshot
    (("n", "n", "y"), "T4"),   # Replication
    (("y", "n", "y"), "T4"),   # Replication wins over pairwise if rerunning
    (("n", "y", "y"), "T4"),   # Replication wins over burden if rerunning
])
def test_recommend_maps_answers_to_template(answers, expected):
    assert recommend(*answers) == expected


def test_default_is_T1_when_nothing_picked():
    # If all answers are empty / ambiguous, fall back to T1 (most common first project)
    assert recommend("", "", "") == "T1"
