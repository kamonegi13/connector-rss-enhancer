#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
レポート取得クラス
OpenCTIからレポートを取得する機能を提供します。
"""

import json
import requests
import traceback
from typing import Dict, Any, Optional, List, Set, Callable


class ReportFetcher:
    """レポート取得クラス"""
    
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
        self.debug_mode = False
        
    def set_debug_mode(self, debug_mode):
        """デバッグモードを設定"""
        self.debug_mode = debug_mode

    def get_latest_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        最新のレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        try:
            # 確実に整数型
            limit = int(limit)
            
            self.helper.log_info(f"Fetching latest reports using GraphQL (limit: {limit})")
            
            # 取得メソッドを定義（優先順位順）
            fetch_methods = [
                {"name": "Helper API", "method": self._fetch_via_helper},
                {"name": "GraphQL", "method": self._fetch_via_graphql},
                {"name": "Simplified GraphQL", "method": self._fetch_via_simple_graphql}
            ]
            
            # 各メソッドを順番に試す
            for method_info in fetch_methods:
                method_name = method_info["name"]
                method = method_info["method"]
                
                try:
                    self.helper.log_info(f"Attempting to fetch reports via {method_name}")
                    reports = method(limit)
                    
                    if reports and len(reports) > 0:
                        self.helper.log_info(f"Successfully fetched {len(reports)} reports via {method_name}")
                        return reports
                    else:
                        self.helper.log_info(f"No reports found via {method_name}")
                except Exception as method_error:
                    if self.debug_mode:
                        self.helper.log_warning(f"Report fetch via {method_name} failed: {str(method_error)}")
                    continue
            
            self.helper.log_info("All regular report fetch methods failed. Trying alternatives...")
            return self.get_reports_alternative(limit)
            
        except Exception as e:
            self.helper.log_error(f"Error fetching reports: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return []

    def _fetch_via_helper(self, limit: int) -> List[Dict[str, Any]]:
        """
        APIヘルパーを使用してレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        # OpenCTI API v6で変更されたフィルタ構造
        list_filters = {
            "mode": "and",
            "filters": [{"key": "entity_type", "values": ["Report"]}],
            "filterGroups": []
        }
        
        reports_result = self.helper.api.stix_domain_object.list(
            filters=list_filters,
            orderBy="created",
            orderMode="desc",
            first=limit,
            withoutPrefix=False
        )
        
        if reports_result and "data" in reports_result and "stixDomainObjects" in reports_result["data"]:
            edges = reports_result["data"]["stixDomainObjects"]["edges"]
            
            processed_reports = []
            for edge in edges:
                if "node" in edge:
                    report = edge["node"]
                    processed_reports.append(self._normalize_report_structure(report))
            
            return processed_reports
        
        return []

    def _fetch_via_graphql(self, limit: int) -> List[Dict[str, Any]]:
        """
        GraphQLを使用してレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        # GraphQLクエリ（OpenCTI 6.6.9 対応）
        query = """
        query LatestReports($first: Int, $orderBy: ReportsOrdering, $orderMode: OrderingMode) {
          reports(
            first: $first,
            orderBy: $orderBy,
            orderMode: $orderMode
          ) {
            edges {
              node {
                id
                name
                description
                report_types
                createdBy {
                  id
                  name
                }
                objectLabel {
                  id
                  value
                  color
                }
                externalReferences {
                  edges {
                    node {
                      id
                      source_name
                      description
                      url
                      external_id
                    }
                  }
                }
                created
                modified
              }
            }
          }
        }
        """
        
        variables = {
            "first": limit,
            "orderBy": "created",
            "orderMode": "desc"
        }
        
        # GraphQLクエリを実行
        response = self.api_client.direct_query(query, variables)
        
        # レスポンスを処理
        return self._process_graphql_response(response, "reports")

    def _fetch_via_simple_graphql(self, limit: int) -> List[Dict[str, Any]]:
        """
        簡略化されたGraphQLクエリでレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        # 簡略化されたクエリ
        simple_query = """
        query LatestReports($first: Int) {
          reports(first: $first) {
            edges {
              node {
                id
                name
                description
                report_types
                objectLabel {
                  id
                  value
                }
                externalReferences {
                  edges {
                    node {
                      url
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        response = self.api_client.direct_query(simple_query, {"first": limit})
        
        # レスポンスを処理
        return self._process_graphql_response(response, "reports")

    def _process_graphql_response(self, response: Dict[str, Any], entity_type: str) -> List[Dict[str, Any]]:
        """
        GraphQLレスポンスからレポートデータを抽出
        
        Args:
            response: GraphQLレスポンス
            entity_type: エンティティタイプ（例："reports"）
            
        Returns:
            List[Dict]: 正規化されたレポートのリスト
        """
        reports = []
        
        if not response:
            return reports
            
        # デバッグ出力
        if self.debug_mode and "errors" in response:
            self.helper.log_error(f"GraphQL errors: {json.dumps(response['errors'])}")
            
        # データの抽出
        if "data" in response and entity_type in response["data"]:
            data = response["data"][entity_type]
            
            if "edges" in data:
                edges = data["edges"]
                
                for edge in edges:
                    if "node" in edge:
                        # レポート構造を正規化して追加
                        reports.append(self._normalize_report_structure(edge["node"]))
        
        return reports

    def get_reports_alternative(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        代替方法でレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        try:
            self.helper.log_info(f"Trying alternative methods to fetch reports (limit: {limit})")
            
            # 代替取得メソッドを定義
            alt_methods = [
                {"name": "REST API", "method": self._fetch_via_rest},
                {"name": "Direct API", "method": self._fetch_via_direct_api},
                {"name": "Custom GraphQL", "method": self._fetch_via_custom_graphql}
            ]
            
            # 各メソッドを順番に試す
            for method_info in alt_methods:
                method_name = method_info["name"]
                method = method_info["method"]
                
                try:
                    self.helper.log_info(f"Attempting to fetch reports via {method_name}")
                    reports = method(limit)
                    
                    if reports and len(reports) > 0:
                        self.helper.log_info(f"Successfully fetched {len(reports)} reports via {method_name}")
                        return reports
                    else:
                        self.helper.log_info(f"No reports found via {method_name}")
                except Exception as method_error:
                    if self.debug_mode:
                        self.helper.log_warning(f"Alternative fetch via {method_name} failed: {str(method_error)}")
                    continue
            
            self.helper.log_info("All alternative report fetch methods failed")
            return []
                
        except Exception as e:
            self.helper.log_error(f"Error in alternative report fetching: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return []

    def _fetch_via_rest(self, limit: int) -> List[Dict[str, Any]]:
        """
        RESTful APIを使用してレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        # RESTエンドポイントから直接データを取得
        url = f"{self.opencti_url}/graphql/rest/report"
        headers = {"Authorization": f"Bearer {self.opencti_token}"}
        
        self.helper.log_info(f"Requesting reports from REST API: {url}")
        
        response = requests.get(
            url,
            headers=headers,
            params={"types": "report", "limit": limit},
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return [self._normalize_report_structure(report) for report in data]
        
        return []

    def _fetch_via_direct_api(self, limit: int) -> List[Dict[str, Any]]:
        """
        直接APIクライアントを使用してレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        # OpenCTI 6.6.9では、フィルタ構造が変更されている
        list_filters = {
            "mode": "and",
            "filters": [{"key": "entity_type", "values": ["Report"]}],
            "filterGroups": []  # 空の配列が必要
        }
        
        # 直接APIクライアントを使用
        api_client = self.helper.api.stix_domain_object
        
        # メソッドを直接呼び出す
        reports = api_client.list(
            filters=list_filters,
            orderBy="created",
            orderMode="desc",
            first=limit
        )
        
        if reports and "data" in reports and "stixDomainObjects" in reports["data"]:
            edges = reports["data"]["stixDomainObjects"]["edges"]
            
            processed_reports = []
            for edge in edges:
                if "node" in edge:
                    processed_reports.append(self._normalize_report_structure(edge["node"]))
                    
            return processed_reports
        
        return []

    def _fetch_via_custom_graphql(self, limit: int) -> List[Dict[str, Any]]:
        """
        カスタムGraphQLクエリでレポートを取得
        
        Args:
            limit: 取得するレポートの最大数
            
        Returns:
            List[Dict]: レポートのリスト
        """
        # より単純なGraphQLクエリ
        query = """
        query FetchReports {
          reports(first: 10) {
            edges {
              node {
                id
                name
                description
                report_types
                objectLabel {
                  id
                  value
                }
                externalReferences {
                  edges {
                    node {
                      url
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        response = self.api_client.direct_query(query)
        
        # 共通処理メソッドを使用
        return self._process_graphql_response(response, "reports")

    def _normalize_report_structure(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        レポート構造を正規化
        
        Args:
            report: オリジナルのレポートデータ
            
        Returns:
            Dict[str, Any]: 正規化されたレポートデータ
        """
        # externalReferencesの構造を調整
        if "externalReferences" in report:
            if isinstance(report["externalReferences"], dict) and "edges" in report["externalReferences"]:
                ext_refs = []
                for ext_ref_edge in report["externalReferences"]["edges"]:
                    if "node" in ext_ref_edge:
                        ext_refs.append(ext_ref_edge["node"])
                report["externalReferences"] = ext_refs
        
        return report

    def find_url_in_report(self, report: Dict[str, Any]) -> Optional[str]:
        """
        レポートから最初のURLを抽出
        
        Args:
            report: レポートデータ
            
        Returns:
            Optional[str]: 見つかったURL、または見つからない場合はNone
        """
        try:
            # URLの確認 - 新しい構造に対応
            if "externalReferences" in report:
                # データ構造に基づいてURLを抽出
                url = self._extract_url_from_external_references(report["externalReferences"])
                
                if url:
                    self.helper.log_info(f"Found external URL: {url}")
                    return url
                else:
                    self.helper.log_info("No valid external URL found in external references")
            else:
                self.helper.log_info("No external references found in report")
                
            return None
            
        except Exception as e:
            self.helper.log_error(f"Error finding URL in report: {str(e)}")
            return None

    def _extract_url_from_external_references(self, external_references: Any) -> Optional[str]:
        """
        外部参照からURLを抽出する共通メソッド
        
        Args:
            external_references: 外部参照データ（リストまたはedges/node形式）
            
        Returns:
            Optional[str]: 見つかったURL、または見つからない場合はNone
        """
        # 配列形式の場合（従来の構造）
        if isinstance(external_references, list):
            for ref in external_references:
                if isinstance(ref, dict) and "url" in ref and ref["url"]:
                    url = ref["url"]
                    # 内部ストレージパスでないことを確認
                    if not url.startswith("http://localhost") and not "storage/get" in url:
                        return url
        
        # edges/node形式の場合（新しい構造）
        elif isinstance(external_references, dict) and "edges" in external_references:
            for edge in external_references["edges"]:
                if "node" in edge and "url" in edge["node"] and edge["node"]["url"]:
                    url = edge["node"]["url"]
                    # 内部ストレージパスでないことを確認
                    if not url.startswith("http://localhost") and not "storage/get" in url:
                        return url
        
        return None

    def get_report_types(self, report: Dict[str, Any]) -> List[str]:
        """
        レポートからレポートタイプを抽出
        
        Args:
            report: レポートデータ
            
        Returns:
            List[str]: レポートタイプのリスト
        """
        # レポートタイプによるフィルタリング - フィールド名の両方をチェック（JSON構造の変更に対応）
        report_types = report.get("reportTypes", report.get("report_types", []))
        # すべてのレポートタイプを小文字に変換
        return [rt.lower() if isinstance(rt, str) else rt for rt in report_types]

    def get_all_reports(self, batch_size=100, max_count=0):
        """
        すべてのレポートを取得（ページングあり）
        
        Args:
            batch_size: 一度に取得するレポート数
            max_count: 取得する最大レポート数（0=無制限）
            
        Returns:
            List[Dict]: レポートのリスト
        """
        try:
            max_text = "unlimited" if max_count == 0 else str(max_count)
            self.helper.log_info(f"Fetching all reports (batch size: {batch_size}, max: {max_text})")
            
            all_reports = []
            cursor = None
            has_more = True
            
            while has_more:
                # ページングクエリ
                query = """
                query FetchReports($first: Int, $after: ID) {
                reports(first: $first, after: $after) {
                    pageInfo {
                    hasNextPage
                    endCursor
                    }
                    edges {
                    node {
                        id
                        name
                        description
                        report_types
                        objectLabel {
                        id
                        value
                        }
                        externalReferences {
                        edges {
                            node {
                            url
                            }
                        }
                        }
                    }
                    }
                }
                }
                """
                
                variables = {
                    "first": batch_size,
                    "after": cursor
                }
                
                self.helper.log_info(f"Fetching batch of reports{' after cursor: ' + cursor if cursor else ''}")
                response = self.api_client.direct_query(query, variables)
                
                if not response or "data" not in response or "reports" not in response["data"]:
                    self.helper.log_info("No more reports found or query failed")
                    break
                    
                reports_data = response["data"]["reports"]
                
                if "edges" not in reports_data or not reports_data["edges"]:
                    self.helper.log_info("No edges found in reports data")
                    break
                    
                batch_reports = []
                for edge in reports_data["edges"]:
                    if "node" in edge:
                        batch_reports.append(self._normalize_report_structure(edge["node"]))
                
                all_reports.extend(batch_reports)
                self.helper.log_info(f"Retrieved {len(batch_reports)} reports (total: {len(all_reports)})")
                
                # 次のページがあるか確認
                if ("pageInfo" in reports_data and 
                    reports_data["pageInfo"]["hasNextPage"] and 
                    reports_data["pageInfo"]["endCursor"]):
                    cursor = reports_data["pageInfo"]["endCursor"]
                    self.helper.log_info(f"More pages available, next cursor: {cursor}")
                else:
                    has_more = False
                    self.helper.log_info("No more pages available")
                
                # 最大件数に達したか確認
                if max_count > 0 and len(all_reports) >= max_count:
                    self.helper.log_info(f"Reached maximum report count limit ({max_count})")
                    all_reports = all_reports[:max_count]
                    break
            
            self.helper.log_info(f"Completed fetching all reports: {len(all_reports)} total")
            return all_reports
                
        except Exception as e:
            self.helper.log_error(f"Error fetching all reports: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return []