import json
import struct
import zlib

import pytest

from cps import codeplug as C, validate as V, diff as D


def sample():
    cp = C.new_codeplug()
    cp.settings.callsign = "N0CALL"
    cp.settings.dmr_id = 9990001
    cp.contacts = [C.Contact("TG91", 91), C.Contact("Local", 2), C.Contact("P25 TG100", 100, mode="P25"),
                   C.Contact("Me", 9990001, kind="private")]
    cp.tglists = [C.TgList("Main", [0, 1])]
    cp.trunksys = [C.TrunkSystem("Metro P25", "P25", 0x293, 0xBEE00, 0x3C1, 0, [460500000, 460525000]),
                   C.TrunkSystem("T3 site", "DMR_T3", 1, control_channels=[439500000], chan_step_hz=12500)]
    cp.channels += [
        C.Channel(name="RPT", rx_hz=146970000, tx_hz=146370000, mode="FM", wide=True, rx_tone="103.5", tx_tone="D023N"),
        C.Channel(name="DMR TG91", rx_hz=440512500, tx_hz=445512500, mode="DMR", cc=1, slot=2, tg=91, contact=0, tglist=0),
        C.Channel(name="T3 CC", rx_hz=439500000, tx_hz=434500000, mode="DMR", cc=1, tg=91, trunk=True, trunksys=1),
        C.Channel(name="P25 trunk", rx_hz=460500000, tx_hz=465500000, mode="P25", nac=0x293, tg=100, trunk=True, trunksys=0),
        C.Channel(name="P25 PH2", rx_hz=460550000, tx_hz=465550000, mode="P25P2", nac=0x293, slot=1, wacn=0xBEE00, sysid=0x3C1),
        C.Channel(name="NXDN", rx_hz=441250000, tx_hz=441250000, mode="NXDN", ran=1, tg=300),
        C.Channel(name="DSTAR", rx_hz=145670000, tx_hz=145670000, mode="DSTAR", ur="CQCQCQ", rpt1="XX0RPT B", rpt2="XX0RPT G"),
        C.Channel(name="YSF", rx_hz=145375000, tx_hz=0, mode="YSF", dgid=20, power="low"),
    ]
    cp.zones = [C.Zone("All", list(range(len(cp.channels)))), C.Zone("Digital", [3, 4, 5])]
    cp.scanlists = [C.ScanList("FM", [0, 1, 2], prio1=2)]
    cp.channels[0].scanlist = 0
    return cp.normalize()


def test_binary_round_trip():
    cp = sample()
    b = C.encode(cp)
    assert b[:4] == b"D8CP" and len(b) % 16 == 0
    cp2 = C.decode(b)
    assert cp2 == cp
    assert C.encode(cp2) == b


def test_header_layout_matches_firmware():
    b = C.encode(sample())
    ver, hs, total, crc = struct.unpack_from("<HHII", b, 4)
    assert (ver, hs, total) == (1, 32, len(b))
    assert zlib.crc32(b[16:]) & 0xFFFFFFFF == crc
    nsec = struct.unpack_from("<H", b, 16)[0]
    secs = {struct.unpack_from("<HHIII", b, 32 + 16 * i)[0]: struct.unpack_from("<HHIII", b, 32 + 16 * i) for i in range(nsec)}
    assert secs[C.SEC_CHANNELS][1] == 64 and secs[C.SEC_SETTINGS][1] == 128 and secs[C.SEC_TRUNKSYS][1] == 48
    for sid, rs, cnt, off, _ in secs.values():
        assert off % 4 == 0 and off + rs * cnt <= total
    # channel record: name at 0, rx at 16, mode at 24, DMR tg at 32+4 (cfwcp.h union)
    off = secs[C.SEC_CHANNELS][3]
    r = b[off + 64 * 3: off + 64 * 4]
    assert r[:8] == b"DMR TG91" and struct.unpack_from("<I", r, 16)[0] == 440512500 and r[24] == 1
    assert r[32:34] == bytes([1, 2]) and struct.unpack_from("<I", r, 36)[0] == 91


def test_crc_and_magic_checked():
    b = bytearray(C.encode(sample()))
    b[200] ^= 1
    with pytest.raises(C.CodeplugError):
        C.decode(bytes(b))
    with pytest.raises(C.CodeplugError):
        C.decode(b"XXXX" + bytes(b[4:]))


def test_json_round_trip_and_yaml():
    cp = sample()
    d = json.loads(C.dumps_json(cp))
    assert d["channels"][4]["mode"] == "DMR" and "nac" not in d["channels"][4]
    assert C.from_dict(d) == cp
    yaml = pytest.importorskip("yaml")
    assert C.from_dict(yaml.safe_load(C.dumps_yaml(cp))) == cp


def test_tones():
    for t in ("88.5", "254.1", "D023N", "D754I"):
        assert C.tone_decode(C.tone_encode(t)) == t
    assert C.tone_encode(None) == 0


def test_validate_clean_sample():
    assert V.errors(V.validate(sample())) == []


@pytest.mark.parametrize("patch,needle", [
    (lambda c: setattr(c.channels[0], "rx_hz", 300000000), "outside"),
    (lambda c: setattr(c.channels[3], "cc", 16), "colour code"),
    (lambda c: setattr(c.channels[3], "slot", 3), "time slot"),
    (lambda c: setattr(c.channels[6], "nac", 0x1000), "NAC"),
    (lambda c: setattr(c.channels[3], "contact", 99), "contact 99"),
    (lambda c: setattr(c.channels[5], "trunksys", 1), "is DMR_T3"),
    (lambda c: setattr(c.channels[8], "ur", "toolongcall"), "UR"),
    (lambda c: setattr(c.channels[9], "dgid", 120), "DG-ID"),
    (lambda c: setattr(c.channels[7], "ran", 64), "RAN"),
    (lambda c: c.zones[0].channels.append(500), "member channel"),
    (lambda c: setattr(c.channels[3], "wide", True), "FM only"),
    (lambda c: setattr(c.channels[3], "rx_tone", "88.5"), "only on FM"),
    (lambda c: setattr(c.channels[0], "trunk", True), "trunk"),
    (lambda c: setattr(c.trunksys[0], "control_channels", []), "no control channel"),
    (lambda c: setattr(c.settings, "dmr_id", 99999999), "DMR ID"),
])
def test_validate_catches(patch, needle):
    cp = sample()
    patch(cp)
    msgs = [str(i) for i in V.errors(V.validate(cp))]
    assert any(needle in m for m in msgs), msgs


def test_size_limit():
    cp = sample()
    cp.channels = [C.Channel(name="X%d" % i) for i in range(6500)]
    with pytest.raises(C.CodeplugError):
        C.encode(cp)
    assert any("size" == i.where for i in V.errors(V.validate(cp)))


def test_diff():
    a = sample()
    b = sample()
    b.channels[1].rx_hz = 146530000
    b.channels.append(C.Channel(name="NEW"))
    b.settings.dmr_id = 1
    lines = D.diff(a, b)
    assert any(l.startswith("~ channel 2") and "146.53000" in l for l in lines)
    assert any(l.startswith("+ channel") and "NEW" in l for l in lines)
    assert any(l.startswith("settings.dmr_id") for l in lines)
    assert D.diff(a, sample()) == []
