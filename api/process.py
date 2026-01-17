from http.server import BaseHTTPRequestHandler
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.feishu import (
    get_feishu_token, get_products_by_batch,
    write_to_output_table, update_batch_result
)
from lib.yunwu import generate_product_title


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
            data = json.loads(body) if body else {}

            batch_num = data.get("batch")
            record_id = data.get("record_id")

            if not batch_num:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing batch parameter"}).encode('utf-8'))
                return

            token = get_feishu_token()
            products = get_products_by_batch(token, batch_num)

            if not products:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    "success": False,
                    "message": "没有找到该批次的产品",
                    "batch": batch_num
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            results = []
            logs = []

            for i, product in enumerate(products):
                asin = product.get('asin', 'Unknown')
                try:
                    new_title = generate_product_title(product)
                    if new_title:
                        results.append({
                            "asin": asin,
                            "product_name": new_title
                        })
                        logs.append({
                            "index": i + 1,
                            "asin": asin,
                            "status": "success",
                            "title_length": len(new_title)
                        })
                    else:
                        logs.append({
                            "index": i + 1,
                            "asin": asin,
                            "status": "failed",
                            "error": "生成失败"
                        })
                except Exception as e:
                    logs.append({
                        "index": i + 1,
                        "asin": asin,
                        "status": "error",
                        "error": str(e)[:100]
                    })

            success_count = 0
            if results:
                success_count = write_to_output_table(token, results)

            if record_id:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result_text = f"已处理 {success_count}/{len(products)} | {timestamp}"
                update_batch_result(token, record_id, result_text)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {
                "success": True,
                "batch": batch_num,
                "total": len(products),
                "processed": len(results),
                "written": success_count,
                "logs": logs
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {"success": False, "error": str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))
