import pytest

from cps import codeplug as C, validate as V
from test_codeplug import sample


def full():
    s = sample()
    s.keys = [C.Key("P25 key", "P25_AES256", 1, 0x84, "00" * 32), C.Key("DMR BP", "DMR_BP", 7, 0, "1234")]
    s.dstar_rpts = [C.DstarRepeater("Test Rpt B", "XX0RPT B", "XX0RPT G", 145670000, 145070000, True)]
    s.trunksys[0].bandplan = [C.BandPlan(1, 851006250, 6250, -45000000, 12500, False, 1),
                              C.BandPlan(2, 762006250, 12500, 30000000, 12500, True, 2)]
    s.trunksys.append(C.TrunkSystem("NX", "NXDN_C", 5, control_channels=[451000000]))
    s.channels[7].trunksys, s.channels[7].nxdn_rate, s.channels[7].vocoder = 2, 9600, "AMBE+2 EFR"
    s.channels[5].key, s.channels[5].talkaround = 0, True
    s.channels[9].dgid_tx, s.channels[9].ysf_mode, s.channels[9].wiresx = 30, "VW", True
    s.channels[8].dstar_rpt = 0
    s.channels[4].talkaround, s.channels[4].tdma_direct = True, True
    s.channels[3].key = 1
    s.digi.dstar_dprs, s.digi.ysf_wiresx_room = True, 12345
    return s


def test_round_trip_all_digital_sections():
    s = full()
    assert V.errors(V.validate(s)) == []
    b = C.encode(s)
    s2 = C.decode(b)
    assert s2 == s and C.encode(s2) == b
    assert C.from_dict(C.to_dict(s)) == s


def test_old_v1_codeplug_without_new_sections_still_decodes():
    import struct
    b = bytearray(C.encode(C.new_codeplug().normalize()))
    nsec = struct.unpack_from("<H", b, 16)[0]
    ids = [struct.unpack_from("<H", b, 32 + 16 * i)[0] for i in range(nsec)]
    assert 11 in ids and 15 in ids


@pytest.mark.parametrize("patch,needle", [
    (lambda s: setattr(s.channels[3], "vocoder", "IMBE"), "vocoder"),
    (lambda s: setattr(s.channels[5], "key", 1), "DMR key"),
    (lambda s: setattr(s.channels[3], "key", 9), "key 9"),
    (lambda s: setattr(s.keys[0], "hex", "00" * 16), "32 bytes"),
    (lambda s: setattr(s.channels[7], "trunksys", 0), "is P25"),
    (lambda s: setattr(s.channels[9], "dgid_tx", 100), "TX DG-ID"),
    (lambda s: setattr(s.channels[8], "dstar_rpt", 4), "D-STAR repeater"),
    (lambda s: s.trunksys[0].bandplan.append(C.BandPlan(1)), "repeat"),
    (lambda s: setattr(s.trunksys[0].bandplan[1], "slots", 1), "TDMA"),
    (lambda s: setattr(s.dstar_rpts[0], "rpt1", "bad call!"), "RPT1"),
])
def test_digital_validation(patch, needle):
    s = full()
    patch(s)
    assert any(needle in str(i) for i in V.errors(V.validate(s))), [str(i) for i in V.errors(V.validate(s))]


def test_tdma_direct_flag_and_duplex_warning():
    s = full()
    b = C.encode(s)
    assert C.decode(b).channels[4].tdma_direct
    s.channels[4].talkaround = False
    assert any("TDMA direct" in i.msg for i in V.validate(s))
