from __future__ import annotations

DEFAULT_LOCALE = "ja"


def locale_from_accept_language(value: str | None) -> str:
    return "ja" if (value or "").lower().startswith("ja") else "en"


def translate(key: str, locale: str = DEFAULT_LOCALE) -> str:
    labels = {
        "manual_scan.ready": {"ja": "読み取りが完了しました。", "en": "Card reading is complete."},
        "ocr.name.low_confidence": {
            "ja": "氏名OCRの信頼度が低いため、確認してください。",
            "en": "Name OCR confidence is low; please review.",
        },
        "display.name.missing": {"ja": "未取得（OCR確認が必要）", "en": "Not detected; review OCR"},
        # Distinct from `missing`: the recognizer produced nothing, so there is nothing to
        # "review". This application has no field for typing a name, so staff read it from
        # the card and correct it where they paste.
        "display.name.not_read": {"ja": "読み取れませんでした", "en": "Could not be read"},
        "display.sex.male": {"ja": "男性", "en": "Male"}, "display.sex.female": {"ja": "女性", "en": "Female"},
        "display.sex.other": {"ja": "その他", "en": "Other"}, "display.permission.yes": {"ja": "あり", "en": "Permitted"},
        "display.permission.no": {"ja": "なし", "en": "Not permitted"},
        "display.signature.verified_production": {"ja": "真正性確認: 確認済み", "en": "Authenticity: Verified"},
        "display.signature.verified_official_test": {"ja": "真正性確認: 公的テストカードとして確認済み", "en": "Authenticity: Verified as an official test card"},
        "display.signature.untrusted_certificate": {"ja": "真正性確認: 未確認（信頼済み認証局まで確認できません）", "en": "Authenticity: Unconfirmed (untrusted certificate)"},
        "display.signature.ambiguous_trust_path": {"ja": "真正性確認: 未確認（信頼経路が一意ではありません）", "en": "Authenticity: Unconfirmed (ambiguous trust path)"},
        "display.signature.certificate_expired": {"ja": "真正性確認: 未確認（証明書の有効期限を確認してください）", "en": "Authenticity: Unconfirmed (certificate expired)"},
        "display.signature.certificate_not_yet_valid": {"ja": "真正性確認: 未確認（証明書はまだ有効ではありません）", "en": "Authenticity: Unconfirmed (certificate not yet valid)"},
        "display.signature.anchor_fingerprint_mismatch": {"ja": "真正性確認: 未確認（信頼元の整合性確認に失敗）", "en": "Authenticity: Unconfirmed (anchor integrity check failed)"},
        "display.signature.missing_signature": {"ja": "真正性確認: 未確認（署名がありません）", "en": "Authenticity: Unconfirmed (signature missing)"},
        "display.signature.missing_certificate": {"ja": "真正性確認: 未確認（証明書がありません）", "en": "Authenticity: Unconfirmed (certificate missing)"},
        "display.signature.missing_signed_component": {"ja": "真正性確認: 未確認（署名対象が不足）", "en": "Authenticity: Unconfirmed (signed component missing)"},
        "display.signature.signature_mismatch": {"ja": "真正性確認: 未確認（署名が一致しません）", "en": "Authenticity: Unconfirmed (signature mismatch)"},
        "display.signature.certificate_invalid": {"ja": "真正性確認: 未確認（証明書が無効）", "en": "Authenticity: Unconfirmed (certificate invalid)"},
        "display.signature.verification_error": {"ja": "真正性確認: 未確認", "en": "Authenticity: Unconfirmed"},
        "display.signature.verified": {"ja": "真正性確認: 確認済み", "en": "Authenticity: Verified"},
        "display.signature.not_verified": {"ja": "署名検証: 確認できませんでした", "en": "Signature: Not verified"},
        "display.signature.skipped_by_config": {"ja": "署名検証: 未確認（設定によりスキップ）", "en": "Signature: Not checked; skipped by settings"},
        "display.signature.certificate_unavailable": {"ja": "署名検証: 未確認（証明書を確認できません）", "en": "Signature: Not checked; certificate unavailable"},
        "display.signature.unsupported_card_generation": {"ja": "署名検証: 未対応（旧世代カード）", "en": "Signature: Not supported for this card generation"},
    }
    return labels.get(key, {}).get(locale, labels.get(key, {}).get("ja", key))
