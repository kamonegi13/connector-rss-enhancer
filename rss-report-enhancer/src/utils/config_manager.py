#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
設定管理クラス
環境変数とYAML設定の読み込み・統合を担当
"""

import os
import yaml


class ConfigManager:
    """設定管理クラス"""

    def __init__(self, config_file_path=None):
        """
        設定マネージャーを初期化
        
        Args:
            config_file_path: 設定ファイルのパス
        """
        self.config = {}
        
        # 設定ファイルが指定されている場合は読み込む
        if config_file_path and os.path.isfile(config_file_path):
            with open(config_file_path, "r") as config_file:
                self.config = yaml.load(config_file, Loader=yaml.FullLoader) or {}
    
    def get_value(self, env_var_name, yaml_path=None, default=None, is_number=False, 
                   is_boolean=False, is_list=False, delimiter=','):
        """
        設定値を取得（優先順位: 環境変数 > YAML設定ファイル > デフォルト値）
        
        Args:
            env_var_name: 環境変数名
            yaml_path: YAML内のパス(リスト)
            default: デフォルト値
            is_number: 数値として解釈するかどうか
            is_boolean: ブール値として解釈するかどうか
            is_list: リストとして解釈するかどうか
            delimiter: リストの区切り文字
            
        Returns:
            取得した設定値
        """
        # 環境変数から取得
        if os.getenv(env_var_name) is not None:
            result = os.getenv(env_var_name)
        # YAML設定から取得
        elif yaml_path and len(yaml_path) > 0 and self.config:
            if yaml_path[0] in self.config and yaml_path[1] in self.config[yaml_path[0]]:
                result = self.config[yaml_path[0]][yaml_path[1]]
            else:
                result = default
        # デフォルト値
        else:
            result = default

        # 結果を適切な型に変換
        if result is not None:
            if is_number:
                result = int(result)
            elif is_boolean:
                result = self._parse_boolean(result)
            elif is_list:
                result = self._parse_list(result, delimiter)

        return result
    
    def _parse_boolean(self, value):
        """
        値をブール値に変換
        
        Args:
            value: 変換する値
            
        Returns:
            bool: 変換されたブール値
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        return bool(value)
    
    def _parse_list(self, value, delimiter=','):
        """
        値をリストに変換
        
        Args:
            value: 変換する値
            delimiter: リストの区切り文字
            
        Returns:
            list: 変換されたリスト
        """
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(delimiter)]
        return []