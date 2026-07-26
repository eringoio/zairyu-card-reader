# Troubleshooting

> **Before opening a public issue: never post genuine card photographs, screenshots of real
> card data, real names, addresses, birth dates, or card numbers, APDU/TLV/IC dumps, card
> certificates or signatures, or logs containing any of these.** Use synthetic values, as
> the tests do — describing the shape of the data is enough. For a security vulnerability,
> report privately instead: see [../SECURITY.md](../SECURITY.md).

## No reader found

Check:

- USB reader is plugged in.
- Reader driver is installed.
- Windows recognizes the device.
- Windows Smart Card service is running.
- Another app is not locking the reader.
- `pyscard` installed correctly.

## Card not detected

Check:

- Card is placed correctly on the reader.
- Reader supports the card type.
- Official or known reader app can detect the card.
- Try removing and placing the card again.
- Try a different USB port.

## Card does not respond to reset (`0x80100066`)

Windows found the reader but could not activate the card as a residence-card-compatible contactless smart card over PC/SC. Residence cards require JIS X 6322 B / ISO/IEC 14443 Type B support. The common message is:

```txt
Unable to connect with protocol: T0 or T1.
スマート カードがリセットに応答していません。 (0x80100066)
```

Check:

- Remove the card, wait a second, and place it flat and centered on the reader.
- Try both sides/orientations if the reader has a small antenna area.
- Confirm the reader supports ISO/IEC 14443 Type B through PC/SC, not only FeliCa, MIFARE, Type A, or generic NFC tag reading.
- If the reader appears as a generic contact reader, such as `Alcorlink USB Smart Card Reader`, it is probably a physical contact-card slot and not suitable for contactless residence cards.
- Close other card-reader apps that might be holding the reader.
- Test the same reader/card with an official or known working residence-card reader app.
- Try another USB port or powered hub if the reader LED repeatedly resets.

## Card connection lost during activation (`0x80100069`)

Windows started activation but then treated the card as removed. For a contactless residence card this usually means the card moved out of the antenna field, the reader is not a contactless Type B reader, or the reader cannot hold a stable Type B session.

Check:

- Keep the card flat and still on the antenna area before clicking Check card.
- Use a reader advertised as contactless PC/SC with ISO/IEC 14443 Type B support.
- Avoid generic contact smart-card readers; 在留カード is contactless.

If this still happens while reader detection works, record the exact reader model. The next implementation step may need a different Type B-capable reader, reader-specific PC/SC mode handling, or a LibJeID helper.

## `pyscard` installation fails

Try:

```bash
python -m pip install --upgrade pip setuptools wheel
pip install pyscard
```

`pyscard` builds a native extension. On Windows this usually needs the Microsoft C++ Build
Tools if no prebuilt wheel matches your Python version. Using 64-bit Python 3.11-3.13
generally avoids the build entirely.

## Port 8787 already in use

Use a different port:

```bash
python launch_reader.py --port 8788
```

If the application reports that the port is used by a *different* program, that is
deliberate: it checks the health identity before reusing a server, so it will not attach to
an unrelated service that happens to be listening there.

## The name or address is empty, or says "Could not be read"

The local OCR model is missing or failed to load. Stage it:

```bash
python tools\fetch_ocr_assets.py
python tools\verify_ocr_assets.py
```

IC-chip fields are unaffected — only the OCR-derived name and address. There is no second
OCR engine by design; see [ocr.md](ocr.md).

## The name or address is wrong

Expected, and the reason those fields must be reviewed. See the known limitations at the top
of [ocr.md](ocr.md). Consult the physical card when recording the information elsewhere;
the application has no field for typing it.

## "Another read is already in progress"

A previous read has not finished. Wait for it and try again. The application refuses
concurrent reads rather than queueing them, because a second reader session started
mid-read can corrupt the first.

## The desktop window does not open

The application falls back automatically: WebView2 → installed Chromium app mode → the
default browser. If all three fail, install the Microsoft Edge WebView2 Runtime or a
Chromium-family browser, or run `zairyu-reader.exe --browser`.

To see which stage is failing, force one:

```text
zairyu-reader.exe --webview      # fails clearly if WebView2 cannot start
zairyu-reader.exe --chrome-app   # fails clearly if no Chromium browser is found
```

## Signature verification says "未確認" / "Unconfirmed"

This is a result, not an error, and the specific status distinguishes the causes:
an untrusted or ambiguous certificate path, an expired or not-yet-valid certificate, a
missing signature or certificate on the card, or a genuine signature mismatch. See
[signature-verification.md](signature-verification.md) for what each status means.

Remember that a verified signature does not prove a card is currently valid, and an
unverified one does not by itself prove a card is fraudulent — a damaged read, an
unsupported card generation, or an expired CA certificate all produce non-verified results.

## Real residence-card reading fails while mock mode works

Mock mode exercises the UI and display fields without touching hardware, so this narrows
the problem to the reader, the driver, the card, or the protocol path. Work through "Card
reading fails with real card" below.

## Card reading fails with real card

Possible causes:

- wrong residence card number typed;
- reader/card compatibility issue;
- incorrect access-control flow;
- unsupported card generation;
- low-level APDU or library issue;
- card removed during reading.

Record:

- reader model;
- Windows version;
- Python version;
- error message;
- whether reader detection worked;
- whether ATR check worked;
- whether known reader apps can read the card.
