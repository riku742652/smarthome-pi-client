"""ble_scanner.py のユニットテスト"""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ble_scanner import parse_co2_sensor, post_sensor_data, scan_once


class TestParseCo2Sensor:
    """温度・湿度・CO2 をパースする parse_co2_sensor() のテスト"""

    def test_正常系_センサーデータをパースできる(self, sample_co2_mfr_data: bytes) -> None:
        """正常なメーカーデータをパースして値を取得できる"""
        result = parse_co2_sensor(sample_co2_mfr_data)
        assert result is not None
        assert result["temperature"] == 23.5
        assert result["humidity"] == 60
        assert result["co2"] == 800

    def test_正常系_負の温度をパースできる(self) -> None:
        """負の温度（冬場など）を正しくパースできる"""
        data = bytearray(16)
        data[8] = 0x05  # 小数部: 5 → 0.5°C
        data[9] = 0x17  # 整数部: 23, bit7=0 → 負
        data[10] = 0x3C
        data[13] = 0x03
        data[14] = 0x20
        result = parse_co2_sensor(bytes(data))
        assert result is not None
        assert result["temperature"] == -23.5

    def test_正常系_小数部がゼロの温度をパースできる(self) -> None:
        """整数温度（小数部ゼロ）を正しくパースできる"""
        data = bytearray(16)
        data[8] = 0x00  # 小数部: 0
        data[9] = 0x98  # 整数部: 24, bit7=1 → 正
        data[10] = 0x50
        data[13] = 0x01
        data[14] = 0x90
        result = parse_co2_sensor(bytes(data))
        assert result is not None
        assert result["temperature"] == 24.0

    def test_異常系_データが短すぎる場合はNoneを返す(self) -> None:
        """データが 15 バイト未満の場合は None を返す"""
        short_data = bytes(14)
        result = parse_co2_sensor(short_data)
        assert result is None

    def test_異常系_空のデータはNoneを返す(self) -> None:
        """空のバイト列は None を返す"""
        result = parse_co2_sensor(b"")
        assert result is None

    def test_正常系_CO2が高い値を正しくパースできる(self) -> None:
        """CO2 が高い値（2000ppm）を正しくパースできる"""
        data = bytearray(16)
        data[8] = 0x00
        data[9] = 0x98
        data[10] = 0x3C
        data[13] = 0x07  # 0x07D0 = 2000
        data[14] = 0xD0
        result = parse_co2_sensor(bytes(data))
        assert result is not None
        assert result["co2"] == 2000


class TestPostSensorData:
    """post_sensor_data() のテスト"""

    @pytest.mark.asyncio
    async def test_正常系_センサーデータをPOSTできる(self) -> None:
        """正常なレスポンスが返る場合に成功する"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        data = {"temperature": 23.5, "humidity": 60, "co2": 800}

        with (
            patch("ble_scanner.SigV4Auth") as mock_auth,
            patch("ble_scanner.Credentials"),
            patch("ble_scanner.AWSRequest") as mock_aws_req,
            patch.dict(
                "os.environ",
                {
                    "AWS_ACCESS_KEY_ID": "test-key",
                    "AWS_SECRET_ACCESS_KEY": "test-secret",
                },
            ),
        ):
            mock_aws_req.return_value.headers = {"Content-Type": "application/json"}
            mock_auth.return_value.add_auth = MagicMock()

            await post_sensor_data(
                client=mock_client,
                api_url="https://example.lambda-url.on.aws",
                aws_region="ap-northeast-1",
                device_id="test-device",
                data=data,
            )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        # URL が /data エンドポイントを指している
        assert "/data" in call_kwargs[0][0]
        # リクエストボディに deviceId が含まれている
        payload = json.loads(call_kwargs[1]["content"])
        assert payload["deviceId"] == "test-device"
        assert payload["temperature"] == 23.5

    @pytest.mark.asyncio
    async def test_異常系_HTTPエラーが発生した場合は例外を再送出する(self) -> None:
        """HTTP エラーレスポンスの場合に例外が送出される"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        data = {"temperature": 23.5, "humidity": 60, "co2": 800}

        with (
            patch("ble_scanner.SigV4Auth"),
            patch("ble_scanner.Credentials"),
            patch("ble_scanner.AWSRequest") as mock_aws_req,
            patch.dict(
                "os.environ",
                {
                    "AWS_ACCESS_KEY_ID": "test-key",
                    "AWS_SECRET_ACCESS_KEY": "test-secret",
                },
            ),
        ):
            mock_aws_req.return_value.headers = {"Content-Type": "application/json"}

            with pytest.raises(httpx.HTTPStatusError):
                await post_sensor_data(
                    client=mock_client,
                    api_url="https://example.lambda-url.on.aws",
                    aws_region="ap-northeast-1",
                    device_id="test-device",
                    data=data,
                )


