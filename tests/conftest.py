import os
import sys

import pytest

# プロジェクトルートを import パスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    """ワーカーを起動せずに Blueprint だけを登録したテスト用 Flask アプリ。

    Flask に依存しないテスト（ワーカー単体など）が Flask 未導入環境でも収集・
    実行できるよう、import はフィクスチャ内で遅延させる。
    """
    from flask import Flask
    from routes import register_blueprints
    from routes.filters import register_filters

    application = Flask(__name__)
    register_filters(application)
    register_blueprints(application)
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()
