"""
处理批次端点
支持流式响应，逐个处理产品
"""
import json
import sys
import os
from datetime import datetime

# 添加 lib 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.feishu import (
    get_feishu_token, get_products_by_batch,
    write_to_output_table, update_batch_result
)
from lib.yunwu import generate_product_title


def handler(request):
    """Vercel Serverless Function handler"""
    # 处理 CORS
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }

    if request.method != "POST":
        return {
            "statusCode": 405,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Method not allowed"})
        }

    try:
        # 解析请求体
        body = request.body
        if isinstance(body, bytes):
            body = body.decode('utf-8')
        data = json.loads(body) if body else {}

        batch_num = data.get("batch")
        record_id = data.get("record_id")

        if not batch_num:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": "Missing batch parameter"})
            }

        # 获取飞书token
        token = get_feishu_token()

        # 获取产品列表
        products = get_products_by_batch(token, batch_num)

        if not products:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "success": False,
                    "message": "没有找到该批次的产品",
                    "batch": batch_num
                })
            }

        # 处理产品并生成标题
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

        # 写入表2
        success_count = 0
        if results:
            success_count = write_to_output_table(token, results)

        # 更新批次状态
        if record_id:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result_text = f"已处理 {success_count}/{len(products)} | {timestamp}"
            update_batch_result(token, record_id, result_text)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "success": True,
                "batch": batch_num,
                "total": len(products),
                "processed": len(results),
                "written": success_count,
                "logs": logs
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }
