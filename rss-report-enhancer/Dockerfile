FROM python:3.9-slim

# タイムゾーンを設定
ENV TZ=UTC

# 必要なパッケージをインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    xvfb \
    xfonts-75dpi \
    xfonts-base \
    libfontconfig1 \
    libxrender1 \
    # xauthを追加（xvfb-runに必要）
    xauth \
    # 画像処理用の追加パッケージ
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    # newspaper3kの依存関係
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    zlib1g-dev \
    libxml2-dev \
    libxslt1-dev \
    # libmagic依存関係
    libmagic1 \
    file \
    # 記事抽出に必要なツール
    wget \
    curl \
    ca-certificates \
    # DNSリゾルバーのインストール（名前解決の問題対策）
    dnsutils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# OCTIコネクタディレクトリを作成
WORKDIR /opt/opencti-connector-rss-enhancer

# 依存関係のインストール
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 画像処理関連のライブラリを追加インストール
RUN pip3 install pillow

# python-magicを明示的に再インストール
RUN pip3 uninstall -y python-magic && \
    pip3 install python-magic

# newspaper3kの依存ライブラリを明示的にインストール
RUN pip3 install nltk && \
    python3 -m nltk.downloader punkt

# スクリプトをコピー
COPY . .

# 設定ファイルが存在することを確認
RUN if [ ! -f config.yml ]; then cp config.yml.sample config.yml; fi

# entrypoint.shに実行権限を付与
RUN chmod +x entrypoint.sh

# wkhtmltopdfのテスト実行
RUN echo "Testing wkhtmltopdf" && \
    xvfb-run -a wkhtmltopdf --version

# メモリ設定を調整
ENV NODE_OPTIONS=--max_old_space_size=4096

ENTRYPOINT ["./entrypoint.sh"]