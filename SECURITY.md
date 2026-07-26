# Security Policy

**[日本語版 →](SECURITY.ja.md)**

This application reads personal data from Japanese residence cards. Please treat any
finding that could expose card data, face images, IC-chip material, or the loopback API as
sensitive.

## 日本語の要約

本アプリは在留カードの個人情報を扱います。カード情報、顔画像、ICチップのデータ、または
ローカルAPIの露出につながる問題は、機微な内容として扱ってください。

**脆弱性は公開のIssueに投稿しないでください。** GitHub の非公開の脆弱性報告機能
（Security → Report a vulnerability）をご利用ください。報告には、**実在のカード情報、氏名、
住所、生年月日、在留カード番号を絶対に含めないでください。** テストと同様に合成データを
使用してください。

対象範囲、対象外、および本アプリが防御しないものについては、以下の英語の記載をご覧ください。

## Reporting a vulnerability

**Do not open a public issue** for a vulnerability that could expose card data. Use GitHub's
private vulnerability reporting on this repository ("Security" → "Report a vulnerability").

Please include what you did, what happened, and what you expected. **Never include real
card data, real names, real addresses, or real card numbers in a report** — use synthetic
values, as the tests do. A description of the shape of the data is enough.

There is no funded bug-bounty programme. This is an independently developed tool.

## Scope

In scope:

- anything that lets a party other than the staff member at the keyboard reach the local
  API, read card data, or trigger a card read — for example a bypass of the `Host`
  allowlist, the per-process request token, or the provenance checks;
- any path that writes card material, a card image, raw APDU/TLV data, a face image, or raw
  OCR text to disk, a log, a diagnostic, or an API response;
- any way to make the application perform network I/O at runtime;
- a signature-verification flaw that lets an invalid card report as verified, or lets
  official-test material report as production authenticity;
- a trust-anchor loading flaw that accepts an unverified or substituted certificate.

Out of scope:

- exposure to another process running as the same Windows user. The request token is
  embedded in a page this server serves over loopback; any process with that user's
  privileges can read it. That is inherent to a local service with no user accounts.
- deliberately running the application outside its supported configuration — for example
  patching out the loopback check.
- OCR misreading a name or an address. This is expected, documented, and the reason every
  OCR-derived field requires staff review.

## What this application does not defend against

Being clear about this matters more than sounding secure:

- **A compromised Windows account.** Everything the application can see, that account can
  see.
- **A malicious card.** Signature verification confirms a cryptographic relationship
  between the data read and the packaged trust material. It does not confirm that a card is
  currently valid or has not been invalidated.
- **Physical access to an unlocked machine.**

## Supported versions

Only the latest release receives fixes.
