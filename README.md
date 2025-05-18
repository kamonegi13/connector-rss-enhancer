OpenCTI RSS Report Enhancerコネクタの概要
提供されたコードを分析すると、これはOpenCTIのRSS Report Enhancerコネクタというツールのソースコードです。このコネクタは、OpenCTIプラットフォームに取り込まれたRSSフィードやレポートを強化する機能を提供します。

主な機能

レポート取得: OpenCTIからレポートを自動的に取得
コンテンツ抽出: レポートに含まれるURLから記事コンテンツを抽出
PDF変換: 抽出したコンテンツを高品質なPDFに変換
メタデータ強化: 元のレポート説明を抽出したコンテンツで強化
ファイル関連付け: 生成したPDFをOpenCTIの元レポートに添付
処理追跡: 処理済みレポートに特定のラベルを付与

アーキテクチャ
コネクタは以下のモジュールで構成されています：

RssReportEnhancerConnector: メインコネクタクラス
ConfigManager: 設定管理
HTMLProcessor: HTML処理とPDF変換
LabelManager: ラベル管理
ReportFetcher: レポート取得
ReportProcessor: レポート処理
OpenCTIApi: API操作
FileOperations: ファイル操作

主要な特徴

複数の抽出方法: 標準、直接wget、高度なブラウザエミュレーションなど複数の方法でコンテンツを抽出
レイアウト保持: 元の記事のレイアウトを保持したPDF変換
広告除去: 広告などの不要な要素を自動的に除去
画像処理: コンテンツ内の画像をPDFに含める設定
エラー耐性: 各処理ステップでの複数のフォールバック方法の実装
WordPress対応: WordPressサイトを自動検出して最適化処理

使用方法
このコネクタはOpenCTI 6.6.9互換で、設定ファイル（config.yml）または環境変数で設定可能です。主な設定項目：

TARGET_REPORT_TYPES: 処理対象のレポートタイプ
PROCESS_ALL_REPORTS: すべてのレポートを処理するかのフラグ
PROCESSED_LABEL: 処理済みレポートに付けるラベル
PRESERVE_ORIGINAL_LAYOUT: 元のレイアウトを保持するか
INCLUDE_IMAGES_IN_PDF: PDFに画像を含めるか
AD_REMOVAL_STRATEGY: 広告除去戦略（"auto", "extract", "minimal"）

実装の特徴

モジュール化されたアーキテクチャ
複数のAPIアクセス方法のサポート（GraphQL、REST、Helper API）
詳細なログ出力
段階的な処理とフォールバックメカニズム
安全なファイル処理（一時ファイルの自動クリーンアップ）

構成ファイル概要
1. Dockerfile
コネクタの実行環境を構築するためのDockerfile:

Python 3.9 Slimをベースイメージとして使用
wkhtmltopdf、Xvfb、画像処理ライブラリなどの必要なパッケージをインストール
newspaper3kやその他の依存ライブラリをインストール
メモリ設定の最適化（Node.jsのメモリ上限を4GBに設定）

2. docker-compose.override.yml
OpenCTI環境に統合するための設定:

OpenCTIサーバーとの接続設定
コネクタの基本設定（名前、スコープ、ログレベルなど）
レポート処理設定（処理間隔、対象レポートタイプなど）
PDF生成オプション
メモリ制限（1GB）とシェアードメモリ（2GB）設定

3. config.yml.sample
環境変数の代わりに使用できる設定ファイルのサンプル:

OpenCTI接続設定
コネクタの基本情報
レポート処理の詳細設定
PDF生成オプション
広告除去戦略オプション

4. entrypoint.sh
コンテナ起動時の初期化スクリプト:

ヘッドレスブラウザ環境（Xvfb）のセットアップ
ディレクトリ移動と環境設定
コネクタ起動

5. requirements.txt
必要なPythonライブラリのリスト:

pycti 6.6.7（OpenCTI Python クライアント）
newspaper3k（記事抽出ライブラリ）
pdfkit（PDF生成ライブラリ）
その他の依存ライブラリ

主要な設定オプション
基本設定

CONNECTOR_NAME: コネクタの名前
CONNECTOR_SCOPE: コネクタの対象範囲（Report）
WAIT_TIME: 処理サイクルの間隔（秒）

レポート処理設定

TARGET_REPORT_TYPES: 処理対象のレポートタイプ（カンマ区切り）
PROCESS_ALL_REPORTS: すべてのレポートを処理するかのフラグ
PROCESSED_LABEL: 処理済みレポートに付けるラベル名
PROCESSED_LABEL_COLOR: ラベルの色（16進数カラーコード）

PDF生成オプション

PRESERVE_ORIGINAL_LAYOUT: 元のレイアウトを保持するか
INCLUDE_IMAGES_IN_PDF: PDFに画像を含めるか
PDF_IMAGE_QUALITY: PDF内の画像品質（1-100）
MAX_IMAGES_IN_PDF: 含める最大画像数

広告除去戦略

AD_REMOVAL_STRATEGY: 以下の3つのモードから選択

extract: コンテンツのみを抽出して新しいHTMLを生成
minimal: 基本的な広告のみ除去し、レイアウトを保持
auto: HTMLの複雑さに基づいて自動選択（デフォルト）



起動時設定

PROCESS_ALL_ON_START: 起動時に全レポートをチェックするか
MAX_REPORTS_ON_START: 起動時に処理する最大レポート数（0=無制限）

導入方法

前提条件:

Docker と Docker Compose がインストールされていること
OpenCTI がすでに稼働していること


インストール手順:

コネクタのソースコードをダウンロードまたはクローン
config.yml.sample をコピーして config.yml を作成し、設定を編集
または docker-compose.override.yml を編集して環境変数を設定
Docker Compose を使用してコンテナをビルド・起動


Docker Compose を使用した起動:
bashdocker-compose -f docker-compose.yml -f docker-compose.override.yml up -d connector-rss-enhancer

ログの確認:
bashdocker-compose logs -f connector-rss-enhancer


技術的な注意点

メモリ使用量:

コンテナのメモリ制限は1GB、シェアードメモリは2GBに設定されています
大量のレポートを処理する場合はメモリ制限の調整が必要かもしれません


wkhtmltopdf と Xvfb:

PDFレンダリングには wkhtmltopdf が使用されています
ヘッドレス環境でブラウザレンダリングをシミュレートするために Xvfb が使用されています


広告除去戦略:

複雑なレイアウトのサイトでは extract モードが最も安定しています
シンプルなレイアウトでは minimal モードが元のデザインを保持します
auto モードは両方のバランスを自動調整します


起動時処理:

PROCESS_ALL_ON_START=true に設定すると、起動時に既存の全レポートを処理します
大量のレポートがある場合は MAX_REPORTS_ON_START で制限を設定することをお勧めします



このコネクタを使用すると、OpenCTIに取り込まれたRSSフィードやレポートを自動的に強化し、コンテンツをPDF形式で保存して参照できるようになります。特に外部サイトのコンテンツが変更されたり削除されたりする可能性がある場合に有用です。
