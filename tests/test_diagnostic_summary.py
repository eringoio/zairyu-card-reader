from __future__ import annotations

from reader.residence_card_reader import _build_local_diagnostic_summary, _build_structure_summary


def test_local_diagnostic_summary_lists_readable_text_without_raw_dump() -> None:
    summary = _build_local_diagnostic_summary(
        {
            "scan_method": "real_partial",
            "chip_version": "0001",
            "card_type": "在留カード",
            "residence_update_status": "無し",
            "address": "",
            "address_write_date": "",
            "municipality_code": "",
            "part_time_permission": "",
            "front_side_extraction": "not_available_without_image_read_and_ocr",
            "front_image_status": "available_on_card_but_not_read_without_explicit_image_mode",
            "face_photo_status": "available_on_card_but_not_read_or_stored_in_this_prototype",
            "read_note": "test note",
        }
    )

    assert "Structured text read from chip" in summary
    assert "image-based on this card generation" in summary
    assert "raw" not in summary.lower()


def test_structure_summary_omits_values_and_lists_tags() -> None:
    summary = _build_structure_summary(
        [
            {
                "file": "DF2/EF01 address",
                "sfi": "81",
                "expected_length": 342,
                "tags": [{"tag": "D4", "length": 0, "present": False, "decoded_text_present": False}],
            }
        ]
    )

    assert "DF2/EF01 address" in summary
    assert "tag D4: length 0" in summary
    assert "decoded text blank after trimming padding" in summary
    assert "omits raw bytes and personal values" in summary
