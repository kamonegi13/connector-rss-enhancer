#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ファイル操作クラス
OpenCTIへのファイルアップロードと関連付けを担当します。
"""

import os
import json
import requests
import traceback
import tempfile
from typing import Dict, Any, Optional


class FileOperations:
    """ファイル操作とアップロード機能 - ImportDocumentのみ使用"""
    
    def __init__(self, opencti_url, opencti_token, api_client, helper):
        """
        初期化
        
        Args:
            opencti_url: OpenCTI API URL
            opencti_token: APIトークン
            api_client: OpenCTI APIクライアントインスタンス
            helper: ヘルパーオブジェクト
        """
        self.opencti_url = opencti_url
        self.opencti_token = opencti_token
        self.api_client = api_client
        self.helper = helper
        # アップロード用の一時ファイル追跡
        self.temp_files = []

    def __del__(self):
        """デストラクタ - 残っている一時ファイルをクリーンアップ"""
        self._cleanup_all_temp_files()

    def upload_and_link_file(self, file_content: bytes, file_name: str, mime_type: str, report_id: str) -> bool:
        """
        ファイルをアップロードしてレポートに関連付ける
        ImportDocumentパイプラインのみを使用
        
        Args:
            file_content: ファイルの内容（バイナリ）
            file_name: ファイル名
            mime_type: MIMEタイプ
            report_id: 関連付けるレポートID
            
        Returns:
            bool: 処理成功の場合True
        """
        temp_path = None
        try:
            self.helper.log_info(f"Uploading file: {file_name} via ImportDocument API")
            
            # 一時ファイルに保存
            temp_path = self._save_to_temp_file(file_content, file_name)
            
            if not temp_path:
                self.helper.log_error("Failed to create temporary file")
                return False
            
            # ImportDocument APIでファイルをアップロード
            result = self._upload_via_import_document(temp_path, file_name, mime_type, report_id)
            
            if result:
                self.helper.log_info("Successfully uploaded file via ImportDocument API")
                return True
            else:
                self.helper.log_error("Failed to upload file via ImportDocument API")
                return False
                
        except Exception as e:
            self.helper.log_error(f"Error in upload_and_link_file: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return False
            
        finally:
            # 一時ファイルの削除を確実に行う
            self._cleanup_temp_file(temp_path)

    def _upload_via_import_document(self, file_path: str, file_name: str, mime_type: str, report_id: str) -> bool:
        """
        ImportDocumentパイプラインを使用してファイルをアップロード
        OpenCTI 6.6.9互換の修正版 - External Reference作成せず
        
        Args:
            file_path: ファイルのパス
            file_name: ファイル名
            mime_type: MIMEタイプ
            report_id: 関連付けるレポートID
            
        Returns:
            bool: 成功時True
        """
        try:
            self.helper.log_info(f"Processing file via ImportDocument pipeline: {file_name}")
            
            # ファイルをレポートに直接インポート
            with open(file_path, 'rb') as file_obj:
                import_query = """
                mutation ImportFile($reportId: ID!, $file: Upload!) {
                stixDomainObjectEdit(id: $reportId) {
                    importPush(file: $file) {
                    id
                    name
                    }
                }
                }
                """
                
                operations = {
                    "query": import_query,
                    "variables": {
                        "reportId": report_id,
                        "file": None
                    }
                }
                
                map_data = {"0": ["variables.file"]}
                
                files = {
                    'operations': (None, json.dumps(operations), 'application/json'),
                    'map': (None, json.dumps(map_data), 'application/json'),
                    '0': (file_name, file_obj, mime_type)
                }
                
                headers = {"Authorization": f"Bearer {self.opencti_token}"}
                upload_url = f"{self.opencti_url}/graphql"
                
                # ファイルをインポート
                self.helper.log_info(f"Importing file via ImportDocument pipeline")
                response = requests.post(
                    upload_url,
                    headers=headers,
                    files=files,
                    timeout=300
                )
                
                if response.status_code != 200:
                    self.helper.log_error(f"File import failed: {response.status_code}")
                    self.helper.log_error(f"Response: {response.text[:500]}")
                    return False
                    
                result = response.json()
                
                # エラーがあるか確認
                if "errors" in result:
                    for error in result.get("errors", []):
                        self.helper.log_error(f"GraphQL Error: {error.get('message')}")
                    return False
                    
                # インポート結果を確認
                if "data" in result and "stixDomainObjectEdit" in result["data"]:
                    if result["data"]["stixDomainObjectEdit"] and "importPush" in result["data"]["stixDomainObjectEdit"]:
                        imported_file = result["data"]["stixDomainObjectEdit"]["importPush"]
                        if imported_file and "id" in imported_file:
                            imported_file_id = imported_file["id"]
                            self.helper.log_info(f"File successfully imported via ImportDocument pipeline: {imported_file_id}")
                            return True
                
                self.helper.log_error("Failed to import file via ImportDocument pipeline")
                self.helper.log_error(f"Response structure: {json.dumps(result)[:500]}")
                return False
                    
        except Exception as e:
            self.helper.log_error(f"Error in ImportDocument processing: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return False

    def _save_to_temp_file(self, file_content: bytes, file_name: str) -> Optional[str]:
        """
        ファイル内容を一時ファイルに保存
        
        Args:
            file_content: ファイルコンテンツ
            file_name: ファイル名
            
        Returns:
            Optional[str]: 一時ファイルのパス、または失敗時はNone
        """
        try:
            # 元のファイル拡張子を保持
            ext = os.path.splitext(file_name)[1]
            
            # 一時ファイルを作成
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_file.write(file_content)
                temp_path = temp_file.name
                
            # 追跡リストに追加
            self.temp_files.append(temp_path)
            self.helper.log_info(f"Temporary file created at: {temp_path}")
            
            return temp_path
            
        except Exception as e:
            self.helper.log_error(f"Error creating temp file: {str(e)}")
            return None

    def _cleanup_temp_file(self, file_path: Optional[str]) -> None:
        """
        一時ファイルを安全に削除
        
        Args:
            file_path: 削除するファイルのパス
        """
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
                self.helper.log_info(f"Temporary file deleted: {file_path}")
                
                if file_path in self.temp_files:
                    self.temp_files.remove(file_path)
            except Exception as e:
                self.helper.log_warning(f"Failed to delete temp file {file_path}: {str(e)}")

    def _cleanup_all_temp_files(self) -> None:
        """すべての追跡されている一時ファイルを削除"""
        if not self.temp_files:
            return
            
        self.helper.log_info(f"Cleaning up {len(self.temp_files)} temporary files")
        
        for temp_file in self.temp_files[:]:
            self._cleanup_temp_file(temp_file)
            
        self.temp_files = []