# Source materials and checksums

Original checksum register generated 2026-07-07.

## Specification PDFs — cited, not redistributed

The specification documents below are published by the Immigration Services Agency of
Japan. **This repository does not redistribute them.** The documentation cites them by
document number, version, page, and section, which is enough to follow any derivation in
`docs/specs/moj/` against the original.

The SHA-256 of each document as used during implementation is recorded so you can confirm
you are reading the same revision the code was written against. Obtain the documents from
the Immigration Services Agency and verify the digest before relying on a citation.

| Document | Description | SHA-256 of the revision used |
|---|---|---|
| `001414093.pdf` | First-generation/current residence-card spec, Ver 1.5 | `e529e43284abc9d4400538125a91084d46c0d3601234a113abe529261b417352` |
| `001460711.pdf` | Normal second-generation residence-card spec, Ver 1.1 | `0221c0770e5ed0f04fe2a7ccb1e564e0c7e687ad97aec4e55008db0164fc8fe8` |
| `001460712.pdf` | Specified-card spec, Ver 1.1, reference only | `65eea1748432b369286196493ca713b7424bff00a7202bbef30e56a428167f59` |
| `001460713.pdf` | Normal second-generation diff table | `4ef3e2ed73ea8a3521f7c99752a87bfde9547423a81e612203813572b85da3f8` |
| `001460714.pdf` | Specified-card diff table | `aacc47a0be8120edffe07968ebe46a4c7bd3ba83b24bb657507f32a9d14eb20c` |

The last two were never present in this repository even before the PDFs were removed; they
are listed for completeness of the register.

## Official source pages

| Generation | Page |
|---|---|
| First generation | <https://www.moj.go.jp/isa/applications/disclosure/120424_01.html> |
| Second generation and specified cards | <https://www.moj.go.jp/isa/publications/resources/120424_01_00003.html> |

Both pages state that copyright in the published specifications is protected, while
expressly not preventing software developers from building and distributing software based
on them. See [../../official-certificates.md](../../official-certificates.md) for how that
shapes what this repository includes.

## Certificate source files

Every file listed as included is present under `docs/external/moj/certs/` and has been
verified byte-for-byte against the corresponding runtime certificate.

| File | Description | Included | SHA-256 |
|---|---|---|---|
| `001460774.zip` | First-generation public CA certificate ZIP (2015) | yes | `5cde542204153e33b866c95a83a311939ada320e3e0534f039cd2c8663731e89` |
| `001460775.zip` | First-generation public CA certificate ZIP (2018) | yes | `7651df34bb28288e7cad6fd5ad1c4ffa9588455fbd523c77a2478650be17f6bd` |
| `001460776.zip` | First-generation public CA certificate ZIP (2021) | yes | `2d6cc2e9aac1ce086007843c9f6da3e3f17949a1cd0ba2c3df2813ff593ea2e5` |
| `001460777.zip` | First-generation public CA certificate ZIP (2024) | yes | `4306634f38c52ef8433ec6ec3ba287706949b15735b40552234a2051c40e3977` |
| `001462221.zip` | Second-generation CA2 certificate ZIP | yes | `fed0160250a0e95377a55868431397b47ebf97ba77d0dd33aeadc4484a230f15` |
| `001460788.zip` | Official second-generation test CA ZIP | yes | `900436c0eae20770f4b23b7f8b78ee88e0bdd93a7077db0c87eca3400181d000` |
| `930001756.crt` | First-generation CA, direct download (2015) | yes | `97f37c5967af5f3cd84e6ed694b09539abb7f8e7e76b6f7496a060008982983d` |
| `930001757.crt` | First-generation CA, direct download (2018) | yes | `ff02323cea7b8c3dfc0dc2de79d46e78514af587368523086b188e9690aec861` |
| `001353372.crt` | First-generation CA, direct download (2021) | yes | `6f50161aa80f7ff7c630505faf472906f7b101d5083e327a6182c82cd7985e67` |
| `001421582.crt` | First-generation CA, direct download (2024) | yes | `bf854466ed9abf61f559c39bf8790546f8acdab99b51fd2330563669ce4a71b2` |
| `001462222.zip` | Specified-card RSA delivery key ZIP | **no** | `05a19a2d2685a25a889f1289532734127d16037519ddf8a6d9e4ed393a221d8b` |
| `001460789.zip` | Official test RSA delivery key ZIP | **no** | not recorded; never obtained |

## Extracted runtime files

