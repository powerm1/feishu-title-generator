#!/usr/bin/env python3
"""
飞书多维表格产品标题生成器
使用云雾API (gpt-5.1) 大模型生成符合规则的产品标题

使用方法:
    # 单次运行
    python3 feishu_title_generator.py

    # 自动监控模式（每60秒检查一次新触发的批次）
    python3 feishu_title_generator.py --watch

    # 自定义检查间隔（秒）
    python3 feishu_title_generator.py --watch --interval 30

    # Webhook服务器模式（接收飞书自动化触发）
    python3 feishu_title_generator.py --webhook

    # 自定义Webhook端口（默认8080）
    python3 feishu_title_generator.py --webhook --port 9000

流程:
    1. 检查表3中 COZE RUN 被勾选且 COZE result 为空的批次（避免重复处理）
    2. 从表1获取该批次的产品数据
    3. 调用云雾API生成优化标题
    4. 写入表2的 Product_Name 字段
    5. 更新表3的 COZE result 标记为已处理

Webhook配置:
    飞书多维表格自动化中配置发送Webhook请求:
    - URL: http://你的服务器IP:8080/webhook
    - 方法: POST
    - 请求体(JSON): {"batch": "{{批次号字段}}", "record_id": "{{record_id}}"}
"""

import urllib.request
import urllib.error
import json
import ssl
import time
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from typing import List, Dict, Optional

# ==================== 配置区域 ====================

# 云雾API配置
YUNWU_API_BASE = "https://yunwu.ai/v1"
YUNWU_API_KEY = "sk-2hX6ze27mkjOWtpCbKeo9U056wR6qmN8DttWMRCvYyNluQ4C"
MODEL_NAME = "gpt-5.1-2025-11-13"

# 飞书配置
FEISHU_APP_ID = "cli_a73bda7327399013"
FEISHU_APP_SECRET = "IxStGQLRexU8XAKuu2uyAfmWQfHPVXlb"
FEISHU_APP_TOKEN = "Xm6ubPCUZa2M7nsjalTczVW5nCf"

# 表格ID
TABLE_INPUT = "tblDgzsh7WQoCxZS"      # COZEINPUTD27-2 (表1: 产品数据采集)
TABLE_OUTPUT = "tblECTD6VFMI2ofL"     # V1D27-2 (表2: 产品详情输出)
TABLE_PROGRESS = "tblwDLoWyb6YlRZJ"   # Progress-D27-2 (表3: 批次进度)

# SSL上下文（跳过验证，生产环境建议启用验证）
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# ==================== 标题生成提示词 ====================

TITLE_GENERATION_PROMPT = """你是一个专业的电商产品标题优化专家。请根据以下信息生成一个优化的英文产品标题。

## 输入信息：
- 原标题: {original_title}
- 五点描述: {bullets}
- Name Format: {name_format}
- 产品重量: {weight}
- 产品尺寸: {size}

## 标题生成规则（必须严格遵守）：
1. 使用 name format 的结构构建标题
2. 标题总字符数（含空格）必须在 100-110 个字符之间（这是硬性要求！）
3. 保留产品核心本质，突出独特卖点和优势
4. 不包含任何品牌名（如 Nelko, Phomemo, NIIMBOT, TransOurDream, SUPVAN, JADENS 等）
5. 保持英文，不翻译成中文
6. 如果是单品，不添加 "1pack"
7. 绝对不能使用以下词汇：battery, batteries, rechargeable

## 输出要求：
只输出优化后的标题，不要包含任何解释、引号或其他内容。
确保字符数严格在 100-110 之间。

现在请生成标题："""

# ==================== HTTP 工具函数 ====================

def http_request(url: str, method: str = "GET", headers: Dict = None, data: Dict = None, timeout: int = 60) -> Dict:
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

# ==================== 飞书 API 函数 ====================

def get_feishu_token() -> str:
    """获取飞书访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    result = http_request(url, method="POST", data=data)

    if result.get("code") == 0:
        return result["tenant_access_token"]
    raise Exception(f"获取飞书token失败: {result}")

def get_triggered_batches(token: str) -> List[Dict]:
    """获取表3中 COZE RUN 被勾选且 COZE result 为空的批次（避免重复处理）"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_PROGRESS}/records?page_size=100"
    headers = {"Authorization": f"Bearer {token}"}

    result = http_request(url, headers=headers)

    batches = []
    if result.get("code") == 0:
        for item in result.get("data", {}).get("items", []):
            fields = item.get("fields", {})
            # 检查 COZE RUN 是否被勾选
            coze_run = fields.get("COZE RUN")
            # 检查 COZE result 是否为空（未处理）
            coze_result = fields.get("COZE result")

            if coze_run == True and (coze_result is None or coze_result == "" or coze_result.strip() == ""):
                batch_num = fields.get("Batch#")
                if batch_num:
                    batches.append({
                        "batch": batch_num,
                        "record_id": item.get("record_id")
                    })
    return batches

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
    except Exception as e:
        print(f"    更新 COZE result 失败: {e}", flush=True)
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
            print(f"    警告: API返回错误 {result}", flush=True)
            break

        for item in result.get("data", {}).get("items", []):
            fields = item.get("fields", {})
            # 检查批次号
            if fields.get("Batch #") == batch_num:
                # 提取ASIN
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

        # 检查是否有更多页
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

    # 每次最多写入100条
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
            else:
                print(f"    写入失败: {result}", flush=True)
        except Exception as e:
            print(f"    写入异常: {e}", flush=True)

        time.sleep(0.5)  # 避免请求过快

    return success_count

# ==================== 云雾 API 大模型调用 ====================

def call_yunwu_api(prompt: str, system_prompt: str = None) -> str:
    """调用云雾API生成内容"""
    url = f"{YUNWU_API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {YUNWU_API_KEY}",
        "Content-Type": "application/json"
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200
    }

    result = http_request(url, method="POST", headers=headers, data=payload, timeout=60)

    if "choices" in result and len(result["choices"]) > 0:
        content = result["choices"][0]["message"]["content"]
        # 清理可能的引号和空白
        content = content.strip().strip('"').strip("'").strip()
        return content
    else:
        raise Exception(f"API调用失败: {result}")

