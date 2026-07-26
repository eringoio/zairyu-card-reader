# OCR

[日本語版 →](ocr.ja.md)

Some compatible residence cards store the name and address as images. When that is the case,
zairyu-card-reader uses a bundled OCR model on the local PC. The image and the OCR result are
not sent to a server.

## What to expect

OCR is an aid for reviewing a card; it is not a guarantee that every character is correct.
The application makes its result visible for a person to compare with the card and other
available information.

Field testing on genuine cards found that OCR usually reads names and addresses well. Known
limitations include:

- Spaces in names can appear in the wrong position.
- A long name can be incomplete.
- The final part of an address, after the prefecture and municipality, can be read incorrectly.
- Place names containing complex kanji can be read incorrectly.

Always check OCR-derived text before relying on it for an administrative procedure.

## Privacy

OCR runs locally. The application does not save the source image, raw OCR data, or its result
to a database or log. See [Privacy](../PRIVACY.md) for the full data-handling policy.

## Building from source

The packaged Windows release includes the required model. Source builds download the pinned
model during dependency preparation; see [Building](building.md). A build should fail clearly
if the model is unavailable rather than silently using a different model.
