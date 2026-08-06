import os
import pytest
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.utils.path_utils import PathUtils


def test_all_config_files_loaded():
    # Mô phỏng logic bootstrap từ main.py / main_window.py
    config_manager = ConfigManager()

    # Path calculation relative to this test file
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Binace_Bot

    app_json = os.path.join(base_dir, "src", "config", "app_config.json")
    user_json = os.path.join(base_dir, "src", "config", "user_config.json")
    ui_matrix_json = os.path.join(base_dir, "src", "config", "ui_matrix.json")

    # Đảm bảo các file này tồn tại trên đĩa cứng
    assert os.path.exists(app_json), f"app_config.json is missing at {app_json}!"
    assert os.path.exists(user_json), f"user_config.json is missing at {user_json}!"
    assert os.path.exists(ui_matrix_json), (
        f"ui_matrix.json is missing at {ui_matrix_json}!"
    )

    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    config_manager.load_json(ui_matrix_json)

    # Lấy toàn bộ config
    all_cfg = config_manager.get_all()

    # Kiểm tra đảm bảo các section cốt lõi đều được merge thành công
    assert "BINANCE_WS_URL" in all_cfg, "Missing basic config from app_config.json"
    assert "DEFAULT_SYMBOLS" in all_cfg, "Missing basic config from user_config.json"

    # Kiểm tra UI Matrix section
    assert "main" in all_cfg, "Missing 'main' section from ui_matrix.json!"
    assert "IDLE" in all_cfg["main"], "'main' section must define IDLE mode"

    assert "data_management" in all_cfg, (
        "Missing 'data_management' section from ui_matrix.json!"
    )
    assert "LOCKED" in all_cfg["data_management"], (
        "'data_management' section must define LOCKED mode"
    )
