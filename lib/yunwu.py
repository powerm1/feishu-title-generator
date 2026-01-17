"""
云雾 API 封装模块
调用大模型生成产品标题
"""
import urllib.request
import urllib.error
import json
import ssl
import time
from typing import Dict, Optional
from .config import YUNWU_API_BASE, YUNWU_API_KEY, MODEL_NAME, TITLE_GENERATION_PROMPT

# SSL上下文
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


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

    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as response:
            result = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"HTTP {e.code}: {error_body}")

    if "choices" in result and len(result["choices"]) > 0:
        content = result["choices"][0]["message"]["content"]
        content = content.strip().strip('"').strip("'").strip()
        return content
    else:
        raise Exception(f"API调用失败: {result}")


def generate_product_title(product: Dict) -> Optional[str]:
    """使用大模型生成产品标题"""
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
                cut_pos = 107
                while cut_pos > 0 and title[cut_pos] not in ' ,':
                    cut_pos -= 1
                title = title[:cut_pos].strip(' ,')

            return title

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise e

    return None
