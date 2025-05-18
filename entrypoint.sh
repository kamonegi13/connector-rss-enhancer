#!/bin/sh

# 専用のランタイムディレクトリを作成し、適切なパーミッションを設定
mkdir -p /tmp/runtime-$(id -u)
chmod 700 /tmp/runtime-$(id -u)
export XDG_RUNTIME_DIR=/tmp/runtime-$(id -u)

# xvfbを使用してヘッドレスブラウザ環境を提供
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# ネットワーク接続の待機
echo "Waiting for network..."
sleep 5

# コネクタのルートディレクトリに移動
cd /opt/opencti-connector-rss-enhancer

# 実行ディレクトリをsrcに変更
cd src

# 環境変数を設定
echo "Current directory: $(pwd)"
echo "Starting connector with image support..."

# コネクタを起動
exec python3 connector.py