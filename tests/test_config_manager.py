"""Tests for config_manager.py — export/import .zip, schema validation."""

import json
import os
import zipfile

import pytest

from config_manager import (
    CURRENT_SCHEMA_VERSION,
    create_default_config,
    export_config,
    import_config,
    load_config,
    save_config,
    validate_config,
)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_valid_config(self):
        config = create_default_config()
        ok, err = validate_config(config)
        assert ok
        assert err == ""

    def test_missing_version(self):
        config = create_default_config()
        del config["version"]
        ok, err = validate_config(config)
        assert not ok
        assert "version" in err

    def test_wrong_version(self):
        config = create_default_config()
        config["version"] = 999
        ok, err = validate_config(config)
        assert not ok
        assert "999" in err

    def test_missing_key(self):
        config = create_default_config()
        del config["custom_terms"]
        ok, err = validate_config(config)
        assert not ok
        assert "custom_terms" in err

    def test_wrong_type(self):
        config = create_default_config()
        config["substring_match"] = "yes"  # should be bool
        ok, err = validate_config(config)
        assert not ok
        assert "substring_match" in err

    def test_invalid_custom_terms_value(self):
        config = create_default_config()
        config["custom_terms"] = {"schools": "not a list"}
        ok, err = validate_config(config)
        assert not ok
        assert "schools" in err

    def test_invalid_custom_terms_item(self):
        config = create_default_config()
        config["custom_terms"] = {"schools": [123]}
        ok, err = validate_config(config)
        assert not ok
        assert "123" in err

    def test_invalid_file_type(self):
        config = create_default_config()
        config["file_types"] = ["txt"]  # missing dot
        ok, err = validate_config(config)
        assert not ok
        assert "txt" in err

    def test_not_dict(self):
        ok, err = validate_config([1, 2, 3])
        assert not ok
        assert "JSON 物件" in err


# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------

class TestCreateDefault:
    def test_default_is_valid(self):
        config = create_default_config()
        ok, _ = validate_config(config)
        assert ok

    def test_default_has_image_types(self):
        config = create_default_config()
        assert ".jpg" in config["file_types"]
        assert ".png" in config["file_types"]


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

class TestExportImport:
    def test_export_creates_zip(self, tmp_path):
        config = create_default_config()
        config["custom_terms"] = {"schools": ["台灣大學"]}
        zip_path = str(tmp_path / "test.zip")

        result = export_config(config, str(tmp_path), zip_path)
        assert os.path.isfile(result)
        assert zipfile.is_zipfile(result)

        with zipfile.ZipFile(result) as zf:
            assert "config.json" in zf.namelist()

    def test_export_includes_logos(self, tmp_path):
        logo_dir = tmp_path / "logos"
        logo_dir.mkdir()
        (logo_dir / "test_logo.png").write_bytes(b"fake png data")

        config = create_default_config()
        config["logo_templates"] = ["test_logo.png"]

        zip_path = str(tmp_path / "out.zip")
        export_config(config, str(logo_dir), zip_path)

        with zipfile.ZipFile(zip_path) as zf:
            assert "logo_templates/test_logo.png" in zf.namelist()

    def test_import_roundtrip(self, tmp_path):
        # Export
        config = create_default_config()
        config["custom_terms"] = {"schools": ["台大", "清大"]}
        zip_path = str(tmp_path / "config.zip")
        export_config(config, str(tmp_path), zip_path)

        # Import to different dir
        target = str(tmp_path / "imported")
        imported, summary = import_config(zip_path, target)

        assert imported["version"] == CURRENT_SCHEMA_VERSION
        assert imported["custom_terms"] == {"schools": ["台大", "清大"]}
        assert "自訂詞彙 2 個" in summary

    def test_import_with_logos(self, tmp_path):
        # Create logo and export
        logo_dir = tmp_path / "logos"
        logo_dir.mkdir()
        (logo_dir / "logo.png").write_bytes(b"logo data")

        config = create_default_config()
        config["logo_templates"] = ["logo.png"]
        zip_path = str(tmp_path / "config.zip")
        export_config(config, str(logo_dir), zip_path)

        # Import
        target = str(tmp_path / "imported")
        imported, summary = import_config(zip_path, target)

        assert "logo.png" in imported["logo_templates"]
        assert os.path.isfile(os.path.join(target, "logo_templates", "logo.png"))
        assert "logo 模板 1 個" in summary

    def test_import_invalid_zip(self, tmp_path):
        bad_file = tmp_path / "bad.zip"
        bad_file.write_text("not a zip")

        with pytest.raises(ValueError, match="zip"):
            import_config(str(bad_file), str(tmp_path))

    def test_import_missing_config_json(self, tmp_path):
        # Create zip without config.json
        zip_path = str(tmp_path / "no_config.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "hello")

        with pytest.raises(ValueError, match="config.json"):
            import_config(zip_path, str(tmp_path))

    def test_import_invalid_schema(self, tmp_path):
        # Create zip with bad config
        zip_path = str(tmp_path / "bad_config.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("config.json", json.dumps({"version": 999}))

        with pytest.raises(ValueError, match="999"):
            import_config(zip_path, str(tmp_path))

    def test_import_nonexistent_file(self, tmp_path):
        with pytest.raises(ValueError, match="不存在"):
            import_config("/nonexistent/file.zip", str(tmp_path))


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_and_load(self, tmp_path):
        config = create_default_config()
        config["custom_terms"] = {"schools": ["台大"]}
        path = str(tmp_path / "config.json")

        save_config(config, path)
        loaded = load_config(path)

        assert loaded["custom_terms"] == {"schools": ["台大"]}
        assert loaded["version"] == CURRENT_SCHEMA_VERSION

    def test_load_missing_returns_default(self, tmp_path):
        loaded = load_config(str(tmp_path / "nonexistent.json"))
        ok, _ = validate_config(loaded)
        assert ok
