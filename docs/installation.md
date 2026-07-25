# Installation

**[日本語版 →](installation.ja.md)**

Two paths. Most people want the first.

---

## For staff: the released Windows package

1. Copy the `zairyu-reader` folder to the PC.
2. Install the NFC reader's driver, if Windows has not already done so.
3. Double-click `zairyu-reader.exe`.
4. Select your reader on the screen that opens, and press save.

Python is not required. Nothing is installed system-wide. Settings go to
`%APPDATA%\ZairyuReader\config.json` and contain only the reader index.

**No internet connection is required.** The package includes the OCR model and the
certificates.

---

## Requirements

### Windows

| Version | Status |
|---|---|
| Windows 11 (64-bit) | Supported |
| Windows 10 (64-bit) | Supported |
| Windows Server 2016 with **Desktop Experience** | Supported through Chromium app mode |
| Windows Server Core | **Not supported** — it cannot display a desktop UI |

### Reader

A **PC/SC contactless reader with ISO/IEC 14443 Type B support**. This is the part people
most often get wrong.

Residence cards are contactless Type B (JIS X 6322-B). A reader that only supports FeliCa,
MIFARE, Type A, or generic NFC tag reading **will not work**, and neither will a
contact-only reader with a card slot. A device that appears in Windows as something like
`Alcorlink USB Smart Card Reader` is usually a contact reader.

You also need:

- the reader manufacturer's PC/SC driver installed;
- the **Windows Smart Card service** (`SCardSvr`) running — check with `services.msc`.

### Display shell

The application opens its own window using one of:

1. **Microsoft Edge WebView2 Runtime** — preferred on desktop Windows.
2. **An installed Google Chrome, Microsoft Edge, or Chromium** in app mode — preferred on
   Windows Server 2016, and used automatically if WebView2 cannot start.
3. The default browser, as a last fallback (`--browser`).

If neither WebView2 nor a Chromium-family browser is present, the application shows a clear
message rather than failing silently.

### Python — source installation only

Python **3.11 or later**, 64-bit. Not needed for the released package.

---

## From source

```bash
git clone <repository-url>
cd zairyu-card-reader

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python tools\fetch_ocr_assets.py

python app.py
```

Open `http://127.0.0.1:8787`.

Use `python launch_reader.py` instead of `python app.py` to start the desktop shell rather
than the bare server.

### The OCR model step

`resources/ocr/ppocrv6/model.onnx` is 76 MB and is **not tracked in Git**. Staging it is a
separate, one-time step:

```bash
python tools\fetch_ocr_assets.py
```

On Windows you can equivalently run:

```powershell
powershell -ExecutionPolicy Bypass -File tools\fetch_ocr_assets.ps1
```

The tool downloads a pinned upstream revision and verifies every artifact — the model, the
metadata, and the generated dictionary — against the committed
`resources/ocr/ppocrv6/manifest.json`. If anything does not match, it names the artifact
that differs and installs nothing.

**Without this step the application still runs and still reads IC-chip fields.** Only the
OCR-derived name and address are reported as `読み取れませんでした` / "Could not be read".

Verify a staged set at any time:

```bash
python tools\verify_ocr_assets.py
```

See [ocr.md](ocr.md).

---

## Internet access: when it is needed and when it is not

| Activity | Internet |
|---|---|
| Installing Python dependencies (source only) | **Required, once** |
| Staging the OCR model (source only) | **Required, once** |
| Running the released package for the first time | Not required |
| **Reading cards, verifying signatures, copying** | **Never required** |

After setup, the application performs no outbound network request at all. The only network
call it makes is to its own loopback health endpoint on `127.0.0.1`.

---

## Never expose the server

> **Do not expose this server through a LAN, a tunnel (ngrok, Cloudflare Tunnel, or
> similar), a reverse proxy, a container port mapping, or a public host.**

The local API returns reviewed card data and **has no user authentication**, because a card
reader has no user to authenticate. It is designed on the assumption that only the person at
the keyboard can reach it.

`--host` accepts `127.0.0.1`, `localhost` and `::1` only. Any other value is refused with a
visible error in every mode, including `--no-browser`. This is not a setting to work around.

For the same reason the server also allowlists the `Host` header and requires a per-process
token, so that a web page you happen to visit cannot reach it either. See
[privacy-and-security.md](privacy-and-security.md).

---

## Launch modes

| Command | Behaviour |
|---|---|
| `zairyu-reader.exe` | Normal. WebView2 on desktop Windows; Chromium app mode on Server 2016 or if WebView2 fails |
| `zairyu-reader.exe --webview` | Force WebView2; fail clearly if it cannot start |
| `zairyu-reader.exe --chrome-app` | Force installed Chromium app mode |
| `zairyu-reader.exe --browser` | Last fallback: open the default browser |
| `zairyu-reader.exe --no-browser` | Server only, for troubleshooting. `--headless` is a compatibility alias and does **not** start headless Chrome |

`ZAIRYU_BROWSER_PATH` can point at a specific Chromium-family executable if automatic
discovery does not find yours.

The port defaults to 8787 and can be changed with `--port`.

---

## Verifying the installation

1. The application window opens without an address bar.
2. The reader list shows your reader.
3. With a card on the reader, **カードを確認 / Check card** reports the card as detected.
4. Tick the sample-data option and read once: the 17 fields fill with obviously synthetic
   values (`SAMPLE NAME`, `SAMPLELAND`). This confirms the UI and copy format work without
   touching a real card.

If step 2 or 3 fails, see [troubleshooting.md](troubleshooting.md).
