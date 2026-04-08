"""Tests for src.models.material_registry.MaterialRegistry."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.models.material_registry import MaterialRegistry
from src.models.material import Material

DATA_DIR = Path(__file__).parent.parent / "data"


def test_builtins_load():
    reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
    assert len(reg.all_materials) >= 40
    assert reg.get("vacuum").is_vacuum
    assert reg.get("al6061").k == 167.0


def test_custom_add_remove():
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(DATA_DIR / "materials.json", f"{tmp}/materials.json")
        user_path = Path(tmp) / "user_materials.json"
        reg = MaterialRegistry(Path(tmp) / "materials.json", user_path)
        mat = Material(id="test_mat", name="TestMat", color="#abcdef",
                       k=1.0, rho=100.0, cp=500.0, is_builtin=False)
        reg.add_or_update_custom(mat)
        assert "test_mat" in reg.custom
        reg2 = MaterialRegistry(Path(tmp) / "materials.json", user_path)
        assert "test_mat" in reg2.custom


def test_corrupt_user_file():
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(DATA_DIR / "materials.json", f"{tmp}/materials.json")
        user_path = Path(tmp) / "user_materials.json"
        user_path.write_text("not valid json {{{{")
        reg = MaterialRegistry(Path(tmp) / "materials.json", user_path)
        assert len(reg.builtins) >= 40


def test_generate_custom_id():
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(DATA_DIR / "materials.json", f"{tmp}/materials.json")
        reg = MaterialRegistry(Path(tmp) / "materials.json", Path(tmp) / "user.json")
        id1 = reg.generate_custom_id("My Alloy")
        mat = Material(id=id1, name="My Alloy", color="#ff0000",
                       k=10.0, rho=500.0, cp=400.0, is_builtin=False)
        reg.add_or_update_custom(mat)
        id2 = reg.generate_custom_id("My Alloy")
        assert id1 != id2


def test_190_plus_builtins():
    reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
    assert len(reg.builtins) >= 190


def test_all_required_fields():
    reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
    for mid, mat in reg.builtins.items():
        assert mat.id
        assert mat.name
        assert mat.color
        assert mat.category is not None


def test_no_duplicate_ids():
    with open(DATA_DIR / "materials.json") as f:
        mats = json.load(f)["materials"]
    ids = [m["id"] for m in mats]
    dupes = [i for i in ids if ids.count(i) > 1]
    assert not dupes


def test_subcategories_comma_delimited():
    reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
    subcats = [m for m in reg.builtins.values() if "," in (m.category or "")]
    assert len(subcats) > 50


def test_save_custom_includes_category():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(b'{"materials": []}')
        tmp_path = Path(f.name)
    try:
        reg = MaterialRegistry(DATA_DIR / "materials.json", tmp_path)
        mat = Material(
            id="test_custom", name="Test", color="#FF0000",
            k=1.0, rho=1000, cp=500, abbr="Tst",
            category="Test,Sub", note="test", is_builtin=False,
        )
        reg.add_or_update_custom(mat)
        with open(tmp_path) as f:
            data = json.load(f)
        assert data["materials"][0]["category"] == "Test,Sub"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_preserved_ids():
    reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
    expected = ["vacuum", "al6061", "cu", "ag", "au", "fe_a36", "ss304",
        "cast_iron", "titanium", "nickel", "pine", "oak", "birch", "mdf",
        "eps", "aerogel", "nat_rubber", "sil_rubber", "pvc", "nylon_66",
        "hdpe", "float_glass", "concrete", "brick", "drywall",
        "mineral_wool", "sandstone", "silicon", "fr4", "therm_paste",
        "alumina", "gaas", "solder", "air", "nitrogen", "argon",
        "hydrogen", "water", "seawater", "ethylene_glycol",
        "antifreeze_50_50", "engine_oil", "hydraulic_fluid", "gasoline",
        "r134a"]
    for eid in expected:
        assert eid in reg.builtins
