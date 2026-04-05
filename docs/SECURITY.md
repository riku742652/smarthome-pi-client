# Security Requirements - Smarthome Pi Client

## 認証情報管理

- AWS IAM 認証情報は `.env` ファイルにのみ保存
- `.env` は `.gitignore` で除外（git に含めない）
- `.env.example` で設定項目を示す（値はダミー）

## アクセス制御

- Raspberry Pi 専用の IAM User（最小権限）
- Lambda Function URL は IAM 認証必須
- SigV4 署名でリクエストを認証

## ログ

- 認証情報をログに出力しない
- センサー値のみをログに記録