def generate_product_title(product: Dict) -> Optional[str]:
    """使用大模型生成产品标题"""
    # 构建提示词
    prompt = TITLE_GENERATION_PROMPT.format(
        original_title=product.get("original_title", "")[:500],
        bullets=product.get("bullets", "")[:1500],
        name_format=product.get("name_format", ""),
        weight=product.get("weight", ""),
        size=product.get("size", "")
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            title = call_yunwu_api(prompt)
            title_len = len(title)

            # 验证标题长度
            if 100 <= title_len <= 110:
                return title

            # 如果长度不对，让模型重新调整
            if title_len < 100:
                adjust_prompt = f"这个标题太短了，只有{title_len}字符。请在保持原意的基础上扩展到100-110字符：\n{title}"
            else:
                adjust_prompt = f"这个标题太长了，有{title_len}字符。请精简到100-110字符，保留核心卖点：\n{title}"

            title = call_yunwu_api(adjust_prompt)
            title_len = len(title)

            if 100 <= title_len <= 110:
                return title

            # 如果还是不对，手动调整
            if title_len > 110:
                # 截断到最后一个空格
                cut_pos = 107
                while cut_pos > 0 and title[cut_pos] not in ' ,':
                    cut_pos -= 1
                title = title[:cut_pos].strip(' ,')

            return title

        except Exception as e:
            print(f"        重试 {attempt + 1}/{max_retries}: {e}", flush=True)
            time.sleep(2)

    return None

# ==================== 主流程 ====================

def process_single_batch(token: str, batch_num: str, record_id: str) -> bool:
    """处理单个批次（供webhook调用）"""
    print(f"\n[处理] 批次: {batch_num}", flush=True)
    print("-" * 50, flush=True)

    # 获取该批次的产品
    print(f"    获取产品数据...", flush=True)
    try:
        products = get_products_by_batch(token, batch_num)
        print(f"    ✓ 获取到 {len(products)} 个产品", flush=True)
    except Exception as e:
        print(f"    ✗ 获取产品失败: {e}", flush=True)
        update_batch_result(token, record_id, f"失败: {str(e)[:50]}")
        return False

    if not products:
        print("    没有找到该批次的产品", flush=True)
        update_batch_result(token, record_id, "无产品数据")
        return False

    # 为每个产品生成标题
    print(f"\n    生成产品标题...", flush=True)
    results = []
    for i, product in enumerate(products):
        asin = product.get('asin', 'Unknown')
        print(f"    [{i+1:3d}/{len(products)}] {asin}...", end=" ", flush=True)

        try:
            new_title = generate_product_title(product)
            if new_title:
                results.append({
                    "asin": asin,
                    "product_name": new_title
                })
                print(f"✓ [{len(new_title):3d}字符]", flush=True)
            else:
                print("✗ 生成失败", flush=True)
        except Exception as e:
            print(f"✗ 错误: {e}", flush=True)

        time.sleep(1)  # 避免API限流

    # 写入表2
    if results:
        print(f"\n[写入] 写入表2 Product_Name字段...", flush=True)
        try:
            success = write_to_output_table(token, results)
            print(f"    ✓ 成功写入 {success}/{len(results)} 条记录", flush=True)

            # 更新批次状态为已处理
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result_text = f"已处理 {success}/{len(products)} | {timestamp}"
            if update_batch_result(token, record_id, result_text):
                print(f"    ✓ 已标记批次为已处理", flush=True)

            return True

        except Exception as e:
            print(f"    ✗ 写入失败: {e}", flush=True)
            update_batch_result(token, record_id, f"写入失败: {str(e)[:30]}")
            return False
    else:
        print("\n    没有成功生成的标题", flush=True)
        update_batch_result(token, record_id, "生成失败")
        return False

def process_batches(token: str) -> int:
    """处理所有待处理的批次，返回处理的批次数"""
    # 检查触发的批次
    print("\n[检查] 检测新触发的批次 (COZE RUN=True 且 COZE result为空)...", flush=True)
    try:
        batches = get_triggered_batches(token)
        if not batches:
            print("    没有需要处理的新批次", flush=True)
            return 0
        print(f"    ✓ 发现 {len(batches)} 个新批次: {[b['batch'] for b in batches]}", flush=True)
    except Exception as e:
        print(f"    ✗ 检测失败: {e}", flush=True)
        return 0

    processed_count = 0

    # 处理每个批次
    for batch_info in batches:
        if process_single_batch(token, batch_info["batch"], batch_info["record_id"]):
            processed_count += 1

    return processed_count

# ==================== Webhook 服务器 ====================

# 全局变量用于webhook服务器
_webhook_token = None
_webhook_token_time = 0

def get_or_refresh_token() -> str:
    """获取或刷新飞书token（带缓存）"""
    global _webhook_token, _webhook_token_time
    current_time = time.time()

    # Token 有效期2小时，每1.5小时刷新一次
    if _webhook_token is None or (current_time - _webhook_token_time) > 5400:
        print("[Token] 获取/刷新飞书访问令牌...", flush=True)
        _webhook_token = get_feishu_token()
        _webhook_token_time = current_time
        print("[Token] ✓ Token获取成功", flush=True)

    return _webhook_token

class WebhookHandler(BaseHTTPRequestHandler):
    """处理飞书自动化发送的Webhook请求"""

    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[Webhook] {self.address_string()} - {args[0]}", flush=True)

    def do_GET(self):
        """处理GET请求（健康检查）"""
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"status": "ok", "message": "Webhook服务器运行中"}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """处理POST请求（接收webhook触发）"""
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')

            print(f"\n[Webhook] 收到请求: {body[:200]}...", flush=True)

            # 解析JSON
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}

            # 提取批次信息
            batch_num = data.get("batch") or data.get("Batch#") or data.get("batch_num")
            record_id = data.get("record_id")

            if not batch_num:
                # 如果没有提供批次号，返回成功但不处理
                # 这可能是飞书的验证请求
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {"status": "ok", "message": "已收到请求，但未提供批次号"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                print("[Webhook] 未提供批次号，跳过处理", flush=True)
                return

            # 立即返回响应（避免飞书超时）
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"status": "accepted", "batch": batch_num, "message": "任务已接收，正在后台处理"}
            self.wfile.write(json.dumps(response).encode('utf-8'))

            # 在后台线程处理批次
            def process_in_background():
                try:
                    token = get_or_refresh_token()

                    # 如果没有record_id，需要从表3查找
                    actual_record_id = record_id
                    if not actual_record_id:
                        print(f"[Webhook] 未提供record_id，从表3查找批次 {batch_num}...", flush=True)
                        batches = get_triggered_batches(token)
                        for b in batches:
                            if b["batch"] == batch_num:
                                actual_record_id = b["record_id"]
                                break

                        if not actual_record_id:
                            print(f"[Webhook] ✗ 未找到批次 {batch_num} 的记录", flush=True)
                            return

                    # 处理批次
                    success = process_single_batch(token, batch_num, actual_record_id)
                    if success:
                        print(f"[Webhook] ✓ 批次 {batch_num} 处理完成", flush=True)
                    else:
                        print(f"[Webhook] ✗ 批次 {batch_num} 处理失败", flush=True)

                except Exception as e:
                    print(f"[Webhook] ✗ 处理异常: {e}", flush=True)

            thread = threading.Thread(target=process_in_background)
            thread.daemon = True
            thread.start()

        except Exception as e:
            print(f"[Webhook] ✗ 请求处理错误: {e}", flush=True)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))

