"""
Unit tests for MessageFilterEngine classification rules, branch filtering, and forward format.
"""

import unittest
import json
from filter_engine import MessageFilterEngine


class TestMessageFilterEngine(unittest.TestCase):

    def setUp(self):
        self.engine = MessageFilterEngine()

    def test_nit_srinagar_branch_filter(self):
        """Verify that in NIT Srinagar group, only Mechanical and all-batch notices are accepted."""
        # Other branch specific message -> must be ignored!
        ece_msg = "Ece ki class kha lagegi kal morning me?"
        result_ece = self.engine.process_message("Nit srinagar batch 2026-30", "+91 99999", "10:00 AM", ece_msg)
        self.assertIsNone(result_ece, "ECE message in NIT Srinagar group should be filtered out!")

        cse_msg = "CSE department coding test link is active now."
        result_cse = self.engine.process_message("Nit srinagar batch 2026-30", "+91 99999", "10:00 AM", cse_msg)
        self.assertIsNone(result_cse, "CSE message in NIT Srinagar group should be filtered out!")

        # Mechanical branch specific message -> must be accepted!
        mech_msg = "Tomorrow Mechanical batch workshop lab at 10 AM. Bring your apron."
        result_mech = self.engine.process_message("Nit srinagar batch 2026-30", "+91 99999", "10:00 AM", mech_msg)
        self.assertIsNotNone(result_mech, "Mechanical message should be accepted!")

        # General all-batch notice -> must be accepted!
        general_notice = "All students of batch 2026 are informed that fee submission deadline is Friday."
        result_gen = self.engine.process_message("Nit srinagar batch 2026-30", "+91 99999", "10:00 AM", general_notice)
        self.assertIsNotNone(result_gen, "All-batch general notice should be accepted!")
        self.assertEqual(result_gen["category"], "ANNOUNCEMENT")

    def test_study_material_category(self):
        """Verify notes, PDFs, and study modules are detected."""
        notes_msg = "Here are the Engineering Chemistry Unit 1 handwritten notes and module pdf."
        result = self.engine.process_message("Engineering Chemistry", "CR Alex", "02:00 PM", notes_msg)
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "STUDY_MATERIAL")
        self.assertIn("notes", result["tags"])
        self.assertIn("pdf", result["tags"])

    def test_forward_message_format(self):
        """Verify formatted message contains Group, Time, Full Message, and Summary."""
        msg = "IMPORTANT CIRCULAR: End-semester exam dates announced on official portal. Check datesheet."
        processed = self.engine.process_message("College Notices", "Dean Office", "11:00 AM", msg)
        self.assertIsNotNone(processed)

        forward_text = self.engine.generate_formatted_forward(processed)
        self.assertIn("*Group:* College Notices", forward_text)
        self.assertIn("*Time:* 11:00 AM", forward_text)
        self.assertIn("*Original Message:*", forward_text)
        self.assertIn("*Summary:*", forward_text)

    def test_loop_prevention(self):
        """Verify bot's own forwarded alerts are ignored to prevent loops."""
        bot_alert = (
            "🔔 *IMPORTANT NOTICE ALERT* 🔔\n"
            "👥 *Group:* College Notices\n"
            "📝 *Original Message:*\nSample Notice\n"
            "📋 *Summary:* Sample summary"
        )
        result = self.engine.process_message("College Notices", "Akshuu", "10:00 AM", bot_alert)
        self.assertIsNone(result, "Bot alert should be ignored!")


if __name__ == "__main__":
    unittest.main()
