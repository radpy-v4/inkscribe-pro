"""Regression tests for application safety and bounded notebook preview."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.safe_ui import SafeArkaPlanNotDonusturucu
from src.storage import NotebookManager


class TestSafetyFixes(unittest.TestCase):
    def test_ai_consent_defaults_to_no_and_denial_keeps_ai_off(self):
        app = object.__new__(SafeArkaPlanNotDonusturucu)
        app.root = MagicMock()
        app.config = MagicMock()
        app.config.ai_onay_verildi = False
        app.config.ai_modu_aktif = True
        app.yazma_modu_aktif = False
        app.alt_cubuk_gecici_mesaj = MagicMock()
        with patch("src.safe_ui.messagebox.askyesno", return_value=False) as ask:
            self.assertFalse(app._ai_onay_iste())
        self.assertEqual(ask.call_args.kwargs["default"], "no")
        self.assertFalse(app.config.ai_onay_verildi)
        self.assertFalse(app.config.ai_modu_aktif)
        app.config.kaydet.assert_called_once()

    def test_shutdown_stops_resources_and_destroys_tk_without_hard_exit(self):
        app = object.__new__(SafeArkaPlanNotDonusturucu)
        app.tray = MagicMock()
        app.hotkey_listener = MagicMock()
        app.root = MagicMock()
        app.programi_kapat()
        app.tray.durdur.assert_called_once()
        app.hotkey_listener.stop.assert_called_once()
        app.root.destroy.assert_called_once()
        self.assertTrue(app._closing)

    def test_pending_strokes_are_rescaled(self):
        app = object.__new__(SafeArkaPlanNotDonusturucu)
        app.tum_stroke_noktalari = [[MagicMock(x=10.0, y=20.0)]]
        app.aktif_noktalar = []
        app.son_x = 10.0
        app.son_y = 20.0
        app._olcekle_noktalari((100, 100), (200, 300))
        point = app.tum_stroke_noktalari[0][0]
        self.assertEqual((point.x, point.y), (20.0, 60.0))
        self.assertEqual((app.son_x, app.son_y), (20.0, 60.0))

    def test_blank_canvas_global_undo_is_disabled(self):
        app = object.__new__(SafeArkaPlanNotDonusturucu)
        with patch("src.safe_ui.ui.logger") as logger:
            app._arka_planda_ctrl_z_bas()
        logger.info.assert_called_once()

    def test_target_input_requires_confirmed_foreground_window(self):
        app = object.__new__(SafeArkaPlanNotDonusturucu)
        app.son_hedef_hwnd = 123
        user32 = MagicMock()
        user32.IsWindow.return_value = True
        user32.GetForegroundWindow.side_effect = [456, 123]
        app.ui = None
        with patch("src.safe_ui.ui.user32", user32):
            self.assertTrue(app._hedef_pencereyi_etkinlestir())
        user32.SetForegroundWindow.assert_called_once_with(123)

    def test_notebook_preview_reads_recent_tail_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = NotebookManager(tmp)
            path = manager.aktif_defter_dosyasi
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Header\n--- 01.01.2026 ---\nold\nnew one\nnew two\n")
            self.assertEqual(manager.son_satirlari_oku(2), ["new one", "new two"])
            self.assertEqual(manager.son_satirlari_oku(0), [])


if __name__ == "__main__":
    unittest.main()
