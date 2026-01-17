"""
配置管理模块
从环境变量读取配置，支持本地开发和 Vercel 部署
"""
import os

# 云雾API配置
YUNWU_API_BASE = "https://yunwu.ai/v1"
YUNWU_API_KEY = os.environ.get("YUNWU_API_KEY", "sk-2hX6ze27mkjOWtpCbKeo9U056wR6qmN8DttWMRCvYyNluQ4C")
MODEL_NAME = "gpt-5.1-2025-11-13"

# 飞书配置
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a73bda7327399013")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "IxStGQLRexU8XAKuu2uyAfmWQfHPVXlb")
FEISHU_APP_TOKEN = os.environ.get("FEISHU_APP_TOKEN", "Xm6ubPCUZa2M7nsjalTczVW5nCf")

# 表格ID
TABLE_INPUT = "tblDgzsh7WQoCxZS"      # COZEINPUTD27-2 (表1: 产品数据采集)
TABLE_OUTPUT = "tblECTD6VFMI2ofL"     # V1D27-2 (表2: 产品详情输出)
TABLE_PROGRESS = "tblwDLoWyb6YlRZJ"   # Progress-D27-2 (表3: 批次进度)

# 标题生成提示词
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
