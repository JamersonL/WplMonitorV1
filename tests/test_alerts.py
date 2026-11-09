import json
import tempfile
import unittest
from datetime import datetime, time
from pathlib import Path

import pandas as pd

from core.alert_config import AlertConfigStore
from core.alert_engine import AlertStateStore, evaluate_critical_drop, filter_issuer_alerts, is_within_schedule


class AlertConfigTests(unittest.TestCase):
    def test_default_issuer_cooldown_preserves_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AlertConfigStore(Path(tmp) / "alerts.json", legacy_window_minutes=19)
            settings = store.get_merchant("merchant")
            self.assertEqual(settings["issuer"]["cooldown_minutes"], 19)
            self.assertFalse(settings["critical_drop"]["enabled"])

    def test_save_and_reload_merchant_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alerts.json"
            store = AlertConfigStore(path)
            settings = {
                "schedule": {"start": "07:00", "end": "22:30"},
                "issuer": {"enabled": True, "min_transactions": 123, "max_approval_rate": 12.5,
                           "max_recurring_percentage": 65, "cooldown_minutes": 25},
                "critical_drop": {"enabled": True, "threshold_percent": 35,
                                  "minimum_baseline_transactions": 200, "cooldown_minutes": 40},
            }
            store.save_merchant("merchant_a", settings)
            self.assertEqual(store.get_merchant("merchant_a"), settings)
            self.assertEqual(json.loads(path.read_text())["merchants"]["merchant_a"], settings)

    def test_invalid_threshold_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AlertConfigStore(Path(tmp) / "alerts.json")
            settings = store.get_merchant("merchant")
            settings["critical_drop"]["threshold_percent"] = 101
            with self.assertRaises(ValueError):
                store.save_merchant("merchant", settings)


class AlertEngineTests(unittest.TestCase):
    def test_existing_issuer_thresholds_are_preserved(self):
        df = pd.DataFrame([
            {"total_tx": 151, "approval_rate": 9.9, "recurring_percentage": 69},
            {"total_tx": 150, "approval_rate": 5, "recurring_percentage": 20},
            {"total_tx": 500, "approval_rate": 10, "recurring_percentage": 20},
        ])
        rules = {"enabled": True, "min_transactions": 150, "max_approval_rate": 10,
                 "max_recurring_percentage": 70}
        result = filter_issuer_alerts(df, rules)
        self.assertEqual(len(result), 1)
        self.assertEqual(int(result.iloc[0]["total_tx"]), 151)

    def test_critical_drop_comparison(self):
        rules = {"enabled": True, "threshold_percent": 30, "minimum_baseline_transactions": 100}
        result = evaluate_critical_drop(60, 100, rules)
        self.assertEqual(result["drop_percent"], 40.0)
        self.assertIsNone(evaluate_critical_drop(80, 100, rules))
        self.assertIsNone(evaluate_critical_drop(0, 50, rules))

    def test_schedule_including_overnight(self):
        regular = {"start": "08:00", "end": "23:00"}
        self.assertTrue(is_within_schedule(time(12, 0), regular))
        self.assertFalse(is_within_schedule(time(23, 30), regular))
        overnight = {"start": "22:00", "end": "06:00"}
        self.assertTrue(is_within_schedule(time(23, 0), overnight))
        self.assertTrue(is_within_schedule(time(5, 0), overnight))
        self.assertFalse(is_within_schedule(time(12, 0), overnight))

    def test_cooldowns_are_separate_by_alert_type_and_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            store = AlertStateStore(path)
            now = datetime(2026, 10, 30, 10, 0, 0)
            store.mark_sent("merchant", "issuer", now)
            self.assertIsNotNone(store.cooldown_remaining("merchant", "issuer", 30, now))
            self.assertIsNone(store.cooldown_remaining("merchant", "critical_drop", 30, now))
            self.assertIsNotNone(AlertStateStore(path).cooldown_remaining("merchant", "issuer", 30, now))


if __name__ == "__main__":
    unittest.main()
