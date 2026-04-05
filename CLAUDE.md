# Agent Guide - Smarthome Pi Client

このファイルは、エージェント（Claude Code）がこのリポジトリで作業する際のナビゲーションマップです。
詳細な指示ではなく、必要な情報への**ポインタ**として機能します。

## プロジェクト概要

SwitchBot CO2センサー（WoSensorTHPCO2）の BLE アドバタイズメントを Raspberry Pi 上でスキャンし、
smarthome Lambda API にデータを送信する Python クライアント。

## コア原則

このプロジェクトは**ハーネスエンジニアリング**の原則に従います：

1. **手書きコード禁止** - すべてのコードはエージェントによって生成される
2. **エージェントの認識可能性最優先** - コンテキスト内にないものは存在しない
3. **構造化されたドキュメント** - すべての知識はリポジトリ内にバージョン管理される
4. **機械的な検証** - リンター、テスト、CIで不変条件を適用する

詳細: `HARNESS_WORKFLOW.md`

## リポジトリナビゲーション

### アーキテクチャ
- `ARCHITECTURE.md` - システム全体のアーキテクチャマップ
- `docs/design-docs/` - 設計決定とその根拠

### 計画と実行
- `docs/exec-plans/active/` - 現在進行中の実行計画
- `docs/exec-plans/completed/` - 完了した実行計画とその学び

### コードベース
- `ble_scanner.py` - メインスクリプト（BLE スキャン + Lambda API 送信）
- `tests/` - テストコード

## 開発コマンド

```bash
# 依存関係インストール
uv sync --all-groups

# テスト実行
uv run pytest tests/ -v --cov=ble_scanner --cov-report=term-missing

# リント
uv run ruff check .

# フォーマット
uv run ruff format .

# 型チェック
uv run pyright .

# まとめて実行
make all
```

## エージェントへの期待事項

### 必ず実行すること
- コンテキスト内の既存パターンに従う
- すべての変更にテストを含める（カバレッジ 85% 以上）
- ruff lint, pyright, pytest をパスすることを確認する
- 変更内容を `docs/exec-plans/` に記録する

### 避けること
- 外部の知識やドキュメントへの依存（すべてリポジトリ内に記録）
- BLE ハードウェアや AWS 認証に依存したテスト（モックを使用）
- `.env` ファイルのコミット（秘密情報澏洩防止）

## タスクの完了条件

実装タスクは以下がすべて揃って初めて完了とする:

1. **PR 作成**
2. **CI が通ること**（全チェック green）
3. **マージ**（`gh pr merge <PR番号> --squash` で実行）

## ドキュメント言語ルール

- **説明文・コメント・ドキュメントはすべて日本語で記述する**
- コードブロック内のコード、コマンド、ファイルパス、変数名はそのまま（英語）
- 技術用語（Lambda、DynamoDB、SigV4 等）はそのまま使用する
