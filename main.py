from config import *
import os
import requests
from solver import Solver
from gevent import pywsgi
import time
from flask import Flask, request, render_template, Response, stream_with_context
import json


app = Flask(__name__)

# 定义API配置
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = siliconflow_api_key

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


@app.route("/")
def index():
    return render_template("index.html")


"""
yield json.dumps(data) + "\n"  # 每次生成一个 JSON 对象
"""


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    solver = Solver(data.get("data"), API_URL, HEADERS)
    return Response(stream_with_context(solver.start()), content_type='application/json')


if __name__ == "__main__":
    print("==========start==========")
    server = pywsgi.WSGIServer(('127.0.0.1', 5000), app)
    server.serve_forever()
    print("==========success==========")
