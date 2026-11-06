import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


spec = importlib.util.spec_from_file_location("prepare_hybrid_inputs", Path(__file__).resolve().parents[1] / "scripts/prepare_hybrid_inputs.py")
helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)


class HybridInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.imports = self.root / "imports"; self.imports.mkdir()
        self.manifest = b'{"frozen": "fixture, not a real OCR cache"}'
        self.anchor = patch.object(helper, "OCR_MANIFEST_SHA256", hashlib.sha256(self.manifest).hexdigest())
        self.anchor.start(); self.addCleanup(self.anchor.stop)

    def test_existing_cache_located_without_modification_or_materialization(self):
        cache = self.imports / "nested/cache"; cache.mkdir(parents=True)
        (cache / "run_manifest.json").write_bytes(self.manifest)
        result = helper.locate_cache(self.imports, self.root / "new")
        self.assertFalse(result["materialized"]); self.assertEqual(Path(result["ocr_dir"]), cache)
        self.assertFalse((self.root / "new").exists()); self.assertEqual((cache / "run_manifest.json").read_bytes(), self.manifest)

    def test_windows_zip_names_materialize_exactly_without_changing_archive(self):
        archive = self.imports / "cache.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("cache\\run_manifest.json", self.manifest); z.writestr("cache\\attempts\\page\\raw.json", b'"retained raw"')
        before = archive.read_bytes(); result = helper.locate_cache(self.imports, self.root / "new")
        self.assertTrue(result["materialized"])
        self.assertEqual((self.root / "new/attempts/page/raw.json").read_bytes(), b'"retained raw"')
        self.assertEqual(archive.read_bytes(), before)
        with self.assertRaises(FileExistsError): helper.locate_cache(self.imports, self.root / "new")

    def test_unsafe_or_duplicate_archive_names_rejected_before_extraction(self):
        archive = self.imports / "cache.zip"
        for name in ("cache/../escape", "cache/C:/escape", "cache/RUN_MANIFEST.JSON"):
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("cache/run_manifest.json", self.manifest); z.writestr(name, b"unsafe")
            with self.assertRaisesRegex(ValueError, "Unsafe/duplicate"): helper.locate_cache(self.imports, self.root / "new")
            self.assertFalse((self.root / "new").exists())

    def test_unrecognized_broader_cache_cannot_be_substituted(self):
        (self.imports / "run_manifest.json").write_text('{"broader_cohort": true}')
        with self.assertRaisesRegex(ValueError, "Original completed GPU cache not found"):
            helper.locate_cache(self.imports, self.root / "new")

    def test_cannot_materialize_inside_preserved_imports(self):
        with self.assertRaisesRegex(ValueError, "outside preserved imports"):
            helper.locate_cache(self.imports, self.imports / "new")


if __name__ == "__main__": unittest.main()
