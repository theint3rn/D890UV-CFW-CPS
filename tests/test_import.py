import os
import struct

import pytest

from cps import import_rdt, import_csv, import_nand, codeplug as C, validate as V
from conftest import RDT, WRITES

# a real D878UV CPS codeplug (V1270) is not shipped: $CFW_CPS_D878_RDT or $CFW_CPS_PRIVATE/d878.rdt (conftest.py)
need_rdt = pytest.mark.skipif(not os.path.exists(RDT), reason="D878UV .rdt not present ($CFW_CPS_D878_RDT)")


@pytest.fixture(scope="module")
def d878():
    return import_rdt.import_rdt(RDT)


@need_rdt
def test_d878_counts(d878):
    cp, rep = d878
    assert cp.channels and cp.zones and cp.contacts
    assert "channels" in " ".join(rep)


@need_rdt
def test_d878_content(d878):
    cp, _ = d878
    assert all(c.mode in ("FM", "DMR") and c.name for c in cp.channels)
    fm = [c for c in cp.channels if c.mode == "FM"]
    assert all(c.rx_tone in (None,) or c.rx_tone[0] in "0123456789D" for c in fm)
    for d in (c for c in cp.channels if c.mode == "DMR"):
        assert 0 <= d.cc <= 15 and d.slot in (1, 2) and (d.contact is None or cp.contacts[d.contact].id == d.tg)
    for z in cp.zones:
        assert all(0 <= i < len(cp.channels) for i in z.channels)
    for s in cp.scanlists:
        assert all(0 <= i < len(cp.channels) for i in s.channels)
    for t in cp.tglists:
        assert all(0 <= i < len(cp.contacts) for i in t.contacts)


@need_rdt
def test_d878_valid_and_fits(d878):
    cp, _ = d878
    assert V.errors(V.validate(cp)) == []
    b = C.encode(cp)
    assert len(b) <= C.REGION_SIZE and C.decode(b) == cp


@need_rdt
@pytest.mark.skipif(not os.path.exists(WRITES), reason="stock CPS capture not present")
def test_d878_matches_stock_cps_image(d878):
    """The stock D890UV CPS converted the same .rdt into its memory image: channels must agree."""
    cp, _ = d878
    img, _ = import_nand.import_nand(WRITES)
    assert len(img.channels) == len(cp.channels)
    for a, b in zip(cp.channels, img.channels):
        assert (a.name, a.rx_hz, a.tx_hz, a.mode) == (b.name, b.rx_hz, b.tx_hz, b.mode)
        if a.mode == "DMR":
            assert (a.cc, a.slot) == (b.cc, b.slot)
        else:
            assert (a.wide, a.rx_tone, a.tx_tone) == (b.wide, b.rx_tone, b.tx_tone)


def test_rdt_rejects_other_files(tmp_path):
    p = tmp_path / "x.rdt"
    p.write_bytes(b"\0" * 1000)
    with pytest.raises(import_rdt.RdtError):
        import_rdt.import_rdt(str(p))


def test_chirp_csv(tmp_path):
    p = tmp_path / "chirp.csv"
    p.write_text("Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,TStep,Skip\n"
                 "0,RPT 1,146.970000,-,0.600000,Tone,103.5,88.5,023,NN,FM,5.00,\n"
                 "1,TSQ,446.500000,,0.000000,TSQL,88.5,123.0,023,NN,NFM,5.00,S\n"
                 "2,DCS,147.000000,+,0.600000,DTCS,88.5,88.5,754,NR,FM,5.00,\n"
                 "3,AIR,121.500000,,0.000000,,88.5,88.5,023,NN,AM,5.00,\n")
    cp, line = import_csv.import_csv(str(p))
    assert len(cp.channels) == 3 and "chirp" in line
    a, b, c = cp.channels
    assert (a.rx_hz, a.tx_hz, a.tx_tone, a.rx_tone, a.wide) == (146970000, 146370000, "103.5", None, True)
    assert (b.rx_tone, b.tx_tone, b.wide, b.scan_skip) == ("123.0", "123.0", False, True)
    assert (c.tx_hz, c.tx_tone, c.rx_tone) == (147600000, "D754N", "D754I")
    assert V.errors(V.validate(cp)) == []


def test_cfw_csv_round_trip(tmp_path):
    from test_codeplug import sample
    cp = sample()
    p = tmp_path / "c.csv"
    p.write_text(import_csv.export_csv(cp))
    cp2, _ = import_csv.import_csv(str(p))
    for a, b in zip(cp.channels, cp2.channels):
        assert (a.name, a.rx_hz, a.tx_hz, a.mode, a.tg, a.nac, a.ran, a.dgid, a.ur, a.slot, a.rx_tone) == \
            (b.name, b.rx_hz, b.tx_hz, b.mode, b.tg, b.nac, b.ran, b.dgid, b.ur, b.slot, b.rx_tone)
    assert [z.name for z in cp2.zones] == ["All", "Digital"]
