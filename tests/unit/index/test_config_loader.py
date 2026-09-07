from pathlib import Path

import pytest

from src.airfare_ml.index.config_loader import (
    IndexConfig,
    load_index_config,
)


CONFIG_PATH = Path("config/index_methodology.yaml")


def test_load_index_config():
    config = load_index_config(CONFIG_PATH)

    assert isinstance(config, IndexConfig)

    assert config.base_value == 100.0
    assert config.base_date == "2026-09-04"

    assert config.representative_fare_method == "median"
    assert config.route_weighting == "equal"
    assert config.lead_time_weighting == "equal"

    assert config.advance_windows == (
        1,
        7,
        15,
        30,
        45,
    )

    assert len(config.route_universe) == 20

    assert config.minimum_route_coverage_ratio == 1.0
    assert config.minimum_stratum_coverage_ratio == 1.0

    assert config.official_weights_used is False


def test_missing_config_raises():
    with pytest.raises(FileNotFoundError):
        load_index_config(
            "config/does_not_exist.yaml"
        )


def test_invalid_coverage_ratio(tmp_path):
    config_path = tmp_path / "invalid.yaml"

    config_path.write_text(
        """
index:
  base_value: 100
  base_date: "2026-09-04"
  representative_fare_method: "median"
  route_weighting: "equal"
  lead_time_weighting: "equal"

advance_windows:
  - 1
  - 7

coverage:
  require_complete_routes: true
  require_complete_strata: true
  minimum_route_coverage_ratio: 1.5
  minimum_stratum_coverage_ratio: 1.0

route_universe:
  - DEL_BOM

weights:
  official_weights_used: false
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_index_config(config_path)