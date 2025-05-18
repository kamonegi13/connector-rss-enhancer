#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RSS Report Enhancer - OpenCTI Connector
レポートからコンテンツを抽出し、PDFとして保存するコネクタです。
"""

import os
import time
import traceback
import yaml
import sys

# 絶対インポートが機能するようにパスを設定
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# pycti をインポート
from pycti import OpenCTIConnectorHelper, get_config_variable

# 自作モジュールを絶対インポート
from src.utils.config_manager import ConfigManager
from src.utils.html_processor import HTMLProcessor
from src.api.opencti_api import OpenCTIApi
from src.api.file_operations import FileOperations
from src.processors.label_manager import LabelManager
from src.processors.report_fetcher import ReportFetcher
from src.processors.report_processor import ReportProcessor


class RssReportEnhancerConnector:
    """RSS Report Enhancer Connector"""

    def __init__(self):
        """コネクタを初期化"""
        # 設定ファイルのパスを構築
        config_file_path = os.path.dirname(os.path.abspath(__file__)) + "/../config.yml"
        
        # 設定ファイルの読み込み
        config = {}
        if os.path.isfile(config_file_path):
            with open(config_file_path, 'r') as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
        
        # OpenCTI ヘルパー初期化 - 必要な設定値を提供
        self.helper = OpenCTIConnectorHelper(config)
        
        # 設定マネージャをインスタンス化
        self.config_manager = ConfigManager(config_file_path)
        
        # 設定パラメータ読み込み
        self._load_configuration()
        
        # 各モジュールの初期化
        self._initialize_modules()
        
        # 設定情報をログに出力
        self._log_configuration()
        
        # 処理済みラベルが存在することを確認
        self.label_manager.ensure_label_exists(self.processed_label, self.processed_label_color)

    def _load_configuration(self):
        """設定を読み込む"""
        # OpenCTI URL と API トークン
        self.opencti_url = self.config_manager.get_value(
            "OPENCTI_URL", ["opencti", "url"]
        )
        self.opencti_token = self.config_manager.get_value(
            "OPENCTI_TOKEN", ["opencti", "token"]
        )
        
        # 待機時間設定（整数に変換）
        self.wait_time = self.config_manager.get_value(
            "WAIT_TIME", ["connector", "wait_time"], 60, is_number=True
        )
        
        # wkhtmltopdfのパス
        self.wkhtmltopdf_path = self.config_manager.get_value(
            "WKHTMLTOPDF_PATH", ["connector", "wkhtmltopdf_path"], "/usr/bin/wkhtmltopdf"
        )
        
        # レポートタイプフィルター設定
        self.target_report_types = self.config_manager.get_value(
            "TARGET_REPORT_TYPES", ["connector", "target_report_types"], 
            "external-import,threat-report,rss-feed,rss,rss-report", is_list=True
        )
        
        # すべてのレポートを処理するかのフラグ
        self.process_all_reports = self.config_manager.get_value(
            "PROCESS_ALL_REPORTS", ["connector", "process_all_reports"], 
            True, is_boolean=True
        )
        
        # 処理済みラベル設定
        self.processed_label = self.config_manager.get_value(
            "PROCESSED_LABEL", ["connector", "processed_label"], 
            "rss-enhanced"
        )
        
        # ラベルの色
        self.processed_label_color = self.config_manager.get_value(
            "PROCESSED_LABEL_COLOR", ["connector", "processed_label_color"], 
            "#ff9900"
        )
        
        # PDFオプション：元のレイアウトを保持するか
        self.preserve_original_layout = self.config_manager.get_value(
            "PRESERVE_ORIGINAL_LAYOUT", ["connector", "preserve_original_layout"], 
            True, is_boolean=True
        )
        
        # PDFオプション：画像を含めるか
        self.include_images_in_pdf = self.config_manager.get_value(
            "INCLUDE_IMAGES_IN_PDF", ["connector", "include_images_in_pdf"], 
            True, is_boolean=True
        )
        
        # PDF画像品質設定
        self.pdf_image_quality = self.config_manager.get_value(
            "PDF_IMAGE_QUALITY", ["connector", "pdf_image_quality"], 
            85, is_number=True
        )
        
        # 最大画像数
        self.max_images_in_pdf = self.config_manager.get_value(
            "MAX_IMAGES_IN_PDF", ["connector", "max_images_in_pdf"], 
            20, is_number=True
        )
        
        # デバッグモード
        self.debug_mode = self.config_manager.get_value(
            "DEBUG_MODE", ["connector", "debug_mode"], 
            False, is_boolean=True
        )

        # 起動時全レポート処理の設定を追加
        self.process_all_on_start = self.config_manager.get_value(
            "PROCESS_ALL_ON_START", ["connector", "process_all_on_start"], 
            False, is_boolean=True
        )
        
        # 起動時に処理する最大レポート数（0=無制限）
        self.max_reports_on_start = self.config_manager.get_value(
            "MAX_REPORTS_ON_START", ["connector", "max_reports_on_start"], 
            100, is_number=True
        )

        # 広告除去戦略
        self.ad_removal_strategy = self.config_manager.get_value(
            "AD_REMOVAL_STRATEGY", ["connector", "ad_removal_strategy"], 
            "auto"
        )
        

    def _initialize_modules(self):
        """モジュールを初期化"""
        # OpenCTI API クライアント
        self.api_client = OpenCTIApi(self.opencti_url, self.opencti_token, self.helper)
        self.api_client.set_debug_mode(self.debug_mode)
        
        # HTML プロセッサ
        self.html_processor = HTMLProcessor(helper=self.helper)
        
        # ファイル操作
        self.file_operations = FileOperations(
            self.opencti_url, 
            self.opencti_token, 
            self.api_client, 
            self.helper
        )
        
        # ラベル管理
        self.label_manager = LabelManager(self.api_client, self.helper)
        
        # レポート取得
        self.report_fetcher = ReportFetcher(
            self.opencti_url, 
            self.opencti_token, 
            self.api_client, 
            self.helper
        )
        self.report_fetcher.set_debug_mode(self.debug_mode)
        
        # レポート処理
        self.report_processor = ReportProcessor(
            self.api_client, 
            self.file_operations, 
            self.label_manager,
            self.html_processor,
            self.helper
        )
        self.report_processor.set_debug_mode(self.debug_mode)
        self.report_processor.set_config(
            self.target_report_types,
            self.process_all_reports,
            self.processed_label,
            self.wkhtmltopdf_path,
            self.preserve_original_layout,
            self.include_images_in_pdf,
            self.pdf_image_quality,
            self.max_images_in_pdf,
            self.ad_removal_strategy  # 新規追加
        )

    def _log_configuration(self):
        """設定情報をログに出力"""
        self.helper.log_info(f"Connector initialized for OpenCTI 6.6.9")
        self.helper.log_info(f"Target report types: {self.target_report_types}")
        self.helper.log_info(f"Process all reports: {self.process_all_reports}")
        self.helper.log_info(f"Processed label: {self.processed_label}")
        self.helper.log_info(f"PDF options: preserve_layout={self.preserve_original_layout}, include_images={self.include_images_in_pdf}")
        self.helper.log_info(f"Ad removal strategy: {self.ad_removal_strategy}")  # 新規追加
        if self.include_images_in_pdf:
            self.helper.log_info(f"PDF image quality: {self.pdf_image_quality}, max_images: {self.max_images_in_pdf}")
        self.helper.log_info(f"Debug mode: {self.debug_mode}")
        self.helper.log_info(f"Process all reports on start: {self.process_all_on_start}")
        if self.process_all_on_start:
            max_reports_text = "unlimited" if self.max_reports_on_start == 0 else str(self.max_reports_on_start)
            self.helper.log_info(f"Max reports to process on start: {max_reports_text}")

    def start(self):
        """コネクタを開始"""
        self.helper.log_info("Starting RSS Report Enhancer connector (v2.0)")
        
        # APIテスト
        self.helper.log_info("Testing API connection...")
        if not self.api_client.test_api_connection():
            self.helper.log_error("Could not connect to OpenCTI API properly")
            
        # 起動時全レポート処理オプションが有効な場合
        if self.process_all_on_start:
            self._process_all_reports_on_start()
            self.helper.log_info("Switching to normal operation mode - monitoring latest reports")
        
        # メインループ
        while True:
            try:
                self.helper.log_info("=== Starting processing cycle ===")
                
                # レポートを取得
                self.helper.log_info("Fetching reports...")
                reports = self.report_fetcher.get_latest_reports(limit=20)
                
                if not reports:
                    self.helper.log_info("No reports found with primary method, trying alternative...")
                    reports = self.report_fetcher.get_reports_alternative(limit=20)
                
                # 報告数を記録
                report_count = len(reports) if reports else 0
                self.helper.log_info(f"Found {report_count} reports to process")
                
                if reports:
                    # レポートごとの処理を詳細に記録
                    for i, report in enumerate(reports):
                        report_name = report.get("name", f"Report #{i+1}")
                        self.helper.log_info(f"Processing report {i+1}/{report_count}: {report_name}")
                    
                    # レポートを処理
                    processed_count = self.report_processor.process_reports(reports, self.report_fetcher)
                    self.helper.log_info(f"Successfully processed {processed_count} out of {report_count} reports")
                else:
                    self.helper.log_info("No reports found for processing")
                
                self.helper.log_info("=== Completed processing cycle ===")
                
                # 処理間隔を空ける
                wait_seconds = int(self.wait_time)
                self.helper.log_info(f"Waiting {wait_seconds} seconds before next check")
                time.sleep(wait_seconds)
                
            except Exception as e:
                self.helper.log_error(f"Error in main loop: {str(e)}")
                self.helper.log_error(traceback.format_exc())
                # エラー発生時に60秒待機
                self.helper.log_info("Waiting 60 seconds after error before retry")
                time.sleep(60)

    def _process_all_reports_on_start(self):
        """起動時に全レポートを確認し処理"""
        try:
            self.helper.log_info("=== Starting startup scan of all reports ===")
            
            # バッチサイズを設定（100件ずつ処理）
            batch_size = 100
            max_reports = self.max_reports_on_start
            
            # 全レポート取得（max_reports=0の場合は制限なし）
            max_text = "unlimited" if max_reports == 0 else str(max_reports)
            self.helper.log_info(f"Fetching reports (max: {max_text})...")
            reports = self.report_fetcher.get_all_reports(
                batch_size=batch_size, 
                max_count=max_reports
            )
            
            # 報告数を記録
            report_count = len(reports) if reports else 0
            self.helper.log_info(f"Found {report_count} reports for startup processing")
            
            if reports:
                # 進捗を表示するカウンター
                processed_count = 0
                already_processed_count = 0
                skipped_count = 0
                
                for i, report in enumerate(reports):
                    report_name = report.get("name", f"Report #{i+1}")
                    
                    # 処理済みかどうか確認
                    if self.label_manager.has_label(report, self.processed_label):
                        already_processed_count += 1
                        if i % 50 == 0 or i+1 == report_count:  # 50件ごとまたは最後のレポートで進捗ログ
                            self.helper.log_info(f"Progress: {i+1}/{report_count} - Skipping already processed report: {report_name}")
                        continue
                    
                    # URLを取得
                    url = self.report_fetcher.find_url_in_report(report)
                    if not url:
                        skipped_count += 1
                        if i % 50 == 0 or i+1 == report_count:
                            self.helper.log_info(f"Progress: {i+1}/{report_count} - No URL found for report: {report_name}")
                        continue
                    
                    # レポートタイプを取得
                    report_types = self.report_fetcher.get_report_types(report)
                    
                    # 処理が必要か確認（process_all_reportsがTrueの場合は常に処理）
                    if not self.process_all_reports:
                        process_report = False
                        for report_type in report_types:
                            report_type_lower = report_type.lower() if isinstance(report_type, str) else report_type
                            if report_type_lower in self.target_report_types:
                                process_report = True
                                break
                        
                        if not process_report:
                            skipped_count += 1
                            if i % 50 == 0 or i+1 == report_count:
                                self.helper.log_info(f"Progress: {i+1}/{report_count} - Skipping non-target report type: {report_name}")
                            continue
                    
                    # 進捗ログ
                    self.helper.log_info(f"Processing report {i+1}/{report_count}: {report_name}")
                    
                    # レポートを処理
                    if self.report_processor.process_report(report, report_types, url):
                        processed_count += 1
                    
                    # 処理間隔を少し空ける（サーバー負荷低減のため）
                    time.sleep(0.5)
                
                self.helper.log_info(f"Startup processing summary: {processed_count} processed, {already_processed_count} already processed, {skipped_count} skipped, out of {report_count} total reports")
            else:
                self.helper.log_info("No reports found for startup processing")
            
            self.helper.log_info("=== Completed startup scan of all reports ===")
                
        except Exception as e:
            self.helper.log_error(f"Error in startup processing: {str(e)}")
            self.helper.log_error(traceback.format_exc())

if __name__ == "__main__":
    try:
        connector = RssReportEnhancerConnector()
        connector.start()
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        traceback.print_exc()