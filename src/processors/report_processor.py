#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
レポート処理クラス
レポートのコンテンツを強化し、PDFを生成します。
"""

import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, Set, Tuple


class ReportProcessor:
    """レポート処理クラス"""
    
    def __init__(self, api_client, file_operations, label_manager, html_processor, helper):
        """
        初期化
        
        Args:
            api_client: OpenCTI APIクライアントインスタンス
            file_operations: ファイル操作インスタンス
            label_manager: ラベル管理インスタンス
            html_processor: HTML処理インスタンス
            helper: ヘルパーオブジェクト
        """
        self.api_client = api_client
        self.file_operations = file_operations
        self.label_manager = label_manager
        self.html_processor = html_processor
        self.helper = helper
        
        # 処理設定
        self.processed_reports = set()  # 処理済みレポートIDを保持
        self.target_report_types = []  # 処理対象レポートタイプ
        self.process_all_reports = True  # すべてのレポートを処理するフラグ
        self.processed_label = "rss-enhanced"  # 処理済みラベル
        self.debug_mode = False
        
        # PDF生成設定
        self.wkhtmltopdf_path = "/usr/bin/wkhtmltopdf"
        self.preserve_original_layout = True
        self.include_images_in_pdf = True
        self.pdf_image_quality = 85
        self.max_images_in_pdf = 10

    def set_config(self, target_types: List[str], process_all: bool, processed_label: str, 
                wkhtmltopdf_path: str, preserve_layout: bool = True, include_images: bool = True, 
                image_quality: int = 85, max_images: int = 20, ad_removal_strategy: str = "auto"):
        """
        設定を適用
        
        Args:
            target_types: 処理対象レポートタイプのリスト
            process_all: すべてのレポートを処理するフラグ
            processed_label: 処理済みラベル
            wkhtmltopdf_path: wkhtmltopdfのパス
            preserve_layout: レイアウトを保持するか
            include_images: PDFに画像を含めるかどうか
            image_quality: 画像品質（1-100）
            max_images: 含める最大画像数
            ad_removal_strategy: 広告除去戦略 ("extract", "minimal", "auto")
        """
        self.target_report_types = [t.strip().lower() for t in target_types]
        self.process_all_reports = process_all
        self.processed_label = processed_label
        self.wkhtmltopdf_path = wkhtmltopdf_path
        self.preserve_original_layout = preserve_layout
        self.include_images_in_pdf = include_images
        self.pdf_image_quality = image_quality
        self.max_images_in_pdf = max_images
        self.ad_removal_strategy = ad_removal_strategy  # 新規追加
        
        # ログに設定を出力
        if self.debug_mode:
            self.helper.log_info(f"Report processor config set:")
            self.helper.log_info(f" - Target report types: {self.target_report_types}")
            self.helper.log_info(f" - Process all reports: {self.process_all_reports}")
            self.helper.log_info(f" - Processed label: {self.processed_label}")
            self.helper.log_info(f" - wkhtmltopdf path: {self.wkhtmltopdf_path}")
            self.helper.log_info(f" - Preserve original layout: {self.preserve_original_layout}")
            self.helper.log_info(f" - Include images: {self.include_images_in_pdf}")
            self.helper.log_info(f" - Ad removal strategy: {self.ad_removal_strategy}")
            if self.include_images_in_pdf:
                self.helper.log_info(f" - Image quality: {self.pdf_image_quality}")
                self.helper.log_info(f" - Max images: {self.max_images_in_pdf}")        

    def set_debug_mode(self, debug_mode):
        """デバッグモードを設定"""
        self.debug_mode = debug_mode

    def is_report_processable(self, report: Dict[str, Any], report_types: List[str], url: Optional[str]) -> bool:
        """
        レポートが処理対象かどうか判定
        
        Args:
            report: レポートデータ
            report_types: レポートタイプのリスト
            url: レポートのURL
            
        Returns:
            bool: 処理対象の場合True
        """
        report_id = report["id"]
        report_name = report.get("name", "Unknown report")
            
        # 処理済みチェック（メモリ内）
        if report_id in self.processed_reports:
            self.helper.log_info(f"Skipping already processed report (in memory): {report_name}")
            return False
                
        # 処理済みチェック（ラベル）
        if self.label_manager.has_label(report, self.processed_label):
            self.helper.log_info(f"Skipping already processed report (label found): {report_name}")
            self.processed_reports.add(report_id)  # メモリ内キャッシュにも追加
            return False
            
        # URLが必要
        if not url:
            self.helper.log_info(f"Skipping report {report_name} - No URL found")
            return False
            
        # レポートタイプの確認（すべて処理するモードでなければ）
        if not self.process_all_reports and report_types:
            process_report = False
            for report_type in report_types:
                report_type_lower = report_type.lower() if isinstance(report_type, str) else report_type
                if report_type_lower in self.target_report_types:
                    self.helper.log_info(f"Matched report type: {report_type}")
                    process_report = True
                    break
                elif self.debug_mode:
                    self.helper.log_info(f"Debug - No match for type: {report_type_lower}")
            
            if not process_report:
                self.helper.log_info(f"Skipping report {report_name} - Not a target report type")
                return False
                
        return True

    def process_report(self, report: Dict[str, Any], report_types: List[str], url: str) -> bool:
        """
        レポートを処理
        
        Args:
            report: レポートデータ
            report_types: レポートタイプのリスト
            url: レポートURL
            
        Returns:
            bool: 処理成功時True
        """
        try:
            report_id = report["id"]
            report_name = report.get("name", "Unknown report")
            
            self.helper.log_info(f"====== Processing report: {report_name} ======")
            
            # 元のURLを固定変数として保持（上書きされないように）
            source_article_url = url
            self.helper.log_info(f"Original source article URL: {source_article_url}")
            
            # PDF出力オプションをログに出力
            pdf_mode = f"{'original layout' if self.preserve_original_layout else 'simple layout'}, {'with images' if self.include_images_in_pdf else 'text only'}"
            self.helper.log_info(f"PDF mode: {pdf_mode}")
            
            # HTML処理インスタンスを使って記事を解析
            self.helper.log_info(f"Fetching and parsing article from URL: {source_article_url}")
            article_data = self.html_processor.extract_article(source_article_url)

            if article_data and article_data.get("text"):
                # 使用された抽出方法をログに記録
                extraction_method = article_data.get("extraction_method", "unknown")
                self.helper.log_info(f"Article successfully extracted using {extraction_method} method")
                self.helper.log_info(f"Extracted content length: {len(article_data['text'])} characters")
                
                # 画像情報をログに出力（画像を含める設定の場合）
                if self.include_images_in_pdf:
                    if "images" in article_data:
                        self.helper.log_info(f"Extracted images: {len(article_data['images'])}")
                    if "top_image" in article_data and article_data["top_image"]:
                        self.helper.log_info(f"Top image: {article_data['top_image']}")

                # コンテンツの取得
                article_text = article_data.get("text", "")
                html_content = article_data.get("html", "")

                # レポートの説明を更新
                current_description = report.get("description", "")
                self.helper.log_info(f"Current description length: {len(current_description)} characters")

                # 記事のメタデータを含む説明文を作成
                article_metadata = ""
                if article_data.get("title"):
                    article_metadata += f"Title: {article_data.get('title')}\n"
                if article_data.get("publish_date"):
                    article_metadata += f"Published: {article_data.get('publish_date')}\n"
                if article_data.get("authors"):
                    article_metadata += f"Authors: {', '.join(article_data.get('authors'))}\n"

                # 説明を抽出した記事で上書き
                new_description = ""
                if article_metadata:
                    new_description += f"{article_metadata}\n"

                # テキストの長さを確認し、必要に応じて安全に切り詰める
                max_safe_length = 90000  # 安全な長さ（APIのエラーを回避するため）

                if len(article_text) > max_safe_length:
                    self.helper.log_info(f"Article text too long ({len(article_text)} chars), truncating to {max_safe_length} chars")
                    article_text = article_text[:max_safe_length] + "\n\n[... Content truncated due to length limits ...]"

                new_description += article_text

                self.helper.log_info(f"New description length: {len(new_description)} characters")

                # レポートの説明を更新
                update_fields = {"description": new_description}
                update_result = self.api_client.update_stix_domain_object(report_id, update_fields)
                
                if not update_result:
                    self.helper.log_error(f"Failed to update description for report {report_name}")
                    # 説明の更新に失敗しても処理を続行
                
                # HTMLをPDFに変換
                self.helper.log_info(f"Converting HTML to PDF ({pdf_mode})")

                pdf_content = self.html_processor.convert_html_to_pdf(
                    html_content, 
                    self.wkhtmltopdf_path,
                    source_article_url,
                    self.preserve_original_layout,
                    self.include_images_in_pdf,
                    self.pdf_image_quality,
                    self.ad_removal_strategy  # 新規追加
                )
                
                if pdf_content:
                    self.helper.log_info(f"Successfully converted HTML to PDF ({len(pdf_content)} bytes)")
                    # PDFファイル名の作成
                    safe_name = "".join([c if c.isalnum() or c in [" ", "-", "_"] else "_" for c in report_name])
                    
                    # PDFファイル名にレイアウトと画像情報を追加
                    layout_info = "original" if self.preserve_original_layout else "simple"
                    image_info = "with_images" if self.include_images_in_pdf else "text_only"
                    filename = f"{safe_name}_{layout_info}_{image_info}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    
                    # PDFファイルをアップロード & 関連付け
                    upload_result = self.file_operations.upload_and_link_file(
                        pdf_content, 
                        filename, 
                        "application/pdf", 
                        report_id
                    )
                    
                    if not upload_result:
                        self.helper.log_error(f"Failed to upload/link PDF for report {report_name}")
                        # ファイルのアップロードに失敗しても処理を続行
                else:
                    self.helper.log_error("Failed to convert HTML to PDF")
            else:
                # 抽出に失敗した場合は、元の説明を維持し、PDFも追加しない
                self.helper.log_info(f"Could not extract article content from {source_article_url}")
                self.helper.log_info("Skipping description update and PDF creation")
                
            # 処理済みラベルを追加
            label_result = self.label_manager.add_label_to_report(report_id, self.processed_label)
            if not label_result:
                self.helper.log_error(f"Failed to add label to report {report_name}")
                # ラベル追加に失敗しても処理済みとしてマーク
            
            # 処理済みとしてマーク（メモリ内）
            self.processed_reports.add(report_id)
            self.helper.log_info(f"Successfully processed report {report_name}")
            self.helper.log_info(f"====== Finished processing report: {report_name} ======")
            
            return True
                
        except Exception as e:
            self.helper.log_error(f"Error processing report: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return False

    def process_reports(self, reports: List[Dict[str, Any]], report_fetcher) -> int:
        """
        複数のレポートを処理
        
        Args:
            reports: レポートのリスト
            report_fetcher: レポート取得オブジェクト
            
        Returns:
            int: 処理したレポートの数
        """
        processed_count = 0
        
        for report in reports:
            try:
                # レポートタイプを取得
                report_types = report_fetcher.get_report_types(report)
                
                # URLを取得
                url = report_fetcher.find_url_in_report(report)
                
                # 処理対象か確認
                if not self.is_report_processable(report, report_types, url):
                    continue
                    
                # レポートを処理
                if self.process_report(report, report_types, url):
                    processed_count += 1
                    
            except Exception as e:
                report_name = report.get("name", "Unknown report")
                self.helper.log_error(f"Error processing report {report_name}: {str(e)}")
                continue
                
        return processed_count