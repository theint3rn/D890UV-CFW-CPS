"""Synthetic codeplug with the .rdt-only dialogs filled in (tests/test_dialogs.py, tests/make_vectors.py); made-up data."""
from cps import codeplug as C, stock as ST
from conftest import SYNTH


def sample(model):
    cp = C.load(SYNTH if model == "D890UV" else SYNTH.replace("synth.d8cp", "synth_d168.d8cp"))
    ST.use(model)
    vals = {
        "AlarmSetting": {"AlarmAEmergency": "2", "AlarmACycle": "3", "AlarmAChannel": "5", "AlarmDTime": "33", "AlarmDId": "9990101",
                         "AlarmDCallType": "1", "AlarmQPrivate": "1A2B", "AlarmWMode": "1", "AlarmDReceive": "1"},
        "DTMFSetting": {"DtmfSelfId": "123", "DtmfBot": "12A", "DtmfEot": "#7", "DtmfKill": "99", "DtmfSideTone": "1", "DtmfTxTime": "3"},
        "T2Setting": {"T2First": "7", "T2Gap": "2"},
        "T5Setting": {"T5SelfId": "12345", "T5BotId": "13", "T5BotTime": "90", "T5EotId": "246", "T5Units": "3", "T5DispAny": "1"},
        "TalkAlias": {"AliasPrio": "1"},
    }
    if model == "D168UV":
        vals["TalkAlias"]["AliasType"] = "1"
        vals["AlarmSetting"].update({"AlarmSigType": "2", "AlarmQGroup": "0C4"})
    for t, d in vals.items():
        for k, v in d.items():
            ST.set_stock_value(cp, t, k, v)
    cp.stock["T5InfoCodes"] = [["1", "0", "0", "55"], ["2", "2", "1", "66"]]
    cp.stock["FriendsList"] = [["1", "9990101"], ["2", "9990103"]]
    if model == "D168UV":
        cp.stock["EncryptionCodeRdt"] = [["1", "1234", "65535"], ["5", "BEEF", "65535"]]
    cp.normalize()
    return cp
