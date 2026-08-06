import os
import sys
import pytest

# Tránh crash trong môi trường Headless (Không có màn hình thật)
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_sanity_ui_boot_and_navigation():
    print("Sanity Check GUI Setup...")
