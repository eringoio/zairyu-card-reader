from __future__ import annotations

from reader.crypto.rc2 import (
    build_e_ifd,
    build_m_ifd,
    build_mutual_authenticate_command,
    build_verify_command,
    decrypt_e_icc,
    derive_base_keys,
    derive_ksenc,
    encrypt_verify_payload,
    verify_m_icc,
)

CARD_NUMBER = "AA12345678BB"
CARD_NUMBER_SHA1 = bytes.fromhex("65 22 B4 E1 71 19 5B B2 18 22 3A 97 6C 04 01 11 BD C4 AA 25")
KENC = bytes.fromhex("65 22 B4 E1 71 19 5B B2 18 22 3A 97 6C 04 01 11")
RND_IFD = bytes.fromhex("11 22 33 44 55 66 77 88")
K_IFD = bytes.fromhex("40 41 42 43 44 45 46 47 48 49 4A 4B 4C 4D 4E 4F")
RND_ICC = bytes.fromhex("92 1C E2 77 32 3D A0 57")
E_IFD = bytes.fromhex(
    "4A D3 C7 B6 BB 48 4A 52 77 19 77 DE D6 18 B4 1D"
    "F8 41 FA 04 76 A0 5F BE 04 1D EA D6 10 9E 77 3B"
)
M_IFD = bytes.fromhex("AC 85 46 17 63 4F 53 97")
E_ICC = bytes.fromhex(
    "28 9A 96 B1 DA 6A E3 DA 87 77 04 19 BF D1 4F 0B"
    "DA D1 5F 36 43 2B 5A 94 6C 18 8C 72 21 75 9A 62"
)
M_ICC = bytes.fromhex("FA 94 2E C5 1E 62 FF 5F")
K_ICC = bytes.fromhex("2C C6 AF 9B 8B 60 7C 66 2F DC AD 27 B4 01 D0 8B")
KSENC = bytes.fromhex("C1 9C F1 3D 3D 7F BE E9 EA 29 3D 83 4C 88 95 2F")
VERIFY_ENCRYPTED = bytes.fromhex("EE 0B 31 EF 87 7F 68 D0 71 C5 6D 58 C7 2E 67 48")


def test_derive_base_keys_from_card_number() -> None:
    keys = derive_base_keys(CARD_NUMBER)

    assert keys.kenc == KENC
    assert keys.kmac == KENC


def test_build_e_ifd_vector() -> None:
    assert build_e_ifd(KENC, RND_IFD, RND_ICC, K_IFD) == E_IFD


def test_build_m_ifd_vector() -> None:
    assert build_m_ifd(KENC, E_IFD) == M_IFD


def test_build_mutual_authenticate_command_vector() -> None:
    command = build_mutual_authenticate_command(E_IFD, M_IFD)

    assert bytes(command) == bytes.fromhex(
        "00 82 00 00 28 4A D3 C7 B6 BB 48 4A 52 77 19 77"
        "DE D6 18 B4 1D F8 41 FA 04 76 A0 5F BE 04 1D EA"
        "D6 10 9E 77 3B AC 85 46 17 63 4F 53 97 00"
    )


def test_verify_m_icc_vector() -> None:
    assert verify_m_icc(KENC, E_ICC, M_ICC)


def test_decrypt_e_icc_and_derive_ksenc_vector() -> None:
    result = decrypt_e_icc(KENC, E_ICC, RND_ICC, RND_IFD, K_IFD)

    assert result.rnd_icc == RND_ICC
    assert result.rnd_ifd == RND_IFD
    assert result.k_icc == K_ICC
    assert result.ksenc == KSENC


def test_derive_ksenc_vector() -> None:
    assert derive_ksenc(K_IFD, K_ICC) == KSENC


def test_encrypt_verify_payload_vector() -> None:
    assert encrypt_verify_payload(KSENC, CARD_NUMBER) == VERIFY_ENCRYPTED


def test_build_verify_command_vector() -> None:
    command = build_verify_command(VERIFY_ENCRYPTED)

    assert bytes(command) == bytes.fromhex(
        "08 20 00 86 13 86 11 01 EE 0B 31 EF 87 7F 68 D0"
        "71 C5 6D 58 C7 2E 67 48"
    )
