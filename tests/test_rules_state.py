"""Rule execution state reset tests."""

from datetime import datetime

import config as c


def test_reset_rule_execution_state_clears_indexed_state():
    c.rule_last_executed[1] = datetime(2026, 7, 7, tzinfo=c.JST)
    c.rule_last_comment_count[1] = 10

    c.reset_rule_execution_state()

    assert c.rule_last_executed == {}
    assert c.rule_last_comment_count == {}