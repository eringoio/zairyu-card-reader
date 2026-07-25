import json

from reader.policy import forbidden_keys, key_is_forbidden, sanitize_response


def test_sensitive_material_is_forbidden_recursively():
    assert key_is_forbidden("raw_tlv")
    assert forbidden_keys({"nested": {"face_image_bytes": "x"}}) == ["nested.face_image_bytes"]


def test_sanitizer_removes_sensitive_material_and_keeps_policy_statuses():
    result = sanitize_response({"card_number": "AB12345678AJ", "raw_apdu": "secret"})
    assert "raw_apdu" not in result
    assert result["my_number_status"] == "not_accessed_by_policy"


def test_sanitizer_keeps_safe_front_image_dimensions_only():
    result = sanitize_response(
        {
            "front_image_width": "856",
            "front_image_height": "540",
            "front_image_data_url": "data:image/png;base64,secret",
            "front_ocr_text": "secret OCR text",
        }
    )

    assert result["front_image_width"] == "856"
    assert result["front_image_height"] == "540"
    assert "front_image_data_url" not in result
    assert "front_ocr_text" not in result


def test_sanitizer_reaches_sensitive_keys_nested_inside_lists_and_maps():
    """Sanitisation must not stop at the top level; card material nests in real responses."""
    result = sanitize_response(
        {
            "card_number": "AB12345678AJ",
            "reads": [
                {
                    "stage": "df1",
                    "raw_tlv": "deadbeef",
                    "inner": {"face_photo_bytes": b"jpeg", "signed_target": "x", "card_generation": "2"},
                },
                {"stage": "df3", "certificate_bytes": "der", "signature_bytes": "sig"},
            ],
            "trace": {"steps": [{"apdu_log": ["00A4"], "sw": "9000"}]},
        }
    )

    flattened = json.dumps(result, default=str)
    for leaked in ("deadbeef", "jpeg", "signed_target", "certificate_bytes", "signature_bytes", "apdu_log", "raw_tlv"):
        assert leaked not in flattened, leaked
    # Safe siblings survive at every depth.
    assert result["card_number"] == "AB12345678AJ"
    assert result["reads"][0]["stage"] == "df1"
    assert result["reads"][0]["inner"]["card_generation"] == "2"
    assert result["trace"]["steps"][0]["sw"] == "9000"


def test_forbidden_keys_reports_every_depth_including_list_indices():
    found = forbidden_keys(
        {
            "a": {"raw_apdu": 1},
            "b": [{"my_number": 2}, {"deep": {"jpki": 3}}],
        }
    )
    assert sorted(found) == ["a.raw_apdu", "b[0].my_number", "b[1].deep.jpki"]
