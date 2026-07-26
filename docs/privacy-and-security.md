# Privacy and security

[日本語版 →](privacy-and-security.ja.md)

zairyu-card-reader handles highly sensitive personal information. Its design keeps card reading
on the local computer, but local-only software can still have security defects. Keep Windows,
the reader driver, and this application updated, and use the application only on a computer
you trust.

## Data handling

- Card reading, OCR, and signature verification run on the local PC.
- The application does not send card data to a server and does not need an internet connection
  to read a card.
- It has no account, cloud storage, telemetry, analytics, or database.
- It does not retain card images, face photographs, raw IC data, or OCR data in logs.
- The selected reader index is the only persistent setting.

## Local service boundary

The desktop application uses a local loopback connection between its window and its bundled
service. It refuses non-loopback connections and is not intended for LAN, tunnel, reverse
proxy, or public hosting. Do not expose its local port to another device or network.

## Your responsibilities

Use the application only where you are authorised to handle the cardholder's information.
Check the displayed data before using it in a procedure, especially OCR-derived text. Protect
the Windows account and screen from unauthorised access while the application is open.

## Security reports

Please report a suspected vulnerability privately using the instructions in
[SECURITY.md](../SECURITY.md). Do not include a real card number, image, or other personal data
in a report.
