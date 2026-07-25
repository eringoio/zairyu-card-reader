"""Offline PP-OCRv6 ONNX Runtime recognizer for transient card-field images."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import Any

from reader.ocr.engine import OcrResult
from reader.runtime_paths import ocr_model_dir

MODEL_NAME = "PP-OCRv6_medium_rec"
MODEL_SHA256 = "9c09abf0957f7968c7586464b7397b84ad2387a0497a351af40e9acc71b673ba"


class OcrAssetError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_unavailable(warning: str) -> OcrResult:
    return OcrResult(engine="unavailable", model=MODEL_NAME, warnings=[warning])


class UnavailableOcrEngine:
    """A no-op that leaves structured card reads usable when OCR is unavailable."""

    def __init__(self, model: str = MODEL_NAME, warning: str = "Local OCR is unavailable.") -> None:
        self._result = OcrResult(engine="unavailable", model=model, warnings=[warning])

    def recognize_name(self, image: bytes) -> OcrResult:
        del image
        return self._result

    def recognize_address(self, image: bytes) -> OcrResult:
        del image
        return self._result


class OnnxOcrEngine:
    """Metadata-validated PP-OCRv6 CTC recognition with no runtime network activity."""

    def __init__(self, model_dir: Path, manifest: dict[str, Any]) -> None:
        self.model_dir = model_dir
        self.manifest = manifest
        self.model_name = str(manifest["model_name"])
        self.metadata = self._load_verified_metadata()
        self.dictionary = self._load_verified_dictionary()
        self._validate_metadata()
        try:
            import onnxruntime as ort
        except Exception as exc:  # pragma: no cover - installed with the application
            raise OcrAssetError("ONNX Runtime CPU cannot initialize.") from exc
        try:
            self.session = ort.InferenceSession(
                str(self._verified_file("model_file", "model_sha256")),
                providers=["CPUExecutionProvider"],
            )
        except Exception as exc:
            raise OcrAssetError("ONNX Runtime CPU cannot initialize the local OCR model.") from exc
        self._inspect_session_contract()
        self._validate_runtime_output_contract()

    @classmethod
    def from_assets(cls) -> OnnxOcrEngine | UnavailableOcrEngine:
        model_dir = ocr_model_dir()
        manifest_path = model_dir / "manifest.json"
        if not manifest_path.is_file():
            return UnavailableOcrEngine(warning="Local PP-OCRv6 model assets are not packaged.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            required = {
                "model_name", "model_file", "model_sha256", "metadata_file",
                "metadata_sha256", "dictionary_file", "dictionary_sha256", "source_revision",
            }
            if not required <= set(manifest) or manifest.get("model_name") != MODEL_NAME:
                raise OcrAssetError("The local PP-OCRv6 manifest is incomplete.")
            if str(manifest["model_sha256"]).lower() != MODEL_SHA256:
                raise OcrAssetError("The local PP-OCRv6 manifest has an unexpected model checksum.")
            return cls(model_dir, manifest)
        except OcrAssetError as exc:
            return UnavailableOcrEngine(warning=str(exc))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return UnavailableOcrEngine(warning="The local PP-OCRv6 manifest cannot be read.")

    # Alias retained only for callers that previously constructed an engine by profile.
    @classmethod
    def from_profile(cls, profile: str = "ppocrv6") -> OnnxOcrEngine | UnavailableOcrEngine:
        del profile
        return cls.from_assets()

    def _verified_file(self, filename_key: str, hash_key: str) -> Path:
        path = self.model_dir / str(self.manifest[filename_key])
        expected = str(self.manifest[hash_key]).lower()
        if not path.is_file():
            raise OcrAssetError("Local PP-OCRv6 model assets are not packaged.")
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            raise OcrAssetError("The local PP-OCRv6 manifest has an invalid checksum.")
        if _sha256(path) != expected:
            raise OcrAssetError("The local PP-OCRv6 model checksum does not match its manifest.")
        return path

    def _load_verified_metadata(self) -> dict[str, Any]:
        try:
            import yaml
        except Exception as exc:  # pragma: no cover - requirements installation failure
            raise OcrAssetError("Local OCR metadata support is unavailable.") from exc
        path = self._verified_file("metadata_file", "metadata_sha256")
        try:
            parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise OcrAssetError("The local PP-OCRv6 metadata is invalid.") from exc
        if not isinstance(parsed, dict):
            raise OcrAssetError("The local PP-OCRv6 metadata is invalid.")
        return parsed

    def _load_verified_dictionary(self) -> list[str]:
        path = self._verified_file("dictionary_file", "dictionary_sha256")
        characters = path.read_text(encoding="utf-8").splitlines()
        metadata_characters = self.metadata.get("PostProcess", {}).get("character_dict")
        if not isinstance(metadata_characters, list) or not metadata_characters:
            raise OcrAssetError("The local PP-OCRv6 character dictionary is missing.")
        if characters != [str(value) for value in metadata_characters]:
            raise OcrAssetError("The local PP-OCRv6 character dictionary does not match its metadata.")
        return characters

    def _validate_metadata(self) -> None:
        preprocess = self.metadata.get("PreProcess", {}).get("transform_ops", [])
        decode = self.metadata.get("PostProcess", {})
        shape = next((op.get("RecResizeImg", {}).get("image_shape") for op in preprocess if isinstance(op, dict) and "RecResizeImg" in op), None)
        mode = next((op.get("DecodeImage", {}).get("img_mode") for op in preprocess if isinstance(op, dict) and "DecodeImage" in op), None)
        if mode != "BGR" or shape != [3, 48, 320] or decode.get("name") != "CTCLabelDecode":
            raise OcrAssetError("The local PP-OCRv6 metadata has an unsupported recognition contract.")
        self.reference_dimensions = [int(value) for value in shape]
        self.blank_index = 0

    def _inspect_session_contract(self) -> None:
        inputs = self.session.get_inputs()
        outputs = self.session.get_outputs()
        if len(inputs) != 1 or len(outputs) != 1:
            raise OcrAssetError("The local PP-OCRv6 ONNX model has an unsupported input/output contract.")
        input_meta = inputs[0]
        shape = list(input_meta.shape)
        if input_meta.type != "tensor(float)" or len(shape) != 4:
            raise OcrAssetError("The local PP-OCRv6 ONNX input contract is invalid.")
        if not self._dimension_matches(shape[1], 3) or not self._dimension_matches(shape[2], 48):
            raise OcrAssetError("The local PP-OCRv6 ONNX input dimensions are incompatible with its metadata.")
        self.input_name = input_meta.name
        self.input_width = int(shape[3]) if isinstance(shape[3], int) and shape[3] > 0 else self.reference_dimensions[2]
        output_shape = list(outputs[0].shape)
        if len(output_shape) != 3:
            raise OcrAssetError("The local PP-OCRv6 ONNX output contract is invalid.")
        allowed_classes = {len(self.dictionary) + 1, len(self.dictionary) + 2}
        concrete = [axis for axis in (1, 2) if isinstance(output_shape[axis], int) and output_shape[axis] in allowed_classes]
        possible = concrete or [axis for axis in (1, 2) if not isinstance(output_shape[axis], int)]
        if len(possible) != 1:
            raise OcrAssetError("The local PP-OCRv6 ONNX class dimension is incompatible with its dictionary.")
        self.class_axis = possible[0]
        self.class_count = 0
        if isinstance(output_shape[self.class_axis], int):
            self._configure_character_mapping(output_shape[self.class_axis])

    @staticmethod
    def _dimension_matches(value: Any, expected: int) -> bool:
        return not isinstance(value, int) or value <= 0 or value == expected

    def _configure_character_mapping(self, class_count: int) -> None:
        """Derive CTC special tokens from the inspected output class count.

        The PP-OCRv6 metadata list intentionally contains only ordered ordinary
        characters. The matching export has either a blank prefix, or a blank prefix plus
        the decoder's generated trailing space token. No PP-OCRv5 class-count assumption
        is used here.
        """
        basic_count = len(self.dictionary) + 1
        if class_count == basic_count:
            mapping = [""] + self.dictionary
        elif class_count == basic_count + 1:
            mapping = [""] + self.dictionary + [" "]
        else:
            raise OcrAssetError("The local PP-OCRv6 ONNX class dimension is incompatible with its dictionary.")
        self.class_count = class_count
        self.class_to_character = mapping

    def _validate_runtime_output_contract(self) -> None:
        try:
            import numpy as np
            output = self.session.run(None, {self.input_name: np.zeros((1, 3, 48, self.input_width), dtype="float32")})[0]
            shape = list(output.shape)
            if len(shape) != 3:
                raise ValueError("rank")
            self._configure_character_mapping(int(shape[self.class_axis]))
        except OcrAssetError:
            raise
        except Exception as exc:
            raise OcrAssetError("The local PP-OCRv6 ONNX output contract is invalid.") from exc

    def recognize_name(self, image: bytes) -> OcrResult:
        return self._recognize(image)

    def recognize_address(self, image: bytes) -> OcrResult:
        return self._recognize(image)

    def _recognize(self, image: bytes) -> OcrResult:
        try:
            tensor = self._prepare_image(image)
            output = self.session.run(None, {self.input_name: tensor})[0]
            text, confidence = self._decode_ctc(output)
            return OcrResult(text=text, lines=[text] if text else [], confidence=confidence,
                             engine="ppocrv6", model=self.model_name)
        except OcrAssetError as exc:
            return _safe_unavailable(str(exc))
        except Exception:
            return _safe_unavailable("Local PP-OCRv6 recognition failed.")

    def _prepare_image(self, image: bytes):
        try:
            import numpy as np
            from PIL import Image
            if not image:
                raise ValueError("empty image")
            with Image.open(BytesIO(image)) as source:
                source.load()
                if source.width <= 0 or source.height <= 0:
                    raise ValueError("empty image")
                # Pillow decodes RGB; PP-OCRv6 metadata explicitly requires BGR.
                bgr = np.asarray(source.convert("RGB"), dtype="uint8")[:, :, ::-1]
        except Exception as exc:
            raise OcrAssetError("Local OCR could not decode the transient image.") from exc
        height, width = self.reference_dimensions[1], self.input_width
        resized_width = max(1, min(width, round(bgr.shape[1] * height / bgr.shape[0])))
        try:
            from PIL import Image
            resized = np.asarray(Image.fromarray(bgr[:, :, ::-1]).resize((resized_width, height), Image.Resampling.LANCZOS), dtype="uint8")[:, :, ::-1]
        except Exception as exc:
            raise OcrAssetError("Local OCR image resizing failed.") from exc
        normalized = resized.astype("float32").transpose((2, 0, 1)) / 255.0
        normalized = (normalized - 0.5) / 0.5
        tensor = np.zeros((1, 3, height, width), dtype="float32")
        tensor[0, :, :, :resized_width] = normalized
        return tensor

    def _decode_ctc(self, output: Any) -> tuple[str, float | None]:
        try:
            import numpy as np
            scores = np.asarray(output)
            if scores.ndim != 3 or scores.shape[0] < 1:
                raise ValueError("rank")
            logits = scores[0] if self.class_axis == 2 else scores[0].transpose(1, 0)
            if logits.shape[1] != self.class_count:
                raise ValueError("classes")
            # Exported Paddle models normally output probabilities. Support logits safely.
            sums = logits.sum(axis=1)
            if np.any(logits < 0) or not np.allclose(sums, 1.0, atol=1e-3):
                shifted = logits - logits.max(axis=1, keepdims=True)
                probabilities = np.exp(shifted) / np.exp(shifted).sum(axis=1, keepdims=True)
            else:
                probabilities = logits
            indices = probabilities.argmax(axis=1).tolist()
            values = probabilities.max(axis=1).tolist()
        except Exception as exc:
            raise OcrAssetError("The local PP-OCRv6 model returned an unsupported result.") from exc
        decoded: list[str] = []
        selected: list[float] = []
        previous: int | None = None
        for index, probability in zip(indices, values, strict=True):
            if not 0 <= index < self.class_count:
                raise OcrAssetError("The local PP-OCRv6 model returned an invalid character index.")
            if index == self.blank_index:
                previous = None
                continue
            if index != previous:
                decoded.append(self.class_to_character[index])
                selected.append(float(probability))
            previous = index
        return "".join(decoded).strip(), round(sum(selected) / len(selected), 4) if selected else None
