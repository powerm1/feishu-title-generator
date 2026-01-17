from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.feishu import get_feishu_token, update_batch_result


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}

            batch_num = data.get("batch") or data.get("Batch#") or data.get("batch_num")
            record_id = data.get("record_id")

            if not batch_num:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    "status": "ok",
                    "message": "Webhook已收到，但未提供批次号"
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            if record_id:
                try:
                    token = get_feishu_token()
                    update_batch_result(token, record_id, "处理中...")
                except Exception:
                    pass

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {
                "status": "accepted",
                "batch": batch_num,
                "record_id": record_id,
                "message": "任务已接收，请在控制台查看并处理"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {"status": "error", "error": str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))
