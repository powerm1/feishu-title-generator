"""
飞书 API 封装模块
提供飞书多维表格的读写功能
"""
import urllib.request
import urllib.error
import json
import ssl
import time
from typing import List, Dict, Optional
from .config import (
    FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN,
    TABLE_INPUT, TABLE_OUTPUT, TABLE_PROGRESS
)

# SSL上下文（跳过验证，生产环境建议启用验证）
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Token 缓存
_token_cache = {"token": None, "expires_at": 0}


def http_request(url: str, method: str = "GET", headers: Dict = None, data: Dict = None, timeout: int = 30) -> Dict:
    """发送HTTP请求"""
    if headers is None:
        headers = {}

    body = None
    if data:
        body = json.dumps(data).encode('utf-8')
        if 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"HTTP {e.code}: {error_body}")


def get_feishu_token() -> str:
    """获取飞书访问令牌（带缓存）"""
    global _token_cache
    current_time = time.time()

    # Token 有效期2小时，提前5分钟刷新
    if _token_cache["token"] and current_time < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    result = http_request(url, method="POST", data=data)

    if result.get("code") == 0:
        _token_cache["token"] = result["tenant_access_token"]
        _token_cache["expires_at"] = current_time + result.get("expire", 7200)
        return _token_cache["token"]
    raise Exception(f"获取飞书token失败: {result}")


def get_all_batches(token: str) -> List[Dict]:
    """获取表3中所有批次及其状态"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_PROGRESS}/records?page_size=100"
    headers = {"Authorization": f"Bearer {token}"}

    result = http_request(url, headers=headers)

    batches = []
    if result.get("code") == 0:
        for item in result.get("data", {}).get("items", []):
            fields = item.get("fields", {})
            batch_num = fields.get("Batch#")
            if batch_num:
                batches.append({
                    "batch": batch_num,
                    "record_id": item.get("record_id"),
                    "coze_run": fields.get("COZE RUN", False),
                    "coze_result": fields.get("COZE result", ""),
                })
    return batches


def get_triggered_batches(token: str) -> List[Dict]:
    """获取表3中 COZE RUN 被勾选且 COZE result 为空的批次"""
    all_batches = get_all_batches(token)
    return [
        b for b in all_batches
        if b["coze_run"] == True and (not b["coze_result"] or b["coze_result"].strip() == "")
    ]


def update_batch_result(token: str, record_id: str, result_text: str) -> bool:
    """更新表3中批次的 COZE result 字段"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_PROGRESS}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "fields": {
            "COZE result": result_text
        }
    }

    try:
        result = http_request(url, method="PUT", headers=headers, data=data)
        return result.get("code") == 0
    except Exception:
        return False


def get_products_by_batch(token: str, batch_num: str) -> List[Dict]:
    """获取指定批次的所有产品"""
    base_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_INPUT}/records"
    headers = {"Authorization": f"Bearer {token}"}

    all_products = []
    page_token = None

    while True:
        url = f"{base_url}?page_size=100"
        if page_token:
            url += f"&page_token={page_token}"

        result = http_request(url, headers=headers)

        if result.get("code") != 0:
            break

        for item in result.get("data", {}).get("items", []):
            fields = item.get("fields", {})
            if fields.get("Batch #") == batch_num:
                asin_field = fields.get("ASIN", {})
                asin = asin_field.get("text", "") if isinstance(asin_field, dict) else str(asin_field)

                product = {
                    "record_id": item.get("record_id"),
                    "asin": asin,
                    "original_title": fields.get("商品标题", ""),
                    "bullets": fields.get("产品卖点", ""),
                    "name_format": fields.get("name format", ""),
                    "weight": fields.get("重量_1", ""),
                    "size": fields.get("体积_1", ""),
                }
                all_products.append(product)

        if not result.get("data", {}).get("has_more"):
            break
        page_token = result.get("data", {}).get("page_token")

    return all_products


def write_to_output_table(token: str, records: List[Dict]) -> int:
    """批量写入产品标题到表2"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_OUTPUT}/records/batch_create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    success_count = 0

    for i in range(0, len(records), 100):
        batch = records[i:i+100]
        batch_data = {
            "records": [
                {
                    "fields": {
                        "ASIN": r["asin"],
                        "Product_Name": r["product_name"]
                    }
                }
                for r in batch
            ]
        }

        try:
            result = http_request(url, method="POST", headers=headers, data=batch_data)
            if result.get("code") == 0:
                success_count += len(batch)
        except Exception:
            pass

        time.sleep(0.3)

    return success_count
