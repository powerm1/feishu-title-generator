from http.server import BaseHTTPRequestHandler
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.feishu import get_feishu_token, get_all_batches


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            token = get_feishu_token()
            batches = get_all_batches(token)

            pending = []
            completed = []

            for b in batches:
                batch_info = {
                    "batch": b["batch"],
                    "record_id": b["record_id"],
                    "coze_run": b["coze_run"],
                    "result": b["coze_result"] or ""
                }

                if b["coze_run"] and not b["coze_result"]:
                    batch_info["status"] = "pending"
                    pending.append(batch_info)
                elif b["coze_result"]:
                    batch_info["status"] = "completed"
                    completed.append(batch_info)
                else:
                    batch_info["status"] = "idle"
                    pending.append(batch_info)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {
                "success": True,
                "pending": pending,
                "completed": completed,
                "total": len(batches)
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))
