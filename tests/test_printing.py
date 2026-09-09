"""Печать пропуска на обе стороны: авто-дуплекс и ручной переворот листа."""
import types

from PIL import Image

from getpass_core import printing


def _fake_ps(returncode=0, stdout="", stderr=""):
    return lambda args, timeout: types.SimpleNamespace(
        returncode=returncode, stdout=stdout, stderr=stderr)


class TestPrinterCanDuplex:
    def test_true_when_driver_reports_duplex(self, monkeypatch):
        monkeypatch.setattr(printing, "_ps", _fake_ps(stdout="True\n"))
        assert printing.printer_can_duplex() is True

    def test_false_when_driver_reports_no_duplex(self, monkeypatch):
        monkeypatch.setattr(printing, "_ps", _fake_ps(stdout="False\n"))
        assert printing.printer_can_duplex() is False

    def test_false_on_powershell_error(self, monkeypatch):
        monkeypatch.setattr(printing, "_ps", _fake_ps(returncode=1, stderr="oops"))
        assert printing.printer_can_duplex() is False


class TestPrintPassTwoSided:
    def test_uses_single_duplex_job_when_supported(self, monkeypatch):
        calls = []
        monkeypatch.setattr(printing, "printer_can_duplex", lambda name=None: True)
        monkeypatch.setattr(
            printing, "_send_duplex_job",
            lambda f, b, name=None: (calls.append("duplex"), (True, ""))[1])
        confirmed = []
        ok, err = printing.print_pass_two_sided(
            Image.new("RGB", (10, 10)), Image.new("RGB", (10, 10)),
            confirm_flip=lambda: confirmed.append(1) or True)
        assert (ok, err) == (True, "")
        assert calls == ["duplex"]
        assert confirmed == []          # авто-дуплекс — переворот листа не нужен

    def test_manual_flow_asks_to_flip_before_back_side(self, monkeypatch):
        sent = []
        monkeypatch.setattr(printing, "printer_can_duplex", lambda name=None: False)
        monkeypatch.setattr(
            printing, "send_image_to_printer",
            lambda img, name=None: (sent.append(img), (True, ""))[1])
        confirmed = []
        front, back = Image.new("RGB", (10, 10), "red"), Image.new("RGB", (10, 10), "blue")
        ok, err = printing.print_pass_two_sided(
            front, back, confirm_flip=lambda: confirmed.append(1) or True)
        assert ok is True
        assert sent == [front, back]    # сначала лицо, потом (после вопроса) оборот
        assert confirmed == [1]

    def test_manual_flow_stops_if_flip_declined(self, monkeypatch):
        sent = []
        monkeypatch.setattr(printing, "printer_can_duplex", lambda name=None: False)
        monkeypatch.setattr(
            printing, "send_image_to_printer",
            lambda img, name=None: (sent.append(img), (True, ""))[1])
        front, back = Image.new("RGB", (10, 10)), Image.new("RGB", (10, 10))
        ok, err = printing.print_pass_two_sided(front, back, confirm_flip=lambda: False)
        assert ok is False
        assert sent == [front]          # оборот не отправлялся — пользователь отменил

    def test_manual_flow_stops_if_front_fails(self, monkeypatch):
        monkeypatch.setattr(printing, "printer_can_duplex", lambda name=None: False)
        monkeypatch.setattr(printing, "send_image_to_printer",
                            lambda img, name=None: (False, "принтер офлайн"))
        confirmed = []
        ok, err = printing.print_pass_two_sided(
            Image.new("RGB", (10, 10)), Image.new("RGB", (10, 10)),
            confirm_flip=lambda: confirmed.append(1) or True)
        assert (ok, err) == (False, "принтер офлайн")
        assert confirmed == []          # до вопроса о перевороте не дошли

    def test_no_confirm_callback_prints_both_sides_unconditionally(self, monkeypatch):
        """confirm_flip не задан (например, вызов не из UI) — печатаем без
        подтверждения, а не падаем и не молчим."""
        sent = []
        monkeypatch.setattr(printing, "printer_can_duplex", lambda name=None: False)
        monkeypatch.setattr(
            printing, "send_image_to_printer",
            lambda img, name=None: (sent.append(img), (True, ""))[1])
        front, back = Image.new("RGB", (10, 10)), Image.new("RGB", (10, 10))
        ok, err = printing.print_pass_two_sided(front, back)
        assert ok is True
        assert sent == [front, back]
