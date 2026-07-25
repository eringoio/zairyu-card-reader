from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import yaml
from PIL import Image

from reader.ocr.engines import get_ocr_engine
from reader.ocr.onnx_engine import MODEL_NAME, OnnxOcrEngine, UnavailableOcrEngine


class _Meta:
    def __init__(self, name: str, shape: list[object], type_: str = "tensor(float)") -> None:
        self.name, self.shape, self.type = name, shape, type_


class _Session:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs

    def get_inputs(self):
        return [_Meta("image", [1, 3, 48, 320])]

    def get_outputs(self):
        return [_Meta("probabilities", [1, 5, 3])]

    def run(self, names, inputs):
        del names, inputs
        return [np.array([[[.1, .8, .1], [.8, .1, .1], [.1, .1, .8], [.1, .1, .8]]], dtype="float32")]


def _stage_assets(tmp_path: Path) -> Path:
    model = tmp_path / "model.onnx"
    metadata = tmp_path / "inference.yml"
    dictionary = tmp_path / "dictionary.txt"
    model.write_bytes(b"synthetic model")
    document = {
        "PreProcess": {"transform_ops": [
            {"DecodeImage": {"img_mode": "BGR"}},
            {"RecResizeImg": {"image_shape": [3, 48, 320]}},
        ]},
        "PostProcess": {"name": "CTCLabelDecode", "character_dict": ["A", "B"]},
    }
    metadata.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")
    dictionary.write_text("A\nB\n", encoding="utf-8")
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "model_name": MODEL_NAME,
        "model_file": model.name,
        # The source package verifier rejects a synthetic model hash; direct construction
        # below exercises the contract-level tests with a local manifest.
        "model_sha256": digest(model),
        "metadata_file": metadata.name,
        "metadata_sha256": digest(metadata),
        "dictionary_file": dictionary.name,
        "dictionary_sha256": digest(dictionary),
        "source_revision": "test",
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def _engine(tmp_path: Path, monkeypatch) -> OnnxOcrEngine:
    root = _stage_assets(tmp_path)
    monkeypatch.setitem(sys.modules, "onnxruntime", SimpleNamespace(InferenceSession=_Session))
    return OnnxOcrEngine(root, json.loads((root / "manifest.json").read_text(encoding="utf-8")))


def test_missing_model_reports_unavailable_rather_than_using_another_engine(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("reader.ocr.onnx_engine.ocr_model_dir", lambda: tmp_path)
    engine = OnnxOcrEngine.from_assets()
    assert isinstance(engine, UnavailableOcrEngine)
    assert engine.recognize_address(b"synthetic").engine == "unavailable"


def test_unavailable_engine_preserves_its_own_warning() -> None:
    result = UnavailableOcrEngine(warning="PP-OCRv6 unavailable").recognize_name(b"x")
    assert result.engine == "unavailable"
    assert result.warnings == ["PP-OCRv6 unavailable"]


def test_metadata_dictionary_order_mismatch_is_rejected(monkeypatch, tmp_path: Path) -> None:
    root = _stage_assets(tmp_path)
    (root / "dictionary.txt").write_text("B\nA\n", encoding="utf-8")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["dictionary_sha256"] = hashlib.sha256((root / "dictionary.txt").read_bytes()).hexdigest()
    with __import__("pytest").raises(Exception, match="dictionary"):
        OnnxOcrEngine(root, manifest)


def test_preprocessing_uses_bgr_height_normalization_and_right_padding(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(tmp_path, monkeypatch)
    image = Image.new("RGB", (2, 1), color=(255, 0, 0))
    from io import BytesIO
    output = BytesIO(); image.save(output, format="PNG")
    tensor = engine._prepare_image(output.getvalue())
    assert tensor.shape == (1, 3, 48, 320)
    # Red RGB becomes BGR, so B (channel 0) is -1 and R (channel 2) is +1.
    assert tensor[0, 0, 0, 0] == -1.0
    assert tensor[0, 2, 0, 0] == 1.0
    assert np.all(tensor[:, :, :, 96:] == 0.0)


def test_preprocessing_rejects_empty_and_malformed_images(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(tmp_path, monkeypatch)
    for image in (b"", b"not an image"):
        with __import__("pytest").raises(Exception, match="decode"):
            engine._prepare_image(image)


def test_ctc_decoder_collapses_only_uninterrupted_duplicates(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(tmp_path, monkeypatch)
    # blank, A, A, blank, A -> AA. The blank resets the prior class.
    output = np.array([[[.1, .9, .0], [.1, .8, .1], [.9, .1, .0], [.1, .9, .0]]], dtype="float32")
    text, confidence = engine._decode_ctc(output)
    assert text == "AA"
    assert confidence == 0.9


def test_ctc_decoder_handles_empty_and_rejects_class_contract_mismatch(monkeypatch, tmp_path: Path) -> None:
    engine = _engine(tmp_path, monkeypatch)
    text, confidence = engine._decode_ctc(np.array([[[1.0, 0.0, 0.0]]], dtype="float32"))
    assert text == "" and confidence is None
    with __import__("pytest").raises(Exception, match="unsupported"):
        engine._decode_ctc(np.zeros((1, 2, 2), dtype="float32"))


def test_default_engine_is_local_only(monkeypatch) -> None:
    monkeypatch.delenv("OCR_ENGINE", raising=False)
    engine = get_ocr_engine()
    # Exactly two outcomes are permitted: the packaged ONNX recognizer, or an honest
    # "unavailable". There is no third engine to fall back to.
    assert isinstance(engine, (OnnxOcrEngine, UnavailableOcrEngine))


def test_ocr_modules_import_no_process_or_temporary_file_machinery() -> None:
    """No OCR path may write a card image to disk or hand it to an interpreter.

    A PowerShell/Windows-Runtime fallback previously did both: it wrote the preprocessed
    card image to %TEMP% and ran `powershell.exe -ExecutionPolicy Bypass`. Inspecting the
    import graph (rather than the prose) keeps the regression visible without tripping on
    a comment that merely names the thing being prevented.
    """
    import ast

    import reader.ocr.engines as engines
    import reader.ocr.front_text as front_text
    import reader.ocr.onnx_engine as onnx_engine
    import reader.ocr.pipeline as pipeline

    forbidden_modules = {"subprocess", "tempfile", "shutil", "os.path", "socket", "urllib"}
    for module in (engines, front_text, onnx_engine, pipeline):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        leaked = imported & forbidden_modules
        assert not leaked, f"{module.__name__} must not import {sorted(leaked)}"


def test_no_powershell_helper_script_ships_in_the_repository() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "tools" / "windows_ocr.ps1").exists()
    assert not (repo_root / "reader" / "ocr" / "windows_ocr.py").exists()
    # The PyInstaller spec must not package anything for an external interpreter.
    spec = (repo_root / "zairyu-reader.spec").read_text(encoding="utf-8")
    assert ".ps1" not in spec
