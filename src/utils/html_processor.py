#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HTML処理クラス
URLから記事コンテンツを取得し、HTMLの解析とPDF変換機能を提供します。
"""

import os
import tempfile
import pdfkit
import newspaper
import requests
import time
import random
import traceback
import subprocess
from urllib.parse import urlparse, urljoin
from newspaper import Article, Config
from datetime import datetime
from lxml import html, etree
import re


class HTMLProcessor:
    """HTML処理クラス - 記事の抽出とPDF変換を担当"""
    
    # 定数定義
    DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    WGET_COMMAND = "wget"
    WGET_TIMEOUT = 30
    WGET_TRIES = 2
    MIN_TEXT_LENGTH = 100
    
    def __init__(self, user_agent=None, helper=None):
        """
        初期化
        
        Args:
            user_agent: 使用するUser-Agent (省略時はデフォルト値使用)
            helper: ログヘルパーオブジェクト (省略可)
        """
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.helper = helper
    
    def log(self, message, level="info"):
        """
        ログメッセージを出力
        
        Args:
            message: ログメッセージ
            level: ログレベル ('info', 'error', 'warning')
        """
        if self.helper:
            if level == "error":
                self.helper.log_error(message)
            elif level == "warning":
                self.helper.log_warning(message)
            else:
                self.helper.log_info(message)
        else:
            print(message)
    
    def extract_article(self, url):
        """
        記事抽出のメイン関数 - 3段階の抽出方法を順に試行
        
        Args:
            url: 記事のURL
            
        Returns:
            dict: 抽出結果を含む辞書、または失敗時はNone
        """
        try:
            self.log(f"====== STARTING EXTRACTION FOR URL: {url} ======")
            
            # 3つの抽出方法を順番に試行
            extraction_methods = [
                {"name": "standard", "method": self._extract_standard},
                {"name": "direct_wget", "method": self._extract_direct},
                {"name": "advanced", "method": self._extract_advanced}
            ]
            
            for method in extraction_methods:
                method_name = method["name"]
                extract_func = method["method"]
                
                self.log(f"[EXTRACTION] ATTEMPT: Using {method_name} method")
                result = extract_func(url)
                
                if self._is_valid_result(result):
                    chars = len(result["text"])
                    self.log(f"[EXTRACTION] SUCCESS: {method_name} method extracted {chars} chars")
                    result["extraction_method"] = method_name
                    self.log(f"[EXTRACTION] COMPLETE: Used {method_name} method for {url}")
                    return result
                else:
                    self.log(f"[EXTRACTION] {method_name} method failed, trying next method")
            
            # すべて失敗した場合
            self.log("[EXTRACTION] FAILURE: All extraction methods failed")
            self.log(f"[EXTRACTION] COMPLETE: No successful extraction for {url}")
            return None
            
        except Exception as e:
            self.log(f"[EXTRACTION] CRITICAL ERROR: {str(e)}", "error")
            if self.helper:
                self.helper.log_error(traceback.format_exc())
            else:
                traceback.print_exc()
            return None
    
    def _is_valid_result(self, result):
        """
        抽出結果が有効かどうかを検証
        
        Args:
            result: 抽出結果辞書
            
        Returns:
            bool: 有効な場合True
        """
        return (result and 
                result.get("text") and 
                len(result.get("text", "").strip()) > self.MIN_TEXT_LENGTH)
    
    def _get_newspaper_config(self, timeout=30, fetch_images=True):
        """
        newspaper3kの設定を取得
        
        Args:
            timeout: タイムアウト秒数
            fetch_images: 画像取得するかどうか
            
        Returns:
            Config: 設定オブジェクト
        """
        config = Config()
        config.browser_user_agent = self.user_agent
        config.request_timeout = timeout
        config.fetch_images = fetch_images
        config.memoize_articles = True
        config.headers = self._get_common_headers()
        return config
    
    def _build_article_result(self, article, html_content=None):
        """
        記事オブジェクトから結果辞書を構築
        
        Args:
            article: newspaperのArticleオブジェクト
            html_content: 元のHTML内容（指定がなければarticle.htmlを使用）
            
        Returns:
            dict: 記事情報を含む辞書
        """
        # 画像情報を収集
        images = []
        if hasattr(article, 'images') and article.images:
            images = list(article.images)
        
        # 日付フォーマット
        publish_date = None
        if article.publish_date:
            try:
                publish_date = article.publish_date.strftime('%Y-%m-%d')
            except:
                pass
        
        # HTMLコンテンツの選択
        html = html_content if html_content is not None else article.html
        
        # サマリーの生成
        summary = article.text[:200] + "..." if article.text and len(article.text) > 200 else article.text
        
        # 結果辞書を構築
        return {
            "title": article.title,
            "text": article.text,
            "html": html,
            "authors": article.authors,
            "publish_date": publish_date,
            "top_image": article.top_image,
            "images": images,
            "keywords": article.keywords if hasattr(article, 'keywords') else [],
            "summary": summary,
            "error": None
        }
    
    def _extract_standard(self, url):
        """
        標準的な記事抽出メソッド - newspaper3kの基本機能を使用
        
        Args:
            url: 記事のURL
            
        Returns:
            dict: 抽出結果を含む辞書、または失敗時はエラー情報
        """
        try:
            config = self._get_newspaper_config(timeout=30, fetch_images=True)
            self.log(f"[STANDARD] Using User-Agent: {config.browser_user_agent}")
            
            # 記事をダウンロードして解析
            article = Article(url, config=config)
            
            try:
                self.log("[STANDARD] Downloading article")
                article.download()
                
                if not article.html or len(article.html) < 100:
                    self.log("[STANDARD] Download failed or HTML too small")
                    return {"error": "Failed to download HTML content", "text": None}
                    
                self.log(f"[STANDARD] Download successful, HTML size: {len(article.html)} bytes")
                self.log("[STANDARD] Parsing article")
                article.parse()
                
                # 記事のテキストを確認
                if not article.text or len(article.text.strip()) < self.MIN_TEXT_LENGTH:
                    self.log("[STANDARD] Parsing successful but text content too small")
                    return {"error": "Insufficient text content", "text": article.text}
                
                self.log(f"[STANDARD] Parsing successful, text length: {len(article.text)} chars")
                self.log(f"[STANDARD] Title: {article.title}")
                self.log(f"[STANDARD] Images found: {len(article.images)}")
                
                # トップ画像とその他の画像情報をログに記録
                if article.top_image:
                    self.log(f"[STANDARD] Top image: {article.top_image}")
                
                return self._build_article_result(article)
                
            except newspaper.article.ArticleException as e:
                self.log(f"[STANDARD] Newspaper exception: {str(e)}")
                return {"error": str(e), "text": None}
            except Exception as e:
                self.log(f"[STANDARD] Unexpected error: {str(e)}")
                return {"error": str(e), "text": None}
                
        except Exception as e:
            self.log(f"[STANDARD] Error in standard extraction: {str(e)}", "error")
            if self.helper:
                self.helper.log_error(traceback.format_exc())
            else:
                traceback.print_exc()
            return {"error": str(e), "text": None}
    
    def _extract_direct(self, url):
        """
        wgetを使用した直接記事抽出 + newspaperパース
        
        Args:
            url: 記事のURL
            
        Returns:
            dict: 抽出結果を含む辞書、または失敗時はエラー情報
        """
        temp_path = None
        try:
            self.log(f"[DIRECT] Attempting wget direct extraction for {url}")
            
            # 一時ファイルを作成
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as temp_file:
                temp_path = temp_file.name
            
            self.log(f"[DIRECT] Using temporary file: {temp_path}")
            
            # User-Agentを指定してwgetでHTMLを取得
            wget_cmd = [
                self.WGET_COMMAND,
                f"--user-agent={self.user_agent}",
                f"--timeout={self.WGET_TIMEOUT}",
                f"--tries={self.WGET_TRIES}",
                "--quiet",
                "-O", temp_path,
                url
            ]
            
            self.log(f"[DIRECT] Executing wget command")
            # 結果をログに出力するためにsubprocessを実行
            process = subprocess.run(wget_cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                self.log(f"[DIRECT] wget command failed: {process.stderr}")
                self._cleanup_temp_file(temp_path)
                return {"error": f"wget failed: {process.stderr}", "text": None}
            
            # ファイルサイズを確認
            file_size = os.path.getsize(temp_path)
            self.log(f"[DIRECT] Retrieved HTML file size: {file_size} bytes")
            
            if file_size < 100:
                self.log("[DIRECT] HTML file too small")
                self._cleanup_temp_file(temp_path)
                return {"error": "HTML file too small", "text": None}
            
            # ファイルの内容を読み込む
            with open(temp_path, 'r', encoding='utf-8', errors='replace') as f:
                html_content = f.read()
            
            # newspaper3kのパーサーを使用してコンテンツを解析
            config = self._get_newspaper_config(fetch_images=True)
            article = Article('', config=config)  # URLは空でOK
            article.html = html_content
            article.download_state = 2  # ダウンロード済みとマーク
            
            try:
                # HTMLをパース
                article.parse()
            except Exception as parse_error:
                self.log(f"[DIRECT] Parse error: {str(parse_error)}")
                self._cleanup_temp_file(temp_path)
                return {"error": f"Parse error: {str(parse_error)}", "text": None}
            
            # 一時ファイルを削除
            self._cleanup_temp_file(temp_path)
            
            # 画像情報を収集
            images = []
            if hasattr(article, 'images') and article.images:
                images = list(article.images)
                self.log(f"[DIRECT] Extracted {len(images)} images")
            
            if article.top_image:
                self.log(f"[DIRECT] Found top image: {article.top_image}")
            
            # テキスト抽出の結果を確認
            if article.text and len(article.text.strip()) > self.MIN_TEXT_LENGTH:
                self.log(f"[DIRECT] Successfully extracted {len(article.text)} chars")
                return self._build_article_result(article, html_content)
            else:
                self.log(f"[DIRECT] Parsing succeeded but insufficient text: {len(article.text if article.text else '')} chars")
                return {"error": "Insufficient text content", "text": article.text}
            
        except Exception as e:
            self.log(f"[DIRECT] Error: {str(e)}", "error")
            if self.helper:
                self.helper.log_error(traceback.format_exc())
            else:
                traceback.print_exc()
            # 一時ファイルを確実に削除
            self._cleanup_temp_file(temp_path)
            return {"error": str(e), "text": None}
    
    def _extract_advanced(self, url):
        """
        高度な記事抽出メソッド - 高度なブラウザエミュレーション
        
        Args:
            url: 記事のURL
            
        Returns:
            dict: 抽出結果を含む辞書、または失敗時はエラー情報
        """
        try:
            # URLからドメインを抽出
            parsed_url = urlparse(url)
            domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # 高度な設定をする（画像取得を有効化）
            config = self._get_newspaper_config(timeout=60, fetch_images=True)
            
            # 手動でセッションを管理（高度なエミュレーション）
            session = requests.Session()
            
            # 高度なヘッダーセットアップ
            advanced_headers = self._get_advanced_headers()
            
            # セッションにヘッダーを設定
            for key, value in advanced_headers.items():
                session.headers[key] = value
                
            self.log(f"[ADVANCED] Using advanced browser emulation")
            self.log(f"[ADVANCED] User-Agent: {session.headers['User-Agent']}")
            
            # ステップ1: まずトップページにアクセス（より高度なエミュレーション）
            try:
                self.log(f"[ADVANCED] Step 1: Visiting site homepage: {domain}")
                # Cookieを取得するためにトップページにアクセス
                top_response = session.get(domain, timeout=30)
                self.log(f"[ADVANCED] Homepage access status: {top_response.status_code}")
                
                # 自然なブラウジングをエミュレート - より長めの待機時間
                wait_time = random.uniform(2.0, 4.0)
                self.log(f"[ADVANCED] Waiting {wait_time:.2f}s to emulate natural browsing")
                time.sleep(wait_time)
                
                # リファラーを更新
                session.headers['Referer'] = domain
                session.headers['Sec-Fetch-Site'] = 'same-origin'
                
                self.log("[ADVANCED] Homepage visit complete")
            except Exception as e:
                self.log(f"[ADVANCED] Homepage access error (continuing): {str(e)}")
            
            # ステップ2: 目的のページにアクセス - より高度なエミュレーション
            self.log(f"[ADVANCED] Step 2: Visiting target article: {url}")
            
            # 追加のヘッダーでページ読み込み
            custom_headers = {
                'Purpose': 'prefetch',
                'Sec-Purpose': 'prefetch',
                'Sec-Fetch-Site': 'same-origin'
            }
            for key, value in custom_headers.items():
                session.headers[key] = value
                
            response = session.get(url, timeout=45)  # より長いタイムアウト
            status_code = response.status_code
            self.log(f"[ADVANCED] Article request status code: {status_code}")
            
            if status_code != 200:
                self.log(f"[ADVANCED] Failed to access article, status code: {status_code}")
                return {"error": f"Failed with status code {status_code}", "text": None}
            
            # さらに待機して自然なページ読み込みをエミュレート
            time.sleep(random.uniform(1.0, 2.0))
            
            # 取得したHTMLでArticleオブジェクトを手動で設定
            self.log(f"[ADVANCED] Retrieved HTML size: {len(response.text)} bytes")
            self.log("[ADVANCED] Parsing content with newspaper")
            
            article = Article(url, config=config)
            article.html = response.text
            article.download_state = 2  # ダウンロード完了状態を設定
            
            # 記事をパース
            try:
                article.parse()
            except Exception as parse_error:
                self.log(f"[ADVANCED] Error parsing article: {str(parse_error)}")
                return {"error": f"Failed to parse article: {str(parse_error)}", "text": None}
            
            # 画像情報を収集
            images = []
            if hasattr(article, 'images') and article.images:
                images = list(article.images)
                self.log(f"[ADVANCED] Extracted {len(images)} images")
            
            if article.top_image:
                self.log(f"[ADVANCED] Found top image: {article.top_image}")
            
            # 記事のテキストを確認
            if article.text and len(article.text.strip()) > self.MIN_TEXT_LENGTH:
                self.log(f"[ADVANCED] Successfully extracted article: {len(article.text)} chars")
                self.log(f"[ADVANCED] Title: {article.title}")
                
                return self._build_article_result(article)
            else:
                self.log("[ADVANCED] Article parsing succeeded but no meaningful text was extracted")
                return {"error": "No meaningful text in the article", "text": article.text if article.text else None}
            
        except Exception as e:
            self.log(f"[ADVANCED] Error in advanced extraction: {str(e)}", "error")
            if self.helper:
                self.helper.log_error(traceback.format_exc())
            else:
                traceback.print_exc()
            return {"error": str(e), "text": None}

    def convert_html_to_pdf(self, html_content, wkhtmltopdf_path, url="", 
                        preserve_layout=True, include_images=True, image_quality=85,
                        ad_removal_strategy="auto"):
        """
        強化された画像保持と自動戦略判定を組み合わせたPDF変換
        
        Args:
            html_content: HTML内容
            wkhtmltopdf_path: wkhtmltopdfのパス
            url: 元のURL
            preserve_layout: レイアウトを保持するか
            include_images: 画像を含めるか
            image_quality: 画像品質（1-100）
            ad_removal_strategy: 広告除去戦略 ("extract", "minimal", "auto")
            
        Returns:
            bytes: PDF内容、または失敗時はNone
        """
        temp_html_path = None
        pdf_path = None
        
        try:
            # デバッグ出力
            self.log("Starting enhanced PDF conversion process")
            self.log(f"HTML content size: {len(html_content) if html_content else 0} bytes")
            self.log(f"Using wkhtmltopdf path: {wkhtmltopdf_path}")
            
            # WordPressサイト検出とプリプロセス
            if self._is_wordpress_site(html_content, url):
                self.log("WordPress site detected, applying specialized processing")
                html_content = self._process_wordpress_html(html_content, url)
                # WordPressサイトは常にextract戦略を使用
                ad_removal_strategy = "extract"
            
            # 1. 自動戦略判定（HTMLの複雑さに基づく）
            if ad_removal_strategy == "auto":
                ad_removal_strategy = self._determine_best_strategy(html_content, url)
                self.log(f"Auto-selected strategy: {ad_removal_strategy} based on layout analysis")
  
            # 2. HTMLプリプロセッシング - コンテンツ画像を識別して保護
            if include_images:
                html_content = self._enhance_content_images(html_content)
                self.log("Enhanced content images with protective markup")
            
            # 3. 選択された戦略に基づいてHTMLを処理
            if ad_removal_strategy == "extract":
                # extract戦略 - 記事の抽出と再構築
                self.log("Using 'extract' strategy - extracting and rebuilding content")
                article_data = self.extract_article(url)
                
                if article_data and article_data.get("text"):
                    cleaned_html = self._build_clean_article_html(
                        article_data.get("title", ""), 
                        article_data.get("text", ""),
                        article_data.get("top_image"),
                        article_data.get("images", []),
                        url, include_images
                    )
                    self.log(f"Created clean article HTML from extracted content ({len(cleaned_html)} bytes)")
                else:
                    # 抽出に失敗した場合は選択的クリーニングにフォールバック
                    self.log("Extraction failed, falling back to selective cleaning")
                    cleaned_html = self._selective_layout_cleaning(html_content)
                    cleaned_html = self._prepare_html_for_better_layout(cleaned_html, url, include_images)
            else:  # "minimal" 戦略
                # minimal戦略 - レイアウトを保持しながら問題要素を除去
                self.log("Using 'minimal' strategy - preserving layout with selective cleaning")
                cleaned_html = self._selective_layout_cleaning(html_content)
                cleaned_html = self._prepare_html_for_better_layout(cleaned_html, url, include_images)
                
                # 結果の品質をチェック
                if not self._is_valid_processed_html(cleaned_html):
                    self.log("Minimal strategy produced poor results, falling back to extract")
                    # extractにフォールバック
                    article_data = self.extract_article(url)
                    if article_data and article_data.get("text"):
                        cleaned_html = self._build_clean_article_html(
                            article_data.get("title", ""), 
                            article_data.get("text", ""),
                            article_data.get("top_image"),
                            article_data.get("images", []),
                            url, include_images
                        )
            
            # 4. レイアウト修復CSSを追加（両方の戦略で共通）
            if '</head>' in cleaned_html:
                cleaned_html = cleaned_html.replace('</head>', f'{self._get_layout_repair_css()}</head>')
            
            # 専用のランタイムディレクトリを作成（権限問題解決）
            try:
                runtime_dir = "/tmp/runtime-pdf"
                os.makedirs(runtime_dir, mode=0o700, exist_ok=True)
                os.environ['XDG_RUNTIME_DIR'] = runtime_dir
                self.log(f"Set XDG_RUNTIME_DIR to {runtime_dir}")
            except Exception as runtime_error:
                self.log(f"Failed to create runtime directory: {str(runtime_error)}", "warning")
                # Qtのエラーを抑制
                os.environ['QT_LOGGING_RULES'] = "qt.qpa.xcb=false;*.debug=false"
            
            # 一時ファイルを使用してPDFを生成
            try:
                with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
                    temp_html.write(cleaned_html.encode('utf-8'))
                    temp_html_path = temp_html.name
                
                pdf_path = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False).name
                
                self.log(f"Using temporary files: HTML={temp_html_path}, PDF={pdf_path}")
                
                # 最適化されたオプション設定
                cmd = [
                    wkhtmltopdf_path,
                    "--quiet",
                    "--page-size", "A4",
                    "--encoding", "UTF-8",
                    "--enable-local-file-access",
                    "--margin-top", "10mm",
                    "--margin-right", "10mm", 
                    "--margin-bottom", "15mm",
                    "--margin-left", "10mm",
                    "--disable-javascript",  # JavaScriptは無効化（タイムアウト防止）
                    "--load-error-handling", "ignore",
                    "--load-media-error-handling", "ignore",
                    "--no-stop-slow-scripts",  # 追加: スクリプト実行を中断しない
                    "--disable-smart-shrinking",  # 追加: スマート縮小を無効化（速度向上）
                ]
                
                # 画像設定
                if include_images:
                    cmd.append("--images")
                else:
                    cmd.append("--no-images")
                
                # 入出力ファイルパスの追加
                cmd.extend([temp_html_path, pdf_path])
                
                self.log(f"Executing command: {' '.join(cmd)}")
                
                # 環境変数を準備
                env = os.environ.copy()
                env['QT_LOGGING_RULES'] = "qt.qpa.xcb=false;*.debug=false"
                
                # タイムアウト設定
                timeout_seconds = 120  # 40秒から120秒に延長
                
                # コマンド実行
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    env=env
                )
                
                self.log(f"Command exit code: {process.returncode}")
                if process.stdout:
                    self.log(f"Command stdout: {process.stdout[:500]}")
                if process.stderr:
                    self.log(f"Command stderr: {process.stderr[:500]}", "warning")
                
                if process.returncode != 0:
                    self.log(f"wkhtmltopdf command failed with code {process.returncode}", "error")
                    return None
                
                # PDFファイルを読み込む
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_content = pdf_file.read()
                    
                    self.log(f"Successfully generated PDF, size: {len(pdf_content)} bytes")
                    return pdf_content
                else:
                    self.log(f"PDF file not created or empty", "error")
                    return None
                    
            except subprocess.TimeoutExpired as timeout_error:
                self.log(f"PDF conversion timed out: {str(timeout_error)}", "error")
                return None
                
            except Exception as temp_file_error:
                self.log(f"Error with temp files: {str(temp_file_error)}", "error")
                return None
            
        except Exception as e:
            self.log(f"Error converting HTML to PDF: {str(e)}", "error")
            traceback.print_exc()
            return None
        
        finally:
            # 一時ファイルを確実に削除
            self._cleanup_temp_files([temp_html_path, pdf_path])

    def _determine_best_strategy(self, html_content, url):
        """
        HTMLの複雑さに基づいて最適な処理戦略を判断
        
        Args:
            html_content: HTML内容
            url: 元のURL
            
        Returns:
            str: 戦略名 ("extract" または "minimal")
        """
        # WordPressサイトの場合は常にextract戦略を使用
        if self._is_wordpress_site(html_content, url):
            self.log("WordPress site detected - using extract strategy")
            return "extract"
        
        # 複雑なレイアウトの特徴を検出
        has_complex_layout = (
            re.search(r'display\s*:\s*grid', html_content) or
            re.search(r'display\s*:\s*flex', html_content) or
            len(re.findall(r'<div', html_content)) > 100 or
            len(re.findall(r'<script', html_content)) > 15
        )
        
        # 多階層のネストされた構造をチェック
        nested_level = 0
        for tag in ['div', 'section', 'article']:
            pattern = f'<{tag}[^>]*>'
            matches = re.findall(pattern, html_content)
            # 非常に多くのネストがある場合
            if len(matches) > 50:
                nested_level += 1
        
        # 特定のサイトパターンをチェック
        problematic_domains = ['therecord.media', 'theverge.com', 'wired.com', 'securityboulevard.com']
        domain_match = False
        if url:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            for prob_domain in problematic_domains:
                if prob_domain in domain:
                    domain_match = True
                    break
        
        # 決定ロジック
        if (has_complex_layout and nested_level >= 2) or domain_match:
            return "extract"  # 複雑なレイアウトにはextract戦略
        else:
            return "minimal"  # シンプルなレイアウトにはminimal戦略

    def _is_valid_processed_html(self, html_content):
        """
        処理されたHTMLの品質をチェック
        
        Args:
            html_content: 処理済みのHTML
            
        Returns:
            bool: 有効な場合True
        """
        # 1. テキスト/HTMLの比率が低すぎないか
        text_ratio = len(re.findall(r'[a-zA-Z0-9]', html_content)) / max(len(html_content), 1)
        if text_ratio < 0.05:  # テキスト率が5%未満
            return False
        
        # 2. 本文コンテンツが含まれているか
        content_containers = ['<article', '<div class="content"', '<div class="article"', '<main']
        has_content = any(container in html_content for container in content_containers)
        if not has_content:
            return False
        
        # 3. ページが極端に大きくないか（巨大なHTMLは問題の兆候）
        if len(html_content) > 500000:  # 500KB以上
            return False
        
        return True
    
    def _enhance_content_images(self, html_content):
        """
        記事関連の画像を識別して強化
        
        Args:
            html_content: 元のHTML
            
        Returns:
            str: 画像強化済みのHTML
        """
        try:
            # lxmlを使用してDOMを解析
            doc = html.document_fromstring(html_content)
            
            # メインコンテンツエリアを特定するセレクタ
            content_selectors = [
                'article', '.article', '.content', 'main', '.main', '.post', 
                '.entry', '[itemprop="articleBody"]', '.story'
            ]
            
            # コンテンツエリアを検索
            content_elements = []
            for selector in content_selectors:
                try:
                    elements = doc.cssselect(selector)
                    if elements:
                        content_elements.extend(elements)
                except Exception:
                    continue
                
            # コンテンツエリア内の画像を保護
            if content_elements:
                for element in content_elements:
                    try:
                        for img in element.cssselect('img'):
                            # 小さすぎる画像やアイコンは除外
                            width = img.get('width')
                            if width and width.isdigit() and int(width) < 50:
                                continue
                                
                            # 広告っぽい画像は除外
                            img_class = img.get('class', '').lower()
                            img_src = img.get('src', '').lower()
                            if any(term in img_class or term in img_src for term in ['ad', 'banner', 'icon', 'logo']):
                                continue
                            
                            # コンテンツ画像として保護
                            img.set('class', (img.get('class', '') + ' content-image-preserve').strip())
                            img.set('style', (img.get('style', '') + '; max-width: 100% !important; height: auto !important;').strip())
                    except Exception:
                        continue
            
            # 変更後のHTMLを返す
            return html.tostring(doc).decode('utf-8')
        
        except Exception as e:
            self.log(f"Error enhancing content images: {str(e)}", "warning")
            
        # エラー時は元のHTMLを返す
        return html_content
    
    def _selective_layout_cleaning(self, html_content):
        """
        レイアウトをなるべく維持しながら問題要素を除去
        
        Args:
            html_content: 元のHTML
            
        Returns:
            str: クリーニング済みのHTML
        """
        # 1. 最も問題のある要素を選択的に除去
        patterns_to_remove = [
            # 広告関連
            (r'<div[^>]*(?:ad|advertisement|banner|sponsor|promo)[^>]*>.*?</div>', ''),
            (r'<aside[^>]*>.*?</aside>', ''),  # サイドバー要素
            # ソーシャルボタン、関連記事
            (r'<div[^>]*(?:social|share|related|recommend)[^>]*>.*?</div>', ''),
            # iframe（動画埋め込みを除く）
            (r'<iframe[^>]*(?:ad|advertisement|banner)[^>]*>.*?</iframe>', ''),
        ]
        
        for pattern, replacement in patterns_to_remove:
            html_content = re.sub(pattern, replacement, html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. グリッド/フレックスレイアウトを調整
        layout_fixes = [
            (r'display\s*:\s*grid[^;]*;', 'display: block;'),
            (r'display\s*:\s*flex[^;]*;', 'display: block;'),
            (r'position\s*:\s*fixed[^;]*;', 'position: static;'),
            (r'position\s*:\s*sticky[^;]*;', 'position: static;'),
        ]
        
        for pattern, replacement in layout_fixes:
            html_content = re.sub(pattern, replacement, html_content)
        
        # 3. インラインスクリプトを削除
        html_content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content, flags=re.DOTALL)
        
        # 4. オンロードハンドラなどのJavaScriptイベントを削除
        js_events = ['onclick', 'onload', 'onscroll', 'onmouseover', 'onmouseout']
        for event in js_events:
            html_content = re.sub(f' {event}="[^"]*"', '', html_content)
        
        return html_content
    
    def _prepare_html_for_better_layout(self, html_content, url="", include_images=True):
        """
        レイアウト保持を強化したHTML前処理
        
        Args:
            html_content: 元のHTML文字列
            url: 元のURL
            include_images: 画像を含めるかどうか
            
        Returns:
            str: 処理済みHTML
        """
        try:
            if not html_content:
                return html_content
                
            # 安全なHTML構造を確保
            has_html_tag = re.search(r'<html.*?>.*?</html>', html_content, re.DOTALL) is not None
            has_head_tag = '<head>' in html_content and '</head>' in html_content
            has_body_tag = '<body' in html_content and '</body>' in html_content
            
            # ベースURLの設定（相対パスの解決に必要）
            base_url_tag = ""
            if url:
                try:
                    parsed_url = urlparse(url)
                    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    base_url_tag = f'<base href="{base_url}/">'
                except:
                    pass
            
            # PDF出力最適化用のCSS - レイアウト保持強化版
            pdf_css = """
            <style>
                @page {
                    size: A4;
                    margin: 10mm 10mm 15mm 10mm;
                }
                
                /* リンクのスタイル保持 */
                a {
                    color: inherit;
                    text-decoration: inherit;
                }
                
                /* 画像の適切な拡大縮小 */
                img {
                    max-width: 100%;
                    height: auto;
                    page-break-inside: avoid;
                }
                
                /* 改ページコントロール */
                h1, h2, h3, h4, h5, h6 {
                    page-break-after: avoid;
                    page-break-inside: avoid;
                }
                
                /* テーブルレイアウト保持 */
                table {
                    border-collapse: collapse;
                    width: 100%;
                    page-break-inside: avoid;
                }
                
                /* フッタースタイル */
                .pdf-footer {
                    text-align: center;
                    font-size: 9pt;
                    color: #666;
                    margin-top: 20px;
                    padding-top: 10px;
                    border-top: 1px solid #ccc;
                }
            </style>
            """
            
            # スクリプトを選択的に削除（問題のあるJavaScriptのみを削除）
            problematic_scripts = [
                r'<script[^>]*google-analytics[^>]*>.*?</script>',
                r'<script[^>]*gtm\.js[^>]*>.*?</script>',
                r'<script[^>]*facebook[^>]*>.*?</script>',
                r'<script[^>]*twitter[^>]*>.*?</script>',
                r'<script[^>]*ads[^>]*>.*?</script>',
                r'<script[^>]*analytics[^>]*>.*?</script>',
                r'<script[^>]*tracker[^>]*>.*?</script>'
            ]
            
            for pattern in problematic_scripts:
                html_content = re.sub(pattern, '', html_content, flags=re.DOTALL | re.IGNORECASE)
            
            # 問題のあるiframeのみを削除
            html_content = re.sub(r'<iframe[^>]*(?:advertisement|ads|youtube|vimeo)[^>]*>.*?</iframe>', '', 
                                html_content, flags=re.DOTALL | re.IGNORECASE)
            
            # 完全なHTML構造を持たない場合は構築
            if not has_html_tag:
                new_html = "<!DOCTYPE html>\n<html>\n"
                
                # head要素を追加
                if not has_head_tag:
                    new_html += "<head>\n"
                    new_html += '  <meta charset="UTF-8">\n'
                    new_html += f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                    if url:
                        new_html += f'  <title>Article from {url}</title>\n'
                    else:
                        new_html += '  <title>Article</title>\n'
                    new_html += base_url_tag + "\n"
                    new_html += pdf_css + "\n"
                    new_html += "</head>\n"
                else:
                    # head要素があれば中身を取り出して拡張
                    head_match = re.search(r'<head>(.*?)</head>', html_content, re.DOTALL)
                    if head_match:
                        head_content = head_match.group(1)
                        new_html += "<head>\n"
                        if '<meta charset' not in head_content:
                            new_html += '  <meta charset="UTF-8">\n'
                        if '<meta name="viewport"' not in head_content:
                            new_html += f'  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                        new_html += base_url_tag + "\n"
                        new_html += head_content + "\n"
                        new_html += pdf_css + "\n"
                        new_html += "</head>\n"
                
                # body要素を追加
                if not has_body_tag:
                    new_html += "<body>\n"
                    new_html += html_content + "\n"
                    
                    # URLフッターを追加
                    if url:
                        new_html += f'<div class="pdf-footer">Source: {url}</div>\n'
                    
                    new_html += "</body>\n"
                else:
                    # body要素があれば抽出して追加
                    body_match = re.search(r'<body.*?>(.*?)</body>', html_content, re.DOTALL)
                    if body_match:
                        body_attributes = re.search(r'<body([^>]*)>', html_content)
                        body_attrs = body_attributes.group(1) if body_attributes else ""
                        new_html += f"<body{body_attrs}>\n"
                        new_html += body_match.group(1) + "\n"
                        
                        # URLフッターを追加
                        if url:
                            new_html += f'<div class="pdf-footer">Source: {url}</div>\n'
                        
                        new_html += "</body>\n"
                
                new_html += "</html>"
                html_content = new_html
            else:
                # 既にHTML構造がある場合は、必要な要素を追加/修正
                
                # head内にベースURLとPDF用CSSを追加
                if has_head_tag:
                    if base_url_tag and '<base' not in html_content:
                        html_content = html_content.replace('</head>', f'{base_url_tag}\n</head>')
                    html_content = html_content.replace('</head>', f'{pdf_css}\n</head>')
                
                # body終了タグの前にURLフッターを追加
                if has_body_tag and url:
                    footer_html = f'<div class="pdf-footer">Source: {url}</div>\n'
                    html_content = html_content.replace('</body>', f'{footer_html}</body>')
            
            return html_content
                
        except Exception as e:
            self.log(f"Error preprocessing HTML for better layout: {str(e)}", "warning")
            return html_content
    
    def _build_clean_article_html(self, title, text, top_image, images, url="", include_images=True):
        """
        抽出した記事コンテンツから整形されたHTMLを構築
        
        Args:
            title: 記事タイトル
            text: 記事本文
            top_image: メイン画像URL
            images: 画像URLリスト
            url: 元のURL
            include_images: 画像を含めるか
            
        Returns:
            str: 整形されたHTML
        """
        # CSS設定
        css = """
        <style>
            /* ページ設定 */
            @page {
                size: A4;
                margin: 10mm 10mm 15mm 10mm;
            }
            
            /* 基本設定 */
            body {
                font-family: Arial, Helvetica, sans-serif;
                font-size: 12pt;
                line-height: 1.5;
                color: #000;
                background-color: #fff;
                margin: 0;
                padding: 20px;
            }
            
            /* 記事コンテナ */
            .article-container {
                max-width: 100%;
                margin: 0 auto;
            }
            
            /* タイトル */
            .article-title {
                font-size: 24pt;
                font-weight: bold;
                margin-bottom: 20px;
                line-height: 1.2;
                color: #333;
            }
            
            /* メイン画像 */
            .main-image {
                max-width: 100%;
                height: auto;
                margin: 20px 0;
                display: block;
            }
            
            /* 記事本文 */
            .article-content {
                margin-top: 20px;
                font-size: 12pt;
                line-height: 1.6;
            }
            
            /* 段落 */
            .article-content p {
                margin: 12px 0;
            }
            
            /* 画像 */
            .article-content img {
                max-width: 100%;
                height: auto;
                margin: 15px 0;
                display: block;
            }
            
            /* フッター */
            .article-footer {
                margin-top: 30px;
                padding-top: 10px;
                border-top: 1px solid #ccc;
                font-size: 10pt;
                color: #666;
                text-align: center;
            }
        </style>
        """
        
        # テキストを段落に分割
        paragraphs = text.split('\n\n')
        
        # 記事本文をHTMLに変換
        content_html = ""
        for paragraph in paragraphs:
            if paragraph.strip():
                content_html += f"<p>{paragraph.strip()}</p>\n"
        
        # 本文中の画像を追加（指定された場合）
        image_html = ""
        if include_images and images:
            # メイン画像（すでにトップに表示されている場合は除く）
            used_images = set()
            if top_image:
                used_images.add(top_image)
            
            # 記事内の画像（最大5枚まで）
            image_count = 0
            for img_url in images:
                if img_url not in used_images and image_count < 5:
                    # 相対URLを絶対URLに変換
                    if url and not img_url.startswith(('http://', 'https://')):
                        img_url = urljoin(url, img_url)
                    
                    # 段落の間に画像を挿入（コンテンツの適切な位置に）
                    insert_pos = min(
                        len(content_html) // 2 + image_count * (len(content_html) // 10),
                        len(content_html) - 1
                    )
                    content_html = (
                        content_html[:insert_pos] + 
                        f'<img src="{img_url}" alt="" class="article-image" />\n' + 
                        content_html[insert_pos:]
                    )
                    
                    used_images.add(img_url)
                    image_count += 1
        
        # HTML文書の構築
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            {css}
        </head>
        <body>
            <div class="article-container">
                <h1 class="article-title">{title}</h1>
                
                {f'<img src="{top_image}" alt="{title}" class="main-image" />' if top_image and include_images else ''}
                
                <div class="article-content">
                    {content_html}
                </div>
                
                <div class="article-footer">
                    Source: {url if url else 'Unknown source'}
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _get_layout_repair_css(self):
        """
        レイアウト修復用のCSS
        
        Returns:
            str: CSSスタイルタグ
        """
        return """
        <style>
            /* 本文コンテンツの強制表示 */
            article, .article, main, .main, .content, .post, .entry, [itemprop="articleBody"], .story {
                display: block !important;
                width: 100% !important;
                max-width: 100% !important;
                position: static !important;
                overflow: visible !important;
                padding: 10px 0 !important;
                margin: 0 auto !important;
                float: none !important;
            }
            
            /* コンテンツ画像の保持と最適化 */
            .content-image-preserve {
                display: block !important;
                max-width: 90% !important;
                height: auto !important;
                margin: 10px auto !important;
                page-break-inside: avoid !important;
            }
            
            /* 見出し最適化 */
            h1, h2, h3 {
                page-break-after: avoid !important;
                margin-top: 20px !important;
                margin-bottom: 10px !important;
            }
            
            /* テキスト最適化 */
            p {
                margin: 10px 0 !important;
                line-height: 1.5 !important;
            }
            
            /* 大きな画像のページ内表示 */
            img {
                page-break-inside: avoid !important;
            }
            
            /* フッタースタイル */
            .pdf-footer {
                text-align: center;
                font-size: 9pt;
                color: #666;
                margin-top: 20px;
                padding-top: 10px;
                border-top: 1px solid #ccc;
            }
        </style>
        """
    
    def _get_common_headers(self):
        """
        全ての取得方法で使用する共通HTTPヘッダーを取得
        
        Returns:
            dict: HTTPヘッダー辞書
        """
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.google.com/',
            'Cache-Control': 'max-age=0'
        }
    
    def _get_advanced_headers(self):
        """
        高度なブラウザエミュレーション用のHTTPヘッダーを取得
        
        Returns:
            dict: 拡張HTTPヘッダー辞書
        """
        return {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,ja;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'DNT': '1',
            'Referer': 'https://www.google.com/',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Google Chrome";v="115", "Chromium";v="115", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    
    def _cleanup_temp_files(self, file_paths):
        """
        複数の一時ファイルを安全に削除
        
        Args:
            file_paths: 削除するファイルパスのリスト
        """
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    self.log(f"Deleted temp file: {file_path}")
                except Exception as e:
                    self.log(f"Failed to delete temp file {file_path}: {str(e)}", "warning")
    
    def _cleanup_temp_file(self, file_path):
        """
        一時ファイルを安全に削除
        
        Args:
            file_path: 削除するファイルのパス
        """
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception as e:
                self.log(f"Failed to delete temp file {file_path}: {str(e)}", "warning")

    def _is_wordpress_site(self, html_content, url):
        """
        WordPressサイトかどうかを検出 - 強化版
        
        Args:
            html_content: HTML内容
            url: 記事URL
            
        Returns:
            bool: WordPressサイトの場合True
        """
        # 処理開始のログ（デバッグモード時のみ）
        if hasattr(self, 'debug_mode') and self.debug_mode:
            self.log(f"Checking if site is WordPress: {url}")
        
        # ===== 既存の検出方法 =====
        
        # 検出方法 (1) - メタジェネレータータグで検出
        if re.search(r'<meta[^>]*name=["\']generator["\'][^>]*content=["\']WordPress', html_content, re.IGNORECASE):
            self.log("WordPress site detected via meta generator tag")
            return True
            
        # 検出方法 (2) - 特定のリソースパターンで検出
        if re.search(r'wp-(?:content|includes)', html_content):
            self.log("WordPress site detected via resource patterns")
            return True
        
        # 検出方法 (3) - WordPressテーマに特有のクラス検出
        wp_classes = [
            'wp-block-', 'entry-content', 'post-content', 'the-content',
            'widget-area', 'site-header', 'site-footer', 'wp-caption'
        ]
        for wp_class in wp_classes:
            if re.search(f'class=["\'][^"\']*{wp_class}', html_content):
                self.log(f"WordPress site detected via class '{wp_class}'")
                return True
        
        # 検出方法 (4) - URLを確認
        if url and ('/wp-content/' in url or '/wp-includes/' in url):
            self.log("WordPress site detected via URL pattern")
            return True
        
        # ===== HackerNewsサイトから学んだパターン =====
        
        # 検出方法 (5) - Blogger/WordPress共通画像パターン検出
        if re.search(r'blogger\.googleusercontent\.com/img/', html_content):
            self.log("WordPress site detected via Blogger image pattern")
            return True
        
        # 検出方法 (6) - 年/月/タイトル.html の典型的なブログURL構造
        if url and re.search(r'/(20\d{2})/(0[1-9]|1[0-2])/[\w-]+\.html', url):
            self.log("WordPress site detected via permalink structure")
            return True
        
        # 検出方法 (7) - 拡張WordPress記事構造検出
        article_patterns = [
            # 記事コンテナ
            r'<article[^>]*class=["\'][^"\']*(?:post|entry|blog-post)',
            # 投稿タイトル
            r'<h\d[^>]*class=["\'][^"\']*(?:post-title|entry-title)',
            # 投稿メタ情報
            r'<div[^>]*class=["\'][^"\']*(?:post-meta|entry-meta)',
            # 一般的なコメントセクション
            r'<div[^>]*id=["\'](?:comments|respond)',
            # 共有ボタン
            r'<div[^>]*class=["\'][^"\']*(?:share-buttons|social-share)',
            # 典型的なRSS/AtomフィードURL
            r'<link[^>]*rel=["\']alternate["\'][^>]*type=["\']application/(?:rss\+xml|atom\+xml)'
        ]
        
        # いずれかのパターンが一致すればWordPressと判定
        for pattern in article_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                self.log(f"WordPress site detected via extended article pattern")
                return True
        
        # 検出方法 (8) - WordPress埋め込みJavaScriptシグネチャ
        js_patterns = [
            r'wp-embed\.min\.js', 
            r'wp-emoji-release\.min\.js',
            r'jquery/jquery\.js\?ver=',
            r'wp-includes/js/',
            r'_wpnonce'
        ]
        
        for pattern in js_patterns:
            if re.search(pattern, html_content):
                self.log(f"WordPress site detected via JavaScript pattern")
                return True
        
        # ===== TheRecordサイトから学んだパターン =====
        
        # 検出方法 (9) - Markdownリンク構文検出
        if re.search(r'\[[\w\s]+\]\(https?://[^\)]+\)', html_content):
            self.log("WordPress site detected via Markdown link syntax")
            return True
        
        # 検出方法 (10) - 拡張記事構造パターン
        enhanced_article_patterns = [
            # レポーター/著者情報ブロック
            r'<div[^>]*(?:author|byline)[^>]*>.*?<\/div>',
            # 関連記事セクションパターン
            r'<div[^>]*(?:related|more-stories)[^>]*>.*?<\/div>',
            # 記事メタデータパターン
            r'<div[^>]*(?:meta|article-info)[^>]*>.*?<\/div>'
        ]
        
        for pattern in enhanced_article_patterns:
            if re.search(pattern, html_content, re.IGNORECASE | re.DOTALL):
                self.log("WordPress site detected via enhanced article structure pattern")
                return True
        
        # 検出方法 (11) - ヘッダー/フッター構造（HackerNewsの拡張）
        header_footer_patterns = [
            r'<header[^>]*class=["\'][^"\']*(?:site-header|main-header)',
            r'<footer[^>]*class=["\'][^"\']*(?:site-footer|main-footer)',
            r'<div[^>]*class=["\'][^"\']*(?:copyright|site-info)'
        ]
        
        for pattern in header_footer_patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                self.log(f"WordPress site detected via header/footer pattern")
                return True
        
        # どのパターンにも一致しなかった場合
        if hasattr(self, 'debug_mode') and self.debug_mode:
            self.log(f"No WordPress patterns detected for: {url}")
        
        return False

    def _process_wordpress_html(self, html_content, url=""):
        """
        WordPressサイト専用のHTML処理 - 強化版
        
        Args:
            html_content: 元のHTML内容
            url: 記事URL
            
        Returns:
            str: 処理済みHTML
        """
        self.log("Applying WordPress-specific processing with enhanced layout")
        
        try:
            # ドキュメントをパース
            doc = html.document_fromstring(html_content)
            
            # 1. 不要な要素を削除
            elements_to_remove = [
                # コメントセクションなど既存の削除対象
                '.comments-area', '#comments', '.comment-respond',
                '.sidebar', '.widget-area', '.widgets-list',
                '.related-posts', '.yarpp', '.jp-relatedposts',
                '.sharedaddy', '.share-buttons', '.social-share',
                '.post-navigation', '.nav-links', '.prev-next',
                '.advertisement', '.adsbygoogle', '[id*="gpt"]', '[class*="ads-"]',
                # さらに追加の不要要素
                '.popup', '.modal', '.cookie-notice', '.gdpr', 
                'script', 'iframe[src*="ads"]', 'iframe[src*="doubleclick"]'
            ]
            
            for selector in elements_to_remove:
                try:
                    for element in doc.cssselect(selector):
                        if element.getparent() is not None:
                            element.getparent().remove(element)
                except Exception as e:
                    if self.debug_mode:
                        self.log(f"Error removing element with selector {selector}: {str(e)}", "warning")
                    continue
            
            # 2. メインコンテンツを特定 - 優先順位付きセレクタリスト
            main_content = None
            main_selectors = [
                'article.post', # 最優先
                'article .entry-content',
                '.post-content',
                '.post .entry-content',
                'article.post',
                '.the-content',
                '#content .post',
                '.entry-content',
                'article',
                '.post',
                '.content',
                # 追加セレクタ
                'main',
                '.main-content',
                '#primary',
                '.site-content article'
            ]
            
            # 3. テーマ検出を追加
            theme_pattern = re.search(r'wp-content/themes/([^/]+)', html_content)
            detected_theme = theme_pattern.group(1) if theme_pattern else None
            
            if detected_theme:
                self.log(f"Detected WordPress theme: {detected_theme}")
                # テーマ固有のセレクタを追加
                if detected_theme in ['twentytwenty', 'twentytwentyone', 'twentytwentytwo']:
                    main_selectors.insert(0, '.entry-content')
                    main_selectors.insert(0, 'article .entry')
                elif detected_theme in ['astra', 'generatepress', 'oceanwp']:
                    main_selectors.insert(0, '.ast-article-single')
                    main_selectors.insert(0, '.content-area')
            
            # コンテンツ探索
            for selector in main_selectors:
                try:
                    elements = doc.cssselect(selector)
                    if elements:
                        main_content = elements[0]
                        self.log(f"Found main content using selector: {selector}")
                        break
                except Exception as e:
                    if self.debug_mode:
                        self.log(f"Error with selector {selector}: {str(e)}", "warning")
                    continue
            
            # 4. タイトル、メタ情報、アイキャッチ画像を取得
            title_text = "Article"
            title_selectors = ['h1.entry-title', 'h1.post-title', '.post h1', 'h1.title', 'header h1']
            for selector in title_selectors:
                try:
                    title_elements = doc.cssselect(selector)
                    if title_elements:
                        title_text = title_elements[0].text_content().strip()
                        break
                except:
                    continue
            
            # 5. 公開日を取得
            publish_date = ""
            date_selectors = ['.posted-on time', '.entry-date', '.post-date', 'time.entry-date', 'meta time']
            for selector in date_selectors:
                try:
                    date_elements = doc.cssselect(selector)
                    if date_elements:
                        publish_date = date_elements[0].text_content().strip()
                        break
                except:
                    continue
            
            # 6. 著者を取得
            author = ""
            author_selectors = ['.author', '.byline', '.post-author', '.entry-author']
            for selector in author_selectors:
                try:
                    author_elements = doc.cssselect(selector)
                    if author_elements:
                        author = author_elements[0].text_content().strip()
                        # "By "などの接頭辞を削除
                        author = re.sub(r'^(By|Posted by|Author[:]?)\s*', '', author, flags=re.IGNORECASE).strip()
                        break
                except:
                    continue
            
            # 7. アイキャッチ画像を取得
            featured_image = None
            image_selectors = ['.post-thumbnail img', '.featured-image img', '.post-image img', 'article img:first-child']
            for selector in image_selectors:
                try:
                    img_elements = doc.cssselect(selector)
                    if img_elements:
                        featured_image = img_elements[0]
                        # 相対URLを絶対URLに変換
                        if 'src' in featured_image.attrib and not featured_image.attrib['src'].startswith(('http://', 'https://')):
                            if url:
                                featured_image.attrib['src'] = urljoin(url, featured_image.attrib['src'])
                        break
                except:
                    continue
            
            # メインコンテンツが見つかった場合、元のサイトに似たHTMLを構築
            if main_content is not None:
                # 8. 画像要素を絶対URLに変換
                for img in main_content.cssselect('img'):
                    if 'src' in img.attrib:
                        src = img.attrib['src']
                        if not src.startswith(('http://', 'https://')):
                            if url:
                                img.attrib['src'] = urljoin(url, src)
                    # レスポンシブ画像の最適化
                    img.attrib['style'] = 'max-width: 100%; height: auto;'
                    # LazyLoad属性を処理
                    if 'data-src' in img.attrib and not img.attrib.get('src', ''):
                        img.attrib['src'] = img.attrib['data-src']
                
                # 9. リンク要素を絶対URLに変換
                for a in main_content.cssselect('a'):
                    if 'href' in a.attrib:
                        href = a.attrib['href']
                        if not href.startswith(('http://', 'https://', '#', 'mailto:')):
                            if url:
                                a.attrib['href'] = urljoin(url, href)
                
                # 10. WordPressのショートコードを削除
                main_html = html.tostring(main_content).decode('utf-8')
                main_html = re.sub(r'\[\/?[a-zA-Z0-9_-]+(?:\s[^\]]+)?\]', '', main_html)
                
                # 11. WordPressテーマに似せたCSSスタイルを構築
                wordpress_style = self._get_wordpress_theme_css(detected_theme)
                
                # 12. HTML文書の構築
                return f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>{title_text}</title>
                    {wordpress_style}
                </head>
                <body class="wordpress-theme {detected_theme if detected_theme else 'default'}">
                    <div id="page" class="site">
                        <div id="content" class="site-content">
                            <article class="post">
                                <header class="entry-header">
                                    <h1 class="entry-title">{title_text}</h1>
                                    <div class="entry-meta">
                                        {f'<span class="posted-on">{publish_date}</span>' if publish_date else ''}
                                        {f'<span class="byline">{author}</span>' if author else ''}
                                    </div>
                                </header>
                                
                                {f'<div class="post-thumbnail">{html.tostring(featured_image).decode("utf-8")}</div>' if featured_image is not None else ''}
                                
                                <div class="entry-content">
                                    {main_html}
                                </div>
                                
                                <footer class="entry-footer">
                                    <div class="source-link">
                                        Source: <a href="{url}">{url}</a>
                                    </div>
                                </footer>
                            </article>
                        </div>
                    </div>
                </body>
                </html>
                """
        
        except Exception as e:
            self.log(f"Error in WordPress processing: {str(e)}", "error")
            if self.helper:
                self.helper.log_error(traceback.format_exc())
            return html_content  # エラー時は元のHTMLを返す
        
        return html_content  # 変更がない場合も元のHTMLを返す

    def _get_wordpress_theme_css(self, theme_name=None):
        """
        WordPressテーマに似せたCSSを提供
        
        Args:
            theme_name: 検出されたテーマ名（オプション）
        
        Returns:
            str: スタイルタグを含むCSS
        """
        # 基本CSS（すべてのテーマに適用）
        base_css = """
        <style>
            /* 基本レイアウト */
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
                font-size: 16px;
                line-height: 1.8;
                color: #333;
                margin: 0;
                padding: 0;
                background: #fff;
            }
            #page {
                max-width: 1200px;
                margin: 0 auto;
                padding: 2em;
            }
            #content {
                width: 100%;
            }
            
            /* タイトルとヘッダー */
            .entry-title {
                font-size: 2.5em;
                line-height: 1.2;
                margin-bottom: 0.5em;
                color: #222;
                font-weight: 700;
            }
            .entry-meta {
                font-size: 0.9em;
                color: #666;
                margin-bottom: 2em;
            }
            .byline, .posted-on {
                margin-right: 1em;
            }
            
            /* アイキャッチ画像 */
            .post-thumbnail {
                margin-bottom: 2em;
                text-align: center;
            }
            .post-thumbnail img {
                max-width: 100%;
                height: auto;
                border-radius: 4px;
            }
            
            /* 記事コンテンツ */
            .entry-content {
                font-size: 1.1em;
                line-height: 1.8;
            }
            .entry-content p {
                margin-bottom: 1.5em;
            }
            .entry-content h2 {
                font-size: 1.8em;
                margin-top: 1.5em;
                margin-bottom: 0.8em;
                padding-bottom: 0.3em;
                border-bottom: 1px solid #eee;
            }
            .entry-content h3 {
                font-size: 1.5em;
                margin-top: 1.5em;
                margin-bottom: 0.8em;
            }
            .entry-content ul, .entry-content ol {
                margin-bottom: 1.5em;
                padding-left: 2em;
            }
            .entry-content li {
                margin-bottom: 0.5em;
            }
            .entry-content a {
                color: #0066cc;
                text-decoration: none;
            }
            .entry-content a:hover {
                text-decoration: underline;
            }
            .entry-content img {
                max-width: 100%;
                height: auto;
                margin: 1.5em 0;
                border-radius: 4px;
            }
            .entry-content blockquote {
                border-left: 4px solid #eee;
                padding-left: 1.5em;
                margin-left: 0;
                color: #666;
                font-style: italic;
            }
            .entry-content pre, .entry-content code {
                background: #f5f5f5;
                border-radius: 3px;
                padding: 0.2em 0.4em;
                font-family: monospace;
            }
            .entry-content pre {
                padding: 1em;
                overflow-x: auto;
            }
            
            /* フッター */
            .entry-footer {
                margin-top: 3em;
                padding-top: 1em;
                border-top: 1px solid #eee;
                font-size: 0.9em;
                color: #666;
            }
            .source-link {
                margin-top: 1em;
            }
            
            /* 印刷用最適化 */
            @page {
                margin: 1.5cm;
            }
            @media print {
                body {
                    font-size: 12pt;
                }
                a {
                    text-decoration: none;
                    color: #000;
                }
                .entry-title {
                    font-size: 24pt;
                }
                .entry-content {
                    font-size: 12pt;
                }
            }
        </style>
        """
        
        # テーマ固有のCSS（検出されたテーマに基づいて追加）
        theme_specific_css = ""
        if theme_name:
            if theme_name in ['twentytwenty', 'twentytwentyone', 'twentytwentytwo']:
                theme_specific_css = """
                <style>
                    body.wordpress-theme {
                        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
                    }
                    .entry-title {
                        font-weight: 800;
                    }
                    .entry-content h2 {
                        font-weight: 700;
                    }
                </style>
                """
            elif theme_name in ['astra', 'generatepress']:
                theme_specific_css = """
                <style>
                    body.wordpress-theme {
                        font-size: 17px;
                        line-height: 1.7;
                    }
                    .entry-title {
                        font-weight: 600;
                    }
                </style>
                """
        
        return base_css + theme_specific_css

