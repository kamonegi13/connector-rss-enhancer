#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ラベル管理クラス
ラベルの作成と関連付けを担当します。
"""

import requests
import traceback
from typing import Dict, Any, Optional, List


class LabelManager:
    """ラベル管理クラス"""
    
    def __init__(self, api_client, helper):
        """
        初期化
        
        Args:
            api_client: OpenCTI APIクライアントインスタンス
            helper: ヘルパーオブジェクト
        """
        self.api_client = api_client
        self.helper = helper
        self.existing_labels = {}  # ラベルキャッシュ

    def ensure_label_exists(self, label_value: str, color: str = "#ff9900") -> bool:
        """
        指定したラベルが存在するか確認し、存在しなければ作成
        
        Args:
            label_value: ラベル値
            color: ラベルの色（16進数カラーコード）
            
        Returns:
            bool: 成功時True
        """
        # キャッシュをチェック
        if label_value in self.existing_labels:
            return True
            
        try:
            self.helper.log_info(f"Checking if label '{label_value}' exists")
            
            # 複数の方法を試行
            create_methods = [
                self._create_label_via_helper,
                self._create_label_via_rest,
                self._create_label_via_graphql
            ]
            
            for method in create_methods:
                try:
                    if method(label_value, color):
                        # 成功した場合、キャッシュに追加
                        self.existing_labels[label_value] = True
                        return True
                except Exception as method_error:
                    self.helper.log_warning(f"Label creation method failed: {str(method_error)}")
                    continue
            
            self.helper.log_error(f"All label creation methods failed for '{label_value}'")
            return False
            
        except Exception as e:
            self.helper.log_error(f"Error checking/creating label: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return False

    def _create_label_via_helper(self, label_value: str, color: str) -> bool:
        """
        APIヘルパーを使用してラベルを作成
        
        Args:
            label_value: ラベル値
            color: ラベルの色
            
        Returns:
            bool: 成功時True
        """
        self.helper.log_info(f"Creating/retrieving label via API helper")
        label_result = self.helper.api.label.create(
            value=label_value,
            color=color
        )
        
        if label_result:
            self.helper.log_info(f"Label '{label_value}' created/retrieved successfully via API")
            return True
            
        return False

    def _create_label_via_rest(self, label_value: str, color: str) -> bool:
        """
        REST APIを使用してラベルを作成
        
        Args:
            label_value: ラベル値
            color: ラベルの色
            
        Returns:
            bool: 成功時True
        """
        self.helper.log_info(f"Creating label via REST API")
        url = f"{self.api_client.opencti_url}/graphql/rest/label"
        headers = {
            "Authorization": f"Bearer {self.api_client.opencti_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "value": label_value,
            "color": color
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            self.helper.log_info(f"Label '{label_value}' created via REST API")
            return True
            
        return False

    def _create_label_via_graphql(self, label_value: str, color: str) -> bool:
        """
        GraphQLを使用してラベルを作成
        
        Args:
            label_value: ラベル値
            color: ラベルの色
            
        Returns:
            bool: 成功時True
        """
        self.helper.log_info(f"Creating label via GraphQL")
        create_query = """
        mutation CreateLabel($input: LabelAddInput!) {
          labelAdd(input: $input) {
            id
          }
        }
        """
        
        create_variables = {
            "input": {
                "value": label_value,
                "color": color
            }
        }
        
        create_response = self.api_client.direct_query(create_query, create_variables)
        
        if create_response and "data" in create_response and "labelAdd" in create_response["data"]:
            self.helper.log_info(f"Label created successfully via direct GraphQL")
            return True
            
        return False

    def add_label_to_report(self, report_id: str, label_value: str) -> bool:
        """
        レポートにラベルを追加
        
        Args:
            report_id: レポートID
            label_value: 追加するラベル値
            
        Returns:
            bool: 追加成功時True
        """
        try:
            self.helper.log_info(f"Adding label '{label_value}' to report {report_id}")
            
            # 複数の方法を試行
            add_methods = [
                self._add_label_via_helper,
                self._add_label_via_graphql
            ]
            
            for method in add_methods:
                try:
                    if method(report_id, label_value):
                        return True
                except Exception as method_error:
                    self.helper.log_warning(f"Label addition method failed: {str(method_error)}")
                    continue
            
            self.helper.log_error(f"All label addition methods failed for '{label_value}'")
            return False
                
        except Exception as e:
            self.helper.log_error(f"Error adding label: {str(e)}")
            self.helper.log_error(traceback.format_exc())
            return False

    def _add_label_via_helper(self, report_id: str, label_value: str) -> bool:
        """
        APIヘルパーを使用してラベルを追加
        
        Args:
            report_id: レポートID
            label_value: ラベル値
            
        Returns:
            bool: 成功時True
        """
        result = self.helper.api.stix_domain_object.add_label(
            id=report_id,
            label_name=label_value
        )
        if result:
            self.helper.log_info(f"Label added successfully using API helper")
            return True
            
        return False

    def _add_label_via_graphql(self, report_id: str, label_value: str) -> bool:
        """
        GraphQLを使用してラベルを追加
        
        Args:
            report_id: レポートID
            label_value: ラベル値
            
        Returns:
            bool: 成功時True
        """
        query = """
        mutation AddLabel($id: ID!, $input: LabelAddInput!) {
          stixDomainObjectAddLabel(id: $id, input: $input) {
            id
          }
        }
        """
        
        variables = {
            "id": report_id,
            "input": {
                "value": label_value
            }
        }
        
        # クエリを実行
        response = self.api_client.direct_query(query, variables)
        
        if response and "data" in response and "stixDomainObjectAddLabel" in response["data"]:
            if response["data"]["stixDomainObjectAddLabel"]:
                self.helper.log_info("Label added successfully using GraphQL")
                return True
                
        return False

    def has_label(self, report: Dict[str, Any], label_value: str) -> bool:
        """
        レポートが指定したラベルを持っているか確認
        
        Args:
            report: レポートデータ
            label_value: 確認するラベル値
            
        Returns:
            bool: ラベルが存在する場合True
        """
        if "objectLabel" not in report or not report["objectLabel"]:
            return False
            
        for label in report["objectLabel"]:
            if isinstance(label, dict) and label.get("value") == label_value:
                return True
        
        return False