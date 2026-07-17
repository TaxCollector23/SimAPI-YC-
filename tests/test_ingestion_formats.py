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
