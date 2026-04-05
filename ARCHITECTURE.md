# Architecture Overview - Smarthome Pi Client

このドキュメントは、pi-client のアーキテクチャを説明します。

## システム概要

Raspberry Pi 上で動作する Python スクリプトが、SwitchBot CO2センサーの BLE アドバタイズメントを
スキャンし、AWS Lambda API にデータを送信します。

## データフロー

```
SwitchBot CO2センサー
    ↓ (BLE advertisement, 60秒間隔)
Raspberry Pi (ble_scanner.py)
    ↓ (HTTP POST with SigV4 署名, timeout=10秒)
Lambda API IAM Function URL (smarthome リポジトリ)
    ↓ (PUT request)
DynamoDB
```

**API コントラクト**: `POST /data`
- リクエスト: `{"deviceId": "...", "temperature": float, "humidity": int, "co2": int}`
- レスポンス: HTTP 201 Created
- 認証: AWS IAM（SigV4 署名）
- Lambda URL: `.env` の `API_URL` から取得

**関連リポジトリ**: https://github.com/riku742652/smarthome

## コードアーキテクチャ

### `ble_scanner.py`

単一ファイル構成（300行以内）。以下の関数で構成される：

| 関数 | 責務 |
|------|------|
| `parse_co2_sensor(mfr_data)` | BLE メーカーデータをパース → センサー値を返す |
| `post_sensor_data(client, ...)` | センサーデータを Lambda API に SigV4 署名付きで POST |
| `scan_once(scan_duration, device_mac)` | BLE スキャンを１回実行 → センサーデータを返す |
| `main()` | メインループ（スキャン → POST を繰り返す） |

### 認証アーキテクチャ

- `smarthome` リポジトリの Terraform が Raspberry Pi 用 IAM User を作成
- AccessKey / SecretKey を `.env` ファイルに設定
- `botocore` で SigV4 署名を生成
- Lambda Function URL の `authorization_type = "AWS_IAM"` で認証

### 依存関係

```
ble_scanner.py
├── bleak          # BLE スキャナー（非同期）
├── botocore       # AWS SigV4 署名生成
└── httpx          # 非同期 HTTP クライアント
```

## デプロイ環境

- **OS**: Raspberry Pi OS (64-bit)
- **Python**: 3.11+
- **パッケージマネージャー**: uv
- **サービス管理**: systemd (`systemd/smarthome-ble.service`)
- **実行ユーザー**: `pi`
- **ワーキングディレクトリ**: `/home/pi/smarthome-pi-client`

## 不変条件

1. `.env` ファイルは git に含めない（秘密情報）
2. テストは BLE ハードウェアや AWS に依存しない（モックを使用）
3. テストカバレッジは 85% 以上
4. ruff lint, pyright, pytest がすべて通ること

## 変更履歴

- 2026-04-05: 初期アーキテクチャ設計（smarthome リポジトリから切り出し）
