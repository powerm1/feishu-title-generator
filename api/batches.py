"""
获取批次列表端点
"""
import json
import sys
import os

# 添加 lib 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.feishu import get_feishu_token, get_all_batches


def handler(request):
    """Vercel Serverless Function handler"""
    # 处理 CORS
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }

    try:
        token = get_feishu_token()
        batches = get_all_batches(token)

        # 分类批次
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

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "success": True,
                "pending": pending,
                "completed": completed,
                "total": len(batches)
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
