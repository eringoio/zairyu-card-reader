from __future__ import annotations

import builtins

from reader.parsing.second_generation_fields import (
    interpret_period_of_stay,
    interpret_period_of_stay_en,
    interpret_period_of_stay_ja,
    map_nationality_code,
    map_residence_status_code,
    parse_rc2_business_fields,
    parse_signature_metadata,
)


def _tlv(tag: str, value: bytes) -> bytes:
    if len(value) < 0x80:
        length = bytes([len(value)])
    elif len(value) <= 0xFF:
        length = bytes([0x81, len(value)])
    else:
        length = bytes([0x82, (len(value) >> 8) & 0xFF, len(value) & 0xFF])
    return bytes.fromhex(tag) + length + value


def test_parse_rc2_residence_card_business_fields() -> None:
    printed = b"".join(
        [
            _tlv("C5", b"20310401"),
            _tlv("C6", b"20000102"),
            _tlv("C7", b"1"),
            _tlv("C8", b"392"),
            _tlv("C9", b"SAMPLE"),
            _tlv("CE", b"0200"),
            _tlv("CA", b"01"),
            _tlv("CB", b"20260401"),
            _tlv("CC", b"9"),
            _tlv("CD", b"20280401"),
        ]
    )
    df2_ef01 = b"".join([_tlv("D5", b"1"), _tlv("D6", b"20270401"), _tlv("D7", b"0")])
    df2_ef02 = _tlv("D8", b"1")
    df2_ef03 = b"".join([_tlv("D9", b"1"), _tlv("DE", "合成メモ".encode())])
    signature = _tlv("DC", b"s" * 96) + _tlv("DD", b"c" * 598)

    fields = parse_rc2_business_fields(
        "05",
        {
            "DF1/EF02": printed,
            "DF2/EF01": df2_ef01,
            "DF2/EF02": df2_ef02,
            "DF2/EF03": df2_ef03,
            "DF3/EF01": signature,
        },
    )

    assert fields["card_expiry_date"] == "2031-04-01"
    assert fields["birth_date"] == "2000-01-02"
    assert fields["sex_code"] == "1"
    assert fields["sex_label"] == "男"
    assert fields["work_restriction_code"] == "9"
    assert fields["work_restriction_label"] == "就労不可"
    assert fields["renewal_application_status"] == "申請中"
    assert fields["isa_commissioner_note_code"] == "1"
    assert fields["isa_commissioner_note_label"] == "記録あり"
    assert fields["reserved_note_text"] == "合成メモ"
    assert "isa_commissioner_note" not in fields
    assert fields["signature_present"] is True
    assert fields["public_key_certificate_status"] == "present"
    # The synthetic DD blob is present but cannot be parsed as a valid certificate, so it is reported as invalid.
    assert fields["signature_verified"] is None
    assert fields["signature_verification_status"] == "certificate_invalid"
    assert fields["period_of_stay_label"] == "2年"
    assert fields["residence_status_label"] == "Unmapped residence status code: SAMPLE"


def test_parse_rc2_special_permanent_resident_business_fields() -> None:
    printed = b"".join(
        [
            _tlv("C5", b"20310401"),
            _tlv("C6", b"19991231"),
            _tlv("C7", b"2"),
            _tlv("C8", b"999"),
        ]
    )
    df2_ef01 = b"".join([_tlv("D9", b"0"), _tlv("DE", "合成".encode())])

    fields = parse_rc2_business_fields("06", {"DF1/EF02": printed, "DF2/EF01": df2_ef01})

    assert fields["birth_date"] == "1999-12-31"
    assert fields["sex_label"] == "女"
    assert fields["isa_commissioner_note_code"] == "0"
    assert fields["isa_commissioner_note_label"] == "なし"
    assert fields["reserved_note_text"] == "合成"


def test_rc2_code_interpretation_helpers() -> None:
    assert map_nationality_code("PAK") == "パキスタン"
    assert map_nationality_code("NLD") == "オランダ"
    assert map_nationality_code("JPN") == "日本"
    assert map_nationality_code("XXX") == "無国籍"
    assert map_nationality_code("ZZZ") == "Unmapped nationality/region code: ZZZ"
    assert map_residence_status_code("T410010000") == "Unmapped residence status code: T410010000"


def test_period_of_stay_defaults_to_japanese_staff_labels() -> None:
    assert interpret_period_of_stay("0010") == "10月"
    assert interpret_period_of_stay("0000") == "無期限"
    assert interpret_period_of_stay("0103") == "1年3月"
    assert interpret_period_of_stay("0200") == "2年"
    assert interpret_period_of_stay("0006") == "6月"
    assert interpret_period_of_stay("090") == "90日"
    assert interpret_period_of_stay("015") == "15日"
    assert interpret_period_of_stay("") == ""
    assert interpret_period_of_stay("XX") == "未対応の在留期間コード: XX"


def test_period_of_stay_indefinite_is_never_rendered_as_zero_months() -> None:
    assert interpret_period_of_stay_ja("0000") == "無期限"
    assert interpret_period_of_stay_en("0000") == "Indefinite"
    assert "0月" not in interpret_period_of_stay_ja("0000")
    assert "0 month" not in interpret_period_of_stay_en("0000")


def test_period_of_stay_english_formatter_is_available_for_diagnostics() -> None:
    assert interpret_period_of_stay_en("0010") == "10 months"
    assert interpret_period_of_stay_en("0103") == "1 year 3 months"
    assert interpret_period_of_stay_en("0100") == "1 year"
    assert interpret_period_of_stay_en("090") == "90 days"
    assert interpret_period_of_stay_en("001") == "1 day"
    assert interpret_period_of_stay_en("ZZ") == "Unmapped period code: ZZ"
    assert interpret_period_of_stay("0010", locale="en") == "10 months"
    assert interpret_period_of_stay("0010", locale="ja") == "10月"


def test_signature_metadata_degrades_when_cryptography_is_missing(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "reader.signature.rc_signature":
            raise ModuleNotFoundError("No module named 'cryptography'", name="cryptography")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    metadata = parse_signature_metadata(_tlv("DC", b"s" * 96) + _tlv("DD", b"c" * 598))

    assert metadata["signature_present"] is True
    assert metadata["public_key_certificate_status"] == "present"
    assert metadata["public_key_certificate_parse_status"] == "not_attempted_missing_dependency"
    assert metadata["certificate_chain_verified"] is None
