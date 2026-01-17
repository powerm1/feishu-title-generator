"""
健康检查端点
"""
import json


def handler(request):
    """Vercel Serverless Function handler"""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "status": "ok",
            "message": "飞书产品标题生成器运行中",
            "version": "1.0.0"
        })
    }
