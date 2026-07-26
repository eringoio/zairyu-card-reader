# Troubleshooting

[日本語版 →](troubleshooting.ja.md)

## The reader is not listed

1. Reconnect the reader directly to the PC and try another USB port.
2. Install or update the manufacturer's Windows driver.
3. Close other software that may be using the reader, then restart this application.
4. Confirm in Windows that the PC/SC smart-card service is available.

The application was field-tested with a Sony FeliCa RC-S300 on Windows 10, Windows 11, and
Windows Server 2016. Other PC/SC readers may work but are not guaranteed.

## The card is not detected or cannot be read

Remove and place the card on the reader again, keep it still, and enter the card number exactly
as printed. A card generation or reader/driver combination may not be supported. Never post a
real card number or card image in a support request.

## OCR is wrong or missing

OCR may make mistakes, especially with long names, spaces, complex kanji, and the final part of
an address. Check the text manually. See [OCR](ocr.md) for known limitations. If OCR is
unavailable in a source build, rebuild after following [Building](building.md).

## Signature verification does not succeed

Check that the card was read successfully first. A failed, incomplete, or unavailable result
does not by itself identify the cause or prove the card invalid. Review the physical card and
follow the procedure's rules. See [Signature verification](signature-verification.md).

## The application window does not open

Run the extracted release from a normal local folder, not from inside the ZIP archive. Windows
may show a warning for an unsigned release; confirm that you obtained the archive from the
official release page and verify its published SHA-256 checksum before choosing to run it.

## Reporting a problem

Include the application version, Windows version, reader model, driver version, and a
description of the non-sensitive symptom. Do not include cardholder data, images, screenshots
containing personal information, logs containing such information, or raw card traffic.
