"""What the [signals] table in profile.toml adds to a score, and the reason it gives.

Opt-in: a profile without [signals] changes no ranking. With one, every point it
moves is named, and the breakdown carries that name, so a ranking can be argued
with rather than trusted.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobhunt import signals

SIGNALS = {"interview_take_home": 5, "interview_live_coding": -8, "ai_encouraged": 3,
           "friction_high": -4, "comp_floor": 170, "comp_meets_floor": 2, "comp_below_floor": -6}


def sig(**over):
    """Signals shaped as signals.extract returns them, each set to earn nothing."""
    base = {"interview": ["unknown"], "ai_stance": "silent", "friction": "unknown",
            "comp_low": None, "comp_high": None, "stack": []}
    base.update(over)
    return base


def bonus(**over):
    return signals.bonus(sig(**over), {"signals": SIGNALS})


class OptInTests(unittest.TestCase):
    def test_a_profile_without_signals_moves_nothing(self):
        self.assertEqual(signals.bonus(sig(interview=["live_coding"], friction="high"), {}),
                         (0.0, []))

    def test_a_signal_the_profile_does_not_price_moves_nothing(self):
        self.assertEqual(bonus(interview=["pairing"]), (0.0, []))


class InterviewTests(unittest.TestCase):
    def test_a_rewarded_format_adds_its_points_and_names_itself(self):
        self.assertEqual(bonus(interview=["take_home"]), (5, ["+5 interview:take_home"]))

    def test_a_penalised_format_subtracts_and_is_named_without_a_plus(self):
        self.assertEqual(bonus(interview=["live_coding"]), (-8, ["-8 interview:live_coding"]))

    def test_every_format_a_posting_states_is_counted(self):
        delta, why = bonus(interview=["take_home", "live_coding"])
        self.assertEqual((delta, why), (-3, ["+5 interview:take_home", "-8 interview:live_coding"]))


class StanceAndFrictionTests(unittest.TestCase):
    def test_the_ai_stance_is_priced_and_named(self):
        self.assertEqual(bonus(ai_stance="encouraged"), (3, ["+3 ai:encouraged"]))

    def test_application_friction_is_priced_and_named(self):
        self.assertEqual(bonus(friction="high"), (-4, ["-4 apply:high"]))


class CompFloorTests(unittest.TestCase):
    def test_pay_reaching_the_floor_meets_it(self):
        self.assertEqual(bonus(comp_low=150, comp_high=170), (2, ["+2 comp:150-170k"]))

    def test_pay_topping_out_below_the_floor_is_penalised(self):
        self.assertEqual(bonus(comp_low=140, comp_high=160), (-6, ["-6 comp:140-160k"]))

    def test_unpublished_pay_is_neither_rewarded_nor_penalised(self):
        self.assertEqual(bonus(comp_low=None, comp_high=None), (0.0, []))


class CombinedTests(unittest.TestCase):
    def test_the_reasons_add_up_to_the_delta_in_a_fixed_order(self):
        delta, why = bonus(interview=["take_home"], ai_stance="encouraged", friction="high",
                           comp_low=150, comp_high=180)
        self.assertEqual(delta, 5 + 3 - 4 + 2)
        self.assertEqual(why, ["+5 interview:take_home", "+3 ai:encouraged", "-4 apply:high",
                               "+2 comp:150-180k"])


if __name__ == "__main__":
    unittest.main()