def run_webhook(port: int = 8080):
    """启动Webhook服务器"""
    print("=" * 70, flush=True)
    print("  飞书多维表格产品标题生成器", flush=True)
    print("  使用云雾API (gpt-5.1-2025-11-13)", flush=True)
    print(f"  模式: Webhook服务器 (端口 {port})", flush=True)
    print("  提示: 按 Ctrl+C 停止", flush=True)
    print("=" * 70, flush=True)

    # 预先获取token
    print("\n[初始化] 获取飞书访问令牌...", flush=True)
    try:
        get_or_refresh_token()
    except Exception as e:
        print(f"    ✗ 失败: {e}", flush=True)
        print("    服务器仍将启动，token将在首次请求时获取", flush=True)

    # 启动服务器
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    print(f"\n[服务器] Webhook服务器已启动", flush=True)
    print(f"    地址: http://0.0.0.0:{port}", flush=True)
    print(f"    健康检查: GET http://localhost:{port}/health", flush=True)
    print(f"    Webhook端点: POST http://localhost:{port}/webhook", flush=True)
    print(f"\n[配置] 飞书多维表格自动化配置:", flush=True)
    print(f"    URL: http://你的服务器IP:{port}/webhook", flush=True)
    print(f"    方法: POST", flush=True)
    print(f'    请求体: {{"batch": "{{{{批次号字段}}}}", "record_id": "{{{{record_id}}}}"}}', flush=True)
    print("\n[等待] 等待Webhook请求...\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n[停止] 用户中断，关闭服务器", flush=True)
        server.shutdown()

def run_once():
    """单次运行模式"""
    print("=" * 70, flush=True)
    print("  飞书多维表格产品标题生成器", flush=True)
    print("  使用云雾API (gpt-5.1-2025-11-13)", flush=True)
    print("  模式: 单次运行", flush=True)
    print("=" * 70, flush=True)

    # 获取飞书token
    print("\n[初始化] 获取飞书访问令牌...", flush=True)
    try:
        token = get_feishu_token()
        print(f"    ✓ Token获取成功", flush=True)
    except Exception as e:
        print(f"    ✗ 失败: {e}", flush=True)
        return

    # 处理批次
    processed = process_batches(token)

    print("\n" + "=" * 70, flush=True)
    print(f"  处理完成! 共处理 {processed} 个批次", flush=True)
    print("=" * 70, flush=True)

def run_watch(interval: int = 60):
    """监控模式：定时检查新触发的批次"""
    print("=" * 70, flush=True)
    print("  飞书多维表格产品标题生成器", flush=True)
    print("  使用云雾API (gpt-5.1-2025-11-13)", flush=True)
    print(f"  模式: 自动监控 (每 {interval} 秒检查一次)", flush=True)
    print("  提示: 按 Ctrl+C 停止", flush=True)
    print("=" * 70, flush=True)

    token = None
    token_time = 0

    while True:
        try:
            current_time = time.time()

            # Token 有效期2小时，每1.5小时刷新一次
            if token is None or (current_time - token_time) > 5400:
                print("\n[初始化] 获取/刷新飞书访问令牌...", flush=True)
                try:
                    token = get_feishu_token()
                    token_time = current_time
                    print(f"    ✓ Token获取成功", flush=True)
                except Exception as e:
                    print(f"    ✗ 失败: {e}", flush=True)
                    time.sleep(interval)
                    continue

            # 处理批次
            processed = process_batches(token)

            if processed > 0:
                print(f"\n[完成] 本轮处理了 {processed} 个批次", flush=True)

            # 等待下一次检查
            print(f"\n[等待] {interval}秒后再次检查...", flush=True)
            time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n[停止] 用户中断，退出监控模式", flush=True)
            break
        except Exception as e:
            print(f"\n[错误] {e}", flush=True)
            print(f"[等待] {interval}秒后重试...", flush=True)
            time.sleep(interval)

def main():
    """主入口"""
    args = sys.argv[1:]

    if "--webhook" in args:
        # Webhook服务器模式
        port = 8080  # 默认端口
        if "--port" in args:
            idx = args.index("--port")
            if idx + 1 < len(args):
                try:
                    port = int(args[idx + 1])
                except ValueError:
                    pass
        run_webhook(port)
    elif "--watch" in args or "-w" in args:
        # 监控模式
        interval = 60  # 默认60秒
        if "--interval" in args:
            idx = args.index("--interval")
            if idx + 1 < len(args):
                try:
                    interval = int(args[idx + 1])
                except ValueError:
                    pass
        run_watch(interval)
    else:
        # 单次运行模式
        run_once()

if __name__ == "__main__":
    main()
