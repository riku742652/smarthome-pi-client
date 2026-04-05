"""pytest 共通フィクスチャ"""
import pytest


@pytest.fixture
def sample_co2_mfr_data() -> bytes:
    """
    SwitchBot CO2センサーのサンプル BLE メーカーデータ。
    温度: 23.5°C, 湿度: 60%, CO2: 800ppm を表す。
    """
    # 16 バイトのメーカーデータ
    # byte8: 0x05 (小数部 5 = 0.5°C)
    # byte9: 0x97 (整数部 23, bit7=1 → 正)
    # byte10: 0x3C (湿度 60%)
    # byte13-14: 0x0320 (CO2 800ppm)
    data = bytearray(16)
    data[8] = 0x05   # 小数部: 5 → 0.5°C
    data[9] = 0x97   # 整数部: 23, 正符号
    data[10] = 0x3C  # 湿度: 60%
    data[13] = 0x03  # CO2 上位バイト
    data[14] = 0x20  # CO2 下位バイト (0x0320 = 800)
    return bytes(data)
