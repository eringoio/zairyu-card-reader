# Privacy

**日本語の要約は [README.ja.md](README.ja.md) にあります。**

This document states plainly what the application reads, what it refuses to read, what it
keeps, and what leaves the machine. It is written so a non-engineer responsible for a
workplace can decide whether the tool is acceptable.

## The short version

- Everything happens on one PC. **No card data ever leaves it over a network.**
- The application makes **no outbound network request at runtime**, at all.
- The only thing written to disk is which reader you selected.
- Face photographs, card images, raw IC data, and My Number data are never stored, never
  displayed, and never copied.
- The one place card data does leave the application is **the Windows clipboard**, because
  copying is the entire point of the tool. That has consequences — see below.

## What is read from the card

Reading only starts after you type the card number printed on the front of the card. The
card itself requires that number; it is the access key.

| Read | Purpose | What happens to it |
|---|---|---|
| Structured business fields | The 17 reviewed fields | Shown on screen, copied when you choose |
| Name image | OCR only, when the card stores the name as an image | Processed in memory, never saved, never shown as an image |
| Address image | OCR only, same | Processed in memory, never saved, never shown as an image |
| Face image | **Signature verification only** | See below |
| Card certificate and signature | Signature verification only | Never displayed, never copied, never logged |

### The face image

Second-generation cards store the name image and the face image in the same file, and the
card's digital signature is computed over the printed entries **plus the face image plus the
name image**. Verifying that signature therefore requires reading the face image.

When the application does this, the face bytes:

- exist only in memory, only inside the verification function;
- are overwritten as soon as verification finishes;
- are never decoded to a picture, never displayed, never saved, never copied, never logged,
  and never included in any API response.

CPython cannot guarantee that every copy of a value is erased from memory — the interpreter
and allocator may retain copies. This is a documented mitigation, not a guarantee of memory
sanitisation.

## What is never read

- **My Number (個人番号)** and any My Number application data.
- **JPKI** certificates and keys.
- Specified residence cards (`07`/`08`) are refused by policy before any such access is
  attempted.

## What is stored on the PC

| Location | Contents |
|---|---|
| `%APPDATA%\ZairyuReader\config.json` | The selected reader index and the application version. **Nothing else.** |
| `%LOCALAPPDATA%\ZairyuReader\BrowserProfile` | A dedicated browser profile used only for the application window, when Chromium app mode is used. No card data. |

**No card data is written to disk.** Not the fields, not the images, not the certificates.
Scan results and the temporary batch list live in the page's memory and disappear when the
page closes.

Diagnostic traces are off by default and, when enabled, record structure only: APDU header
bytes, status words, response *lengths*, TLV tags, and true/false field-presence flags.
There is no configuration switch anywhere in the application that can make a trace contain
raw chip data, images, or personal values.

## What leaves the machine

**Over a network: nothing.** The application performs no outbound network request while it
runs. The only network call in the codebase is the launcher checking its own loopback
health endpoint on `127.0.0.1`.

Internet access is needed only twice, and never while reading a card:

1. installing Python dependencies, when running from source;
2. staging the OCR model, once.

The released `.exe` bundles the model and needs neither.

**Via the clipboard: the 17 reviewed fields, when you press copy.** This is deliberate. It
is also the largest privacy consideration in normal use.

> **Windows clipboard history and cloud clipboard sync may retain copied card data.** The
> "clear" button in the application replaces the current clipboard contents, but Windows
> does not allow an application to erase clipboard history. If clipboard sync is enabled,
> Windows may have sent the text to your Microsoft account.
>
> On any PC used to read residence cards, turn off clipboard history and cloud clipboard
> sync: **Settings → System → Clipboard**.

## Who can reach the application

The server listens on `127.0.0.1` only, and refuses to bind anywhere else. Beyond that it
allowlists the `Host` header, requires a per-process token on every staff endpoint, checks
request provenance, and emits no CORS headers — so a web page you happen to visit cannot
reach it either.

What this does **not** protect against: another program running under the same Windows user
account. Such a program can read the same page the browser reads, and therefore the token.
This is inherent to a local application with no user accounts. If the Windows account is
compromised, the application's data is compromised.

## Your responsibilities

The tool does not decide whether you may read a card. Before reading:

- obtain the holder's consent, or confirm you are otherwise authorised to verify the card;
- follow your organisation's rules for handling personal information;
- remember that residence-card data is personal information under Japan's Act on the
  Protection of Personal Information.

Treat copied text and anything you paste it into as sensitive.

## When reporting a problem publicly

**Never post genuine card photographs, screenshots of real card data, real names,
addresses, birth dates, or card numbers, APDU/TLV/IC dumps, card certificates or signatures,
or logs containing any of these.** Use synthetic values. Describing the shape of the data is
enough to diagnose almost anything.

For a vulnerability, use private reporting instead — see [SECURITY.md](SECURITY.md).

## Technical detail

The enforcement mechanisms behind every statement above are described in
[docs/privacy-and-security.md](docs/privacy-and-security.md).