class TestScanOnce:
    """scan_once() のテスト"""

    @pytest.mark.asyncio
    async def test_正常系_センサーデータが見つかった場合は辞書を返す(
        self, sample_co2_mfr_data: bytes
    ) -> None:
        """BLE スキャンでセンサーデータが見つかった場合に辞書を返す"""
        from bleak.backends.device import BLEDevice
        from bleak.backends.scanner import AdvertisementData

        # BleakScanner のコールバック機構をモックする
        # scan_once は BleakScanner コンテキストマネージャを使うため、
        # コールバックが呼ばれるタイミングをシミュレートする
        captured_callback = None

        class MockBleakScanner:
            def __init__(self, callback: Callable[..., Any]) -> None:
                nonlocal captured_callback
                captured_callback = callback

            async def __aenter__(self) -> "MockBleakScanner":
                # コンテキスト入時にコールバックを呼ぶ（センサーが見つかった状態）
                assert captured_callback is not None
                mock_device = MagicMock(spec=BLEDevice)
                mock_device.address = "AA:BB:CC:DD:EE:FF"
                mock_adv = MagicMock(spec=AdvertisementData)
                mock_adv.manufacturer_data = {0x0969: sample_co2_mfr_data}
                captured_callback(mock_device, mock_adv)
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

        with (
            patch("ble_scanner.BleakScanner", MockBleakScanner),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scan_once(scan_duration=0.1)

        assert result is not None
        assert result["temperature"] == 23.5
        assert result["humidity"] == 60
        assert result["co2"] == 800

    @pytest.mark.asyncio
    async def test_正常系_センサーが見つからない場合はNoneを返す(self) -> None:
        """スキャン時間内にセンサーが見つからない場合は None を返す"""

        class MockBleakScanner:
            def __init__(self, callback: Callable[..., Any]) -> None:
                pass

            async def __aenter__(self) -> "MockBleakScanner":
                # コールバックを一切呼ばない（センサーが見つからない）
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

        with (
            patch("ble_scanner.BleakScanner", MockBleakScanner),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scan_once(scan_duration=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_正常系_MACアドレスフィルタリングが機能する(
        self, sample_co2_mfr_data: bytes
    ) -> None:
        """device_mac が指定された場合、一致しないデバイスをスキップする"""
        from bleak.backends.device import BLEDevice
        from bleak.backends.scanner import AdvertisementData

        captured_callback = None

        class MockBleakScanner:
            def __init__(self, callback: Callable[..., Any]) -> None:
                nonlocal captured_callback
                captured_callback = callback

            async def __aenter__(self) -> "MockBleakScanner":
                assert captured_callback is not None
                # 対象外 MAC のデバイスを送信
                mock_device = MagicMock(spec=BLEDevice)
                mock_device.address = "FF:EE:DD:CC:BB:AA"
                mock_adv = MagicMock(spec=AdvertisementData)
                mock_adv.manufacturer_data = {0x0969: sample_co2_mfr_data}
                captured_callback(mock_device, mock_adv)
                return self

            async def __aexit__(self, *args: object) -> None:
                pass

        with (
            patch("ble_scanner.BleakScanner", MockBleakScanner),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await scan_once(
                scan_duration=0.1,
                device_mac="AA:BB:CC:DD:EE:FF",  # 一致しない MAC を指定
            )

        assert result is None


class TestMain:
    """main() のテスト"""

    @pytest.mark.asyncio
    async def test_異常系_必須環境変数が未設定の場合はSystemExitを送出する(self) -> None:
        """必須環境変数（API_URL 等）が設定されていない場合に SystemExit を送出する"""
        import ble_scanner

        with patch.dict(
            "os.environ",
            {
                "API_URL": "",
                "DEVICE_ID": "",
                "AWS_ACCESS_KEY_ID": "",
                "AWS_SECRET_ACCESS_KEY": "",
            },
            clear=False,
        ):
            with pytest.raises(SystemExit):
                await ble_scanner.main()

    @pytest.mark.asyncio
    async def test_正常系_POST呼び出し(self, sample_co2_mfr_data: bytes) -> None:
        """センサーデータが取得できた場合に POST を呼び出す"""
        import ble_scanner

        call_count = 0

        async def mock_scan_once(
            scan_duration: float = 5.0,
            device_mac: str | None = None,
        ) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"temperature": 23.5, "humidity": 60, "co2": 800}
            raise KeyboardInterrupt  # 2回目でループを終了させる

        async def mock_post_sensor_data(*args: Any, **kwargs: Any) -> None:
            pass

        async def mock_sleep(seconds: float) -> None:
            pass

        with (
            patch.dict(
                "os.environ",
                {
                    "API_URL": "https://example.lambda-url.on.aws",
                    "DEVICE_ID": "test-device",
                    "AWS_ACCESS_KEY_ID": "test-key",
                    "AWS_SECRET_ACCESS_KEY": "test-secret",
                },
            ),
            patch.object(ble_scanner, "scan_once", side_effect=mock_scan_once),
            patch.object(ble_scanner, "post_sensor_data", side_effect=mock_post_sensor_data),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(KeyboardInterrupt):
                await ble_scanner.main()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_正常系_センサーが見つからない場合は警告ログを記録する(self) -> None:
        """センサーデータが取得できなかった場合に警告ログを記録してループを継続する"""
        import ble_scanner

        call_count = 0

        async def mock_scan_once(
            scan_duration: float = 5.0,
            device_mac: str | None = None,
        ) -> dict | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # センサーが見つからない
            raise KeyboardInterrupt

        async def mock_sleep(seconds: float) -> None:
            pass

        with (
            patch.dict(
                "os.environ",
                {
                    "API_URL": "https://example.lambda-url.on.aws",
                    "DEVICE_ID": "test-device",
                    "AWS_ACCESS_KEY_ID": "test-key",
                    "AWS_SECRET_ACCESS_KEY": "test-secret",
                },
            ),
            patch.object(ble_scanner, "scan_once", side_effect=mock_scan_once),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            with pytest.raises(KeyboardInterrupt):
                await ble_scanner.main()

        assert call_count == 2
