#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OpenCTI API操作クラス
GraphQLクエリの実行やAPI情報の取得を担当します。
"""

import json
import requests
import traceback
from typing import Dict, Any, Optional, Union, List


class OpenCTIApi:
    """OpenCTI API操作クラス"""
    
    def __init__(self, opencti_url, opencti_token, helper):
        """
        初期化
        
        Args:
            opencti_url: OpenCTI API URL
            opencti_token: APIトークン
            helper: ヘルパーオブジェクト
        """
        self.opencti_url = opencti_url
        self.opencti_token = opencti_token
        self.helper = helper
        self.debug_mode = False
        self.timeout = 60  # 秒単位のリクエストタイムアウト
        self.max_retries = 3  # リトライ回数

    def set_debug_mode(self, debug_mode):
        """
        デバッグモードを設定
        
        Args:
            debug_mode: デバッグモードのフラグ
        """
        self.debug_mode = debug_mode

    def direct_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        GraphQLクエリを直接実行
        
        Args:
            query: GraphQLクエリ文字列
            variables: クエリ変数
            
        Returns:
            Optional[Dict[str, Any]]: レスポンス辞書、またはエラー時はNone
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.opencti_token}"
        }
        
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        # リクエスト内容をログに出力
        if self.debug_mode:
            self.helper.log_info(f"Sending GraphQL query: {query}")
            self.helper.log_info(f"Variables: {json.dumps(variables)}")
        else:
            self.helper.log_info(f"Sending GraphQL query with variables: {json.dumps(variables)}")
        
        # リトライメカニズムを実装
        return self._execute_query_with_retry(payload, headers)

    def _execute_query_with_retry(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        リトライ機能付きでクエリを実行
        
        Args:
            payload: クエリのペイロード
            headers: HTTPヘッダー
            
        Returns:
            Optional[Dict[str, Any]]: レスポンス辞書、またはエラー時はNone
        """
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                # タイムアウトを設定して接続問題を回避
                response = requests.post(
                    f"{self.opencti_url}/graphql",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # レスポンスステータスをログに出力
                self.helper.log_info(f"GraphQL response status: {response.status_code}")
                
                if response.status_code != 200:
                    self.helper.log_error(f"GraphQL query failed with status {response.status_code}")
                    self.helper.log_error(f"Response: {response.text[:500]}")
                    
                    # レート制限などの一時的なエラーの場合はリトライ
                    if response.status_code in [429, 502, 503, 504]:
                        retry_count += 1
                        self.helper.log_info(f"Retrying query (attempt {retry_count}/{self.max_retries})")
                        continue
                    return None
                
                # JSONデコードエラーを処理
                try:
                    response_json = response.json()
                except json.JSONDecodeError:
                    self.helper.log_error(f"Failed to decode JSON response: {response.text[:200]}...")
                    retry_count += 1
                    continue
                
                # エラーがあればログに出力
                if "errors" in response_json:
                    self.helper.log_error(f"GraphQL errors: {json.dumps(response_json['errors'])}")
                    
                return response_json
                
            except requests.exceptions.Timeout:
                self.helper.log_error("GraphQL request timed out")
                retry_count += 1
                if retry_count < self.max_retries:
                    self.helper.log_info(f"Retrying query (attempt {retry_count}/{self.max_retries})")
                    continue
                    
            except requests.exceptions.ConnectionError:
                self.helper.log_error("Connection error during GraphQL request")
                retry_count += 1
                if retry_count < self.max_retries:
                    self.helper.log_info(f"Retrying query (attempt {retry_count}/{self.max_retries})")
                    continue
                    
            except Exception as e:
                self.helper.log_error(f"Unexpected error in GraphQL request: {str(e)}")
                return None
        
        self.helper.log_error(f"Failed after {self.max_retries} retries")
        return None

    def test_api_connection(self) -> bool:
        """
        APIへの接続をテスト
        
        Returns:
            bool: 接続成功の場合True
        """
        # APIバージョンを取得してみる - OpenCTI 6.6.9対応
        test_query = """
        query {
          about {
            version
          }
        }
        """
        
        try:
            # 方法1: GraphQLクエリでバージョン取得
            test_result = self.direct_query(test_query)
            
            if test_result and "data" in test_result and "about" in test_result["data"]:
                version = test_result["data"]["about"].get("version", "unknown")
                self.helper.log_info(f"Connected to OpenCTI platform version: {version}")
                return True
            
            # 方法2: 直接バージョンエンドポイントを呼び出し
            try:
                self.helper.log_info("Trying direct version endpoint...")
                headers = {"Authorization": f"Bearer {self.opencti_token}"}
                response = requests.get(f"{self.opencti_url}/version", headers=headers)
                
                if response.status_code == 200:
                    api_info = response.json()
                    if "version" in api_info:
                        self.helper.log_info(f"Connected to OpenCTI platform - direct API check. Version: {api_info['version']}")
                        return True
            except Exception as direct_error:
                self.helper.log_info(f"Direct version endpoint failed: {str(direct_error)}")
            
            # 方法3: APIヘルパーを使用
            try:
                self.helper.log_info("Trying API helper for version info...")
                api_version = self.helper.api.info.get()
                if api_version:
                    self.helper.log_info(f"Connected to OpenCTI API version: {api_version}")
                    return True
            except Exception as helper_error:
                self.helper.log_info(f"API helper version check failed: {str(helper_error)}")
            
            self.helper.log_error("Could not determine OpenCTI version - all methods failed")
            return False
            
        except Exception as e:
            self.helper.log_error(f"API test failed: {str(e)}")
            return False

    def get_vocabularies(self, category: str) -> List[str]:
        """
        ボキャブラリー（語彙）リストを取得
        
        Args:
            category: ボキャブラリーカテゴリ
            
        Returns:
            List[str]: ボキャブラリー名のリスト
        """
        self.helper.log_info(f"Fetching vocabularies for category: {category}")
        
        # 複数の方法を順番に試す
        methods = [
            (self._get_vocabularies_via_helper, "API helper"),
            (self._get_vocabularies_via_graphql, "GraphQL"),
            (self._get_vocabularies_via_rest, "REST API")
        ]
        
        for method, method_name in methods:
            try:
                self.helper.log_info(f"Trying to fetch vocabularies using {method_name}")
                result = method(category)
                
                if result and len(result) > 0:
                    self.helper.log_info(f"Successfully fetched {len(result)} vocabularies using {method_name}")
                    return result
                else:
                    self.helper.log_info(f"No vocabularies found using {method_name}")
            except Exception as e:
                if self.debug_mode:
                    self.helper.log_info(f"Vocabulary method '{method_name}' failed: {str(e)}")
                continue
        
        # 何も見つからなかった場合はハードコードされた値をデフォルトとして使用
        self.helper.log_info(f"Falling back to default vocabulary values for {category}")
        if category == "report_types_ov":
            default_values = ["threat-report", "attack-pattern", "tool", "malware", "vulnerability", "rss-feed", "rss-report"]
            self.helper.log_info(f"Using {len(default_values)} default vocabulary values")
            return default_values
            
        return []

    def _get_vocabularies_via_helper(self, category: str) -> List[str]:
        """
        APIヘルパーを使用してボキャブラリーを取得
        
        Args:
            category: ボキャブラリーカテゴリ
            
        Returns:
            List[str]: ボキャブラリー名のリスト
        """
        vocabs = self.helper.api.vocabulary.list()
        
        if vocabs:
            # カテゴリでフィルタリング
            filtered_vocabs = [
                v.get("name", "").lower() 
                for v in vocabs 
                if v.get("category") == category and v.get("name")
            ]
            
            return filtered_vocabs
        
        return []

    def _get_vocabularies_via_graphql(self, category: str) -> List[str]:
        """
        GraphQLを使用してボキャブラリーを取得
        
        Args:
            category: ボキャブラリーカテゴリ
            
        Returns:
            List[str]: ボキャブラリー名のリスト
        """
        query = f"""
        query VocabularyDefinition {{
          vocabularies(category: {category}) {{
            edges {{
              node {{
                name
              }}
            }}
          }}
        }}
        """
        
        response = self.direct_query(query)
        
        if response and "data" in response and "vocabularies" in response["data"]:
            vocab_edges = response["data"]["vocabularies"].get("edges", [])
            vocabularies = [
                edge["node"]["name"].lower() 
                for edge in vocab_edges 
                if "node" in edge and "name" in edge["node"]
            ]
            
            return vocabularies
            
        return []

    def _get_vocabularies_via_rest(self, category: str) -> List[str]:
        """
        REST APIを使用してボキャブラリーを取得
        
        Args:
            category: ボキャブラリーカテゴリ
            
        Returns:
            List[str]: ボキャブラリー名のリスト
        """
        url = f"{self.opencti_url}/graphql/rest/vocabulary"
        headers = {"Authorization": f"Bearer {self.opencti_token}"}
        
        response = requests.get(url, headers=headers, params={"category": category})
        
        if response.status_code == 200:
            result = response.json()
            
            if isinstance(result, list):
                return [item.get("name", "").lower() for item in result if item.get("name")]
                
        return []

    def update_stix_domain_object(self, object_id: str, fields: Dict[str, Any]) -> bool:
        """
        STIX Domainオブジェクトのフィールドを更新（API互換性問題解決版）
        
        Args:
            object_id: オブジェクトID
            fields: 更新対象フィールドの辞書
            
        Returns:
            bool: 更新成功の場合True
        """
        try:
            success_count = 0
            field_count = len(fields)
            
            # 各フィールドに対して更新を実行
            for field_name, field_value in fields.items():
                self.helper.log_info(f"Updating field '{field_name}' for object {object_id}")
                
                # エスケープ処理 - 特殊文字を含む長いテキストを処理
                if isinstance(field_value, str) and len(field_value) > 50000:
                    self.helper.log_info(f"Field value is large ({len(field_value)} chars), truncating if needed")
                    # 長いテキストを必要に応じて切り詰め
                    if len(field_value) > 200000:
                        field_value = field_value[:199000] + "\n\n[Content truncated due to size limits]"
                
                # GraphQL クエリを使用してフィールドを更新
                if self._update_field_via_graphql(object_id, field_name, field_value):
                    success_count += 1
                    self.helper.log_info(f"Field '{field_name}' updated successfully")
                else:
                    self.helper.log_error(f"Failed to update field '{field_name}'")
            
            # すべてのフィールドが更新されたか確認
            return success_count == field_count
                
        except Exception as e:
            self.helper.log_error(f"Error updating STIX domain object: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return False

    def _update_field_via_graphql(self, object_id: str, field_name: str, field_value: Any) -> bool:
        """
        GraphQL経由で単一フィールドを更新
        
        Args:
            object_id: オブジェクトID
            field_name: フィールド名
            field_value: フィールド値
            
        Returns:
            bool: 更新成功の場合True
        """
        query = """
        mutation UpdateEntity($id: ID!, $input: [EditInput]!) {
          stixDomainObjectEdit(id: $id) {
            fieldPatch(input: $input) {
              id
            }
          }
        }
        """
        
        variables = {
            "id": object_id,
            "input": [{
                "key": field_name,
                "value": field_value
            }]
        }
        
        # GraphQL クエリを実行
        response = self.direct_query(query, variables)
        
        if response and "data" in response and "stixDomainObjectEdit" in response["data"]:
            return True
            
        # エラー情報の詳細を出力
        if self.debug_mode and response and "errors" in response:
            self.helper.log_error(f"GraphQL errors: {json.dumps(response['errors'])}")
            
        return False