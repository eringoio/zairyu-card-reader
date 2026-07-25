from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

ZERO_AES_IV = b"\x00" * 16


class Rc2CryptoError(ValueError):
    pass


@dataclass(frozen=True)
class Rc2BaseKeys:
    kenc: bytes
    kmac: bytes


@dataclass(frozen=True)
class Rc2MutualAuthResult:
    rnd_icc: bytes
    rnd_ifd: bytes
    k_icc: bytes
    ksenc: bytes


def normalize_card_number(card_number: str) -> bytes:
    normalized = card_number.strip().upper().encode("ascii")
    if len(normalized) != 12:
        raise Rc2CryptoError("Residence-card number must be exactly 12 ASCII bytes.")
    return normalized


def derive_base_keys(card_number: str) -> Rc2BaseKeys:
    # SHA-1 is not a choice here. The residence-card specification defines base-key
    # derivation as SHA-1 over the 12-byte card number truncated to 16 bytes, and a card
    # will not authenticate against anything else. It derives a session key from a value
    # the operator is already physically holding; it is never used for authenticity
    # verification, which is SHA-256 with RSA-2048 or ECDSA P-384.
    key = sha1(normalize_card_number(card_number)).digest()[:16]  # noqa: S324
    return Rc2BaseKeys(kenc=key, kmac=key)


def aes_cbc_encrypt(key: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise Rc2CryptoError("AES-128 key must be 16 bytes.")
    if len(data) % 16:
        raise Rc2CryptoError("AES-CBC input must be a multiple of 16 bytes.")

    from Crypto.Cipher import AES

    return AES.new(key, AES.MODE_CBC, iv=ZERO_AES_IV).encrypt(data)


def aes_cbc_decrypt(key: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise Rc2CryptoError("AES-128 key must be 16 bytes.")
    if len(data) % 16:
        raise Rc2CryptoError("AES-CBC input must be a multiple of 16 bytes.")

    from Crypto.Cipher import AES

    return AES.new(key, AES.MODE_CBC, iv=ZERO_AES_IV).decrypt(data)


def aes_cmac(key: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise Rc2CryptoError("AES-CMAC key must be 16 bytes.")

    from Crypto.Cipher import AES
    from Crypto.Hash import CMAC

    mac = CMAC.new(key, ciphermod=AES)
    mac.update(data)
    return mac.digest()


def truncated_aes_cmac(key: bytes, data: bytes) -> bytes:
    return aes_cmac(key, data)[:8]


def build_e_ifd(kenc: bytes, rnd_ifd: bytes, rnd_icc: bytes, k_ifd: bytes) -> bytes:
    if len(rnd_ifd) != 8 or len(rnd_icc) != 8 or len(k_ifd) != 16:
        raise Rc2CryptoError("RND.IFD, RND.ICC, and K.IFD must be 8, 8, and 16 bytes.")
    return aes_cbc_encrypt(kenc, rnd_ifd + rnd_icc + k_ifd)


def build_m_ifd(kmac: bytes, e_ifd: bytes) -> bytes:
    if len(e_ifd) != 32:
        raise Rc2CryptoError("E_IFD must be 32 bytes.")
    return truncated_aes_cmac(kmac, e_ifd)


def build_mutual_authenticate_command(e_ifd: bytes, m_ifd: bytes) -> list[int]:
    if len(e_ifd) != 32 or len(m_ifd) != 8:
        raise Rc2CryptoError("MUTUAL AUTHENTICATE requires 32-byte E_IFD and 8-byte M_IFD.")
    return [0x00, 0x82, 0x00, 0x00, 0x28, *e_ifd, *m_ifd, 0x00]


def verify_m_icc(kmac: bytes, e_icc: bytes, m_icc: bytes) -> bool:
    if len(e_icc) != 32 or len(m_icc) != 8:
        raise Rc2CryptoError("Card mutual-auth response must contain 32-byte E_ICC and 8-byte M_ICC.")
    return truncated_aes_cmac(kmac, e_icc) == m_icc


def derive_ksenc(k_ifd: bytes, k_icc: bytes) -> bytes:
    if len(k_ifd) != 16 or len(k_icc) != 16:
        raise Rc2CryptoError("K.IFD and K.ICC must be 16 bytes.")
    seed = bytes(left ^ right for left, right in zip(k_ifd, k_icc, strict=True))
    # Specification-mandated session-key derivation; see `derive_base_keys`.
    return sha1(seed + bytes.fromhex("00000001")).digest()[:16]  # noqa: S324


def decrypt_e_icc(
    kenc: bytes,
    e_icc: bytes,
    expected_rnd_icc: bytes,
    expected_rnd_ifd: bytes,
    k_ifd: bytes,
) -> Rc2MutualAuthResult:
    decrypted = aes_cbc_decrypt(kenc, e_icc)
    if len(decrypted) != 32:
        raise Rc2CryptoError("Decrypted E_ICC must be 32 bytes.")
    rnd_icc = decrypted[:8]
    rnd_ifd = decrypted[8:16]
    k_icc = decrypted[16:]
    if rnd_icc != expected_rnd_icc:
        raise Rc2CryptoError("Card RND.ICC did not match the GET CHALLENGE value.")
    if rnd_ifd != expected_rnd_ifd:
        raise Rc2CryptoError("Card RND.IFD did not match the terminal challenge.")
    return Rc2MutualAuthResult(
        rnd_icc=rnd_icc,
        rnd_ifd=rnd_ifd,
        k_icc=k_icc,
        ksenc=derive_ksenc(k_ifd, k_icc),
    )


def pad_iso7816(data: bytes, block_size: int = 16) -> bytes:
    if block_size <= 0:
        raise Rc2CryptoError("Block size must be positive.")
    padded = data + b"\x80"
    while len(padded) % block_size:
        padded += b"\x00"
    return padded


def remove_iso7816_padding(data: bytes) -> bytes:
    index = len(data) - 1
    while index >= 0 and data[index] == 0x00:
        index -= 1
    if index < 0 or data[index] != 0x80:
        raise Rc2CryptoError("Invalid ISO/IEC 7816 padding.")
    return data[:index]


def encrypt_verify_payload(ksenc: bytes, card_number: str) -> bytes:
    return aes_cbc_encrypt(ksenc, pad_iso7816(normalize_card_number(card_number), block_size=16))


def build_verify_command(encrypted_card_number: bytes) -> list[int]:
    if len(encrypted_card_number) != 16:
        raise Rc2CryptoError("Encrypted VERIFY payload must be 16 bytes.")
    return [0x08, 0x20, 0x00, 0x86, 0x13, 0x86, 0x11, 0x01, *encrypted_card_number]


def decrypt_sm_response_payload(ksenc: bytes, encrypted_data: bytes) -> bytes:
    return remove_iso7816_padding(aes_cbc_decrypt(ksenc, encrypted_data))
