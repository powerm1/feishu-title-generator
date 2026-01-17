# 飞书产品标题生成器

使用云雾API (GPT-5.1) 为飞书多维表格中的产品生成优化标题。

## 功能
 
- 查看批次列表和状态
- 手动触发批次处理
- 实时处理日志  
- Webhook 接收飞书自动化触发
- 自动刷新状态

## 部署到 Vercel

### 1. Fork 或 Clone 此仓库

```bash
git clone https://github.com/YOUR_USERNAME/feishu-title-generator.git
```

### 2. 在 Vercel 导入项目

1. 登录 [Vercel](https://vercel.com)
2. 点击 "Import Project"
3. 选择 GitHub 仓库

### 3. 配置环境变量

在 Vercel 项目设置中添加以下环境变量：

| 变量名 | 说明 |
|--------|------|
| `YUNWU_API_KEY` | 云雾API密钥 |
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_APP_TOKEN` | 飞书多维表格 Token |

### 4. 部署

点击 Deploy，等待部署完成。

## 飞书自动化配置

在飞书多维表格中设置自动化：

1. **触发条件**: 当 COZE RUN 字段被勾选时
2. **动作**: 发送 Webhook 请求
   - URL: `https://your-app.vercel.app/api/webhook`
   - 方法: POST
   - 请求体: `{"batch": "{{Batch#}}", "record_id": "{{record_id}}"}`

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/batches` | GET | 获取批次列表 |
| `/api/process` | POST | 处理指定批次 |
| `/api/webhook` | POST | 接收 Webhook 触发 |

## 本地开发

```bash
# 安装 Vercel CLI
npm i -g vercel

# 本地运行
vercel dev
```

## 注意事项

- Vercel Hobby 计划函数执行限制 10 秒，Pro 计划可达 60 秒
- 大批次处理可能需要升级到 Pro 计划
- 敏感信息请使用环境变量，不要提交到代码库
