import pytest

from cps import codeplug as C, link, ops
from fake_radio import FakeCfwRadio
from test_codeplug import sample


@pytest.fixture
def radio():
    r = FakeCfwRadio()
    yield r
    r.close()


def test_write_read_round_trip(radio):
    port = "tcp:127.0.0.1:%d" % radio.port
    cp = sample()
    data = ops.write_radio(port, cp, log=lambda s: None)
    assert radio.valid() and bytes(radio.flash[:len(data)]) == data
    assert radio.order[-1] == 0, "header block must be written last"
    back, raw, inf = ops.read_radio(port, log=lambda s: None)
    assert raw == data and back == cp and inf["valid"]


def test_diff_shown_and_cancel(radio):
    port = "tcp:127.0.0.1:%d" % radio.port
    ops.write_radio(port, sample(), log=lambda s: None)
    cp = sample()
    cp.channels[0].name = "RENAMED"
    seen = []
    assert ops.write_radio(port, cp, log=lambda s: None, confirm=lambda lines: seen.extend(lines) or False) is None
    assert any("RENAMED" in l for l in seen)
    assert ops.read_radio(port, log=lambda s: None)[0].channels[0].name != "RENAMED"


def test_invalid_codeplug_not_written(radio):
    cp = sample()
    cp.channels[0].rx_hz = 1
    with pytest.raises(C.CodeplugError):
        ops.write_radio("tcp:127.0.0.1:%d" % radio.port, cp, log=lambda s: None)
    assert radio.writes == 0


def test_refuses_stock_radio():
    r = FakeCfwRadio(ident=b"D890UV\0")
    try:
        with pytest.raises(link.LinkError, match="not the cfw"):
            ops.write_radio("tcp:127.0.0.1:%d" % r.port, sample(), log=lambda s: None)
        assert r.writes == 0
    finally:
        r.close()


def test_write_protected_build():
    r = FakeCfwRadio(write_protected=True)
    try:
        with pytest.raises(link.LinkError, match="write-protected"):
            ops.write_radio("tcp:127.0.0.1:%d" % r.port, sample(), log=lambda s: None)
        assert r.writes == 0
    finally:
        r.close()


def test_hardware_port_needs_flag(monkeypatch):
    class P:
        hardware = True

        def close(self):
            pass
    monkeypatch.setattr(link, "open_port", lambda spec, timeout=5.0: P())
    with pytest.raises(link.LinkError, match="allow-hardware"):
        link.with_radio("/dev/ttyUSB0", lambda r: None, writing=True)
