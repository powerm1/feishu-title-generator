"""
Webhook 接收端点
接收飞书自动化触发的请求
"""
import json
import sys
import os

# 添加 lib 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.feishu import get_feishu_token, update_batch_result


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

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        # 提取批次信息
        batch_num = data.get("batch") or data.get("Batch#") or data.get("batch_num")
        record_id = data.get("record_id")

        if not batch_num:
            # 可能是飞书的验证请求，返回成功
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "status": "ok",
                    "message": "Webhook已收到，但未提供批次号"
                })
            }

        # 标记批次为处理中（如果有record_id）
        if record_id:
            try:
                token = get_feishu_token()
                update_batch_result(token, record_id, "处理中...")
            except Exception:
                pass

        # 返回成功响应
        # 注意：Vercel Serverless 不支持后台任务
        # 实际处理需要用户在前端手动触发或使用外部队列
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "status": "accepted",
                "batch": batch_num,
                "record_id": record_id,
                "message": "任务已接收，请在控制台查看并处理"
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
                "status": "error",
                "error": str(e)
            })
        }
