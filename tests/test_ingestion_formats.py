"""Multi-format ingestion: YAML, TOML, TXT, Markdown on top of CSV/JSON/VTK/OpenFOAM."""
import pytest

from core.ingestion import DataIngester

ing = DataIngester()


def test_yaml_trial_list():
    data = """
trials:
  - velocity: 150
    pressure: 101325
    temperature: 300
  - velocity: 200
    pressure: 95000
    temperature: 280
"""
    df, meta = ing.ingest(data, filename="simulation.yaml")
    assert meta["detected_format"] == "yaml"
    assert len(df) == 2
    assert set(["velocity", "pressure", "temperature"]).issubset(df.columns)


def test_yaml_bare_list():
    data = "- velocity: 150\n  pressure: 101325\n- velocity: 200\n  pressure: 95000\n"
    df, meta = ing.ingest(data, filename="simulation.yml")
    assert meta["detected_format"] == "yaml"
    assert len(df) == 2


def test_toml_array_of_tables():
    data = """
[[trial]]
velocity = 150
pressure = 101325
temperature = 300

[[trial]]
velocity = 200
pressure = 95000
temperature = 280
"""
    df, meta = ing.ingest(data, filename="simulation.toml")
    assert meta["detected_format"] == "toml"
    assert len(df) == 2
    assert df["velocity"].tolist() == [150, 200]


def test_txt_key_value_blocks():
    data = "velocity: 150\npressure: 101325\ntemperature: 300\n\nvelocity: 200\npressure: 95000\ntemperature: 280\n"
    df, meta = ing.ingest(data, filename="simulation.txt")
    assert meta["detected_format"] == "txt"
    assert len(df) == 2
    assert df["velocity"].dtype.kind in "if"


def test_markdown_table():
    data = (
        "# Simulation results\n\n"
        "| velocity | pressure | temperature |\n"
        "|----------|----------|-------------|\n"
        "| 150      | 101325   | 300         |\n"
        "| 200      | 95000    | 280         |\n"
    )
    df, meta = ing.ingest(data, filename="simulation.md")
    assert meta["detected_format"] == "md"
    assert len(df) == 2
    assert df["pressure"].tolist() == [101325, 95000]


def test_format_hint_overrides_detection():
    data = "velocity = 150\npressure = 101325\n"
    df, meta = ing.ingest(data, format_hint="toml")
    assert meta["detected_format"] == "toml"
    assert len(df) == 1


def test_unsupported_format_raises():
    with pytest.raises(ValueError):
        ing.ingest("some data", format_hint="pdf")


# ── Alias-collision regressions ───────────────────────────────────────
# `Sr` (Strouhal number) was silently renamed to `degree_of_saturation`
# because a later dict entry overwrote the earlier alias. Fluid columns
# then hit the geomech saturation bound.
def test_sr_stays_strouhal_number():
    from core.ingestion import DataIngester
    ing = DataIngester()
    df, meta = ing.ingest("Sr,velocity\n0.21,15.0\n0.22,15.5\n", filename="fluid.csv")
    assert "strouhal_number" in df.columns, (
        f"Sr alias regressed: {list(df.columns)}"
    )
    assert "degree_of_saturation" not in df.columns


# `E` / `H` uppercase-only aliases were unreachable through the
# case-collapsing lookup; column `E` (electric field) was silently
# renamed to `oswald_efficiency`, `H` to `enthalpy`.
def test_electric_and_magnetic_fields_are_not_silently_relabelled():
    from core.ingestion import DataIngester
    ing = DataIngester()
    df, _ = ing.ingest("E,H\n1e3,4.0\n1.1e3,4.1\n", filename="em.csv")
    # Either they stay as-is (safe) or resolve to the correct EM
    # canonical name. What must NOT happen: they become the
    # aerodynamics/thermo names they used to be.
    assert "oswald_efficiency" not in df.columns
    assert "enthalpy" not in df.columns


# _coerce_numeric was silently dropping unparseable strings ("NA",
# "1,234", "3.2e-4 Pa"). A downstream `repair_short_nan_gaps` (or ML
# training run) would then see interpolated numbers where the source
# had labels the user cared about.
def test_coerce_numeric_preserves_column_when_any_cell_is_unparseable():
    from core.ingestion import _coerce_numeric
    import pandas as pd
    s = pd.Series(["1.0", "2.0", "NA", "4.0"])
    out = _coerce_numeric(s)
    # "NA" is a real value the caller must see, not a NaN to interpolate.
    assert (out == s).all(), f"lost 'NA' during coerce: {out.tolist()}"
    # But a fully-numeric column still coerces.
    s2 = pd.Series(["1.0", "2.0", "3.0"])
    assert pd.api.types.is_numeric_dtype(_coerce_numeric(s2))
