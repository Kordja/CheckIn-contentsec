"""
Flask 应用入口。
运行方式: python api/app.py  或  python -m api.app
"""

import os
import sys

# 确保项目根目录在 sys.path 中
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from flask import Flask
from flask_cors import CORS

from api.routes import api
from db.database import init_db


def create_app():
    app = Flask(__name__, static_folder="../frontend", static_url_path="/")
    CORS(app)

    # 初始化数据库
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "checkin.db")
    init_db(db_path)

    # 注册 API 蓝图
    app.register_blueprint(api)

    # 首页
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    return app


if __name__ == "__main__":
    # 修复 Windows 下 stdout 编码
    if sys.stdout.encoding != "utf-8":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    app = create_app()
    print("启动 Flask 服务: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
