import unittest

import ai_client
import ai_notice


class AIFallbackNoticeTest(unittest.TestCase):

    def setUp(self):
        ai_notice.reset()
        self.shown = []

    def test_first_failure_notifies_with_reason(self):
        ai_notice.report_fallback(
            ai_client.AIError("AI server error: Unauthorized"), self.shown.append
        )

        self.assertEqual(len(self.shown), 1)
        self.assertIn("canned", self.shown[0].lower())
        self.assertIn("Unauthorized", self.shown[0])

    def test_repeated_failures_notify_only_once_per_run(self):
        for _ in range(5):
            ai_notice.report_fallback(ai_client.AIError("down"), self.shown.append)

        self.assertEqual(len(self.shown), 1)

    def test_reset_allows_a_new_notice_for_the_next_run(self):
        ai_notice.report_fallback(ai_client.AIError("down"), self.shown.append)
        ai_notice.reset()
        ai_notice.report_fallback(ai_client.AIError("down"), self.shown.append)

        self.assertEqual(len(self.shown), 2)

    def test_unexpected_errors_get_a_generic_reason(self):
        ai_notice.report_fallback(KeyError("secret internals"), self.shown.append)

        self.assertNotIn("secret internals", self.shown[0])
        self.assertIn("unexpected", self.shown[0].lower())

    def test_notifier_failure_does_not_break_sending(self):
        def broken(_message):
            raise RuntimeError("ui gone")

        ai_notice.report_fallback(ai_client.AIError("down"), broken)


if __name__ == "__main__":
    unittest.main()