| File | Description | SHA-256 |
|---|---|---|
| `zairyucard_ca_20240508_20340808.crt` | First-generation CA certificate | `bf854466ed9abf61f559c39bf8790546f8acdab99b51fd2330563669ce4a71b2` |
| `zairyucard_ca2_20260420_20390720.crt` | Second-generation CA2 certificate | `11e6ad8b8e64f0cdb1d8ba9e3689926c80e8479a2f098616f674a23582bec13b` |

The specified-card RSA delivery public key `keys_smrsapub_001.bin` (SHA-256
`98bf7014e478241f7943fc1a76c38b6c7bda4da9a927d106ae9ab8a1ad684d0a`) is **not** an extracted
runtime file and is not distributed with this project. Its digest is recorded so the
omission is verifiable.

## First-generation verification references

`001414093.pdf` is the authoritative old-generation format used by
`reader/signature/first_generation.py`: §§3.3.4.3-3.3.4.4 (D0/D1 values and fixed maximum
lengths, p. 10), §3.3.4.9 (DA check code and DB certificate, p. 13), and §3.4.3.1 / Figure
3-4 (SHA-256, RSA-2048 PKCS#1 v1.5, and the D0-value-plus-D1-value signed target, p. 14).
The DF/SFI reading sequence is §4.2.5 and the appendix sequence (pp. 32, 40).

## Certificate source register (trust-profile implementation)

All certificate bytes are packaged only after local SHA-256 verification. The application
does not retrieve these URLs or any other remote material at runtime.

| Profile | Generation | Official archive | Historical direct file | Runtime certificate | SHA-256 fingerprint | Verification |
|---|---|---|---|---|---|---|
| production | first | `001460774.zip` | `930001756.crt` | `zairyucard_ca_20150606_20250906.crt` | `97:F3:7C:59:67:AF:5F:3C:D8:4E:6E:D6:94:B0:95:39:AB:B7:F8:E7:E7:6B:6F:74:96:A0:60:00:89:82:98:3D` | archive/direct DER bytes match |
| production | first | `001460775.zip` | `930001757.crt` | `zairyucard_ca_20180407_20280707.crt` | `FF:02:32:3C:EA:7B:8C:3D:FC:0D:C2:DE:79:D4:6E:78:51:4A:F5:87:36:85:23:08:6B:18:8E:96:90:AE:C8:61` | archive/direct DER bytes match |
| production | first | `001460776.zip` | `001353372.crt` | `zairyucard_ca_20210527_20310827.crt` | `6F:50:16:1A:A8:0F:7F:F7:C6:30:50:5F:AF:47:29:06:F7:B1:01:D5:08:3E:32:7A:61:82:C8:2C:D7:98:5E:67` | archive/direct DER bytes match |
| production | first | `001460777.zip` | `001421582.crt` | `zairyucard_ca_20240508_20340808.crt` | `BF:85:44:66:ED:9A:BF:61:F5:59:C3:9B:F8:79:05:46:F8:AC:DA:B9:9B:51:FD:23:30:56:36:69:CE:4A:71:B2` | archive/direct DER bytes match |
| production | second | `001462221.zip` | — | `zairyucard_ca2_20260420_20390720.crt` | `11:E6:AD:8B:8E:64:F0:CD:B1:D8:BA:9E:36:89:92:6C:80:E8:47:9A:2F:09:86:16:F6:74:A2:35:82:BE:C1:3B` | official archive DER extracted |
| official_test | second | `001460788.zip` | — | `zairyucard_ca2_test_20260319_20390619.crt` | `18:46:B8:15:D3:1F:04:FE:93:D5:74:50:A6:D8:A8:C3:51:EA:C3:D8:C4:44:A2:37:5D:95:73:4D:F7:DD:10:57` | official archive DER extracted on 2026-07-17 |

The related delivery-key archives `001460789.zip` (official test) and `001462222.zip`
(production) are source-register entries only. Their RSA keys apply to specified cards, not
normal `05`/`06` cards, are not trust anchors, and **neither archive is distributed with
this project**. They are listed so a reader can confirm the omission is deliberate.

| Official source ID | Material | Status in this project |
|---|---|---|
| `001460789.zip` | Official test RSA delivery key | Not included, not downloaded, not loaded; specified-card-only material. |
| `001462222.zip` | Production RSA delivery key | Not included, not downloaded, not loaded; never a trust anchor and never used for `05`/`06`. |
