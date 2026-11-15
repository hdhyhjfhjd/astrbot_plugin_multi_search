# astrbot_plugin_multi_search

为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 接入**多源联网搜索**的插件。

在插件配置面板填写搜索源（名称、地址、Key），填了名称的源会自动出现在
AstrBot 原生「网页搜索提供商」下拉框里，选哪个就用哪个。

---

## 1. 配置方式

打开 `插件 → 多源搜索 → 配置`，点「添加更多」加搜索源。每个源填 4 项：

| 字段 | 说明 |
|---|---|
| **源名称** | 填什么就出现在下拉框里，比如 `searxng` / `tavily` / `bocha` |
| **地址** | API 端点地址。插件根据地址自动识别格式，不需要选协议。留空则按源名匹配默认地址。 |
| **API Key** | 第三方 API 的密钥（自部署 SearXNG 不需要） |
| **额外参数(JSON)** | 附加请求参数，JSON 格式，不需要则留 `{}` |

**地址怎么填：**

| 搜索源 | 地址 |
|---|---|
| 自部署 SearXNG | `http://127.0.0.1:8088` |
| Tavily | `https://api.tavily.com/search`（或留空自动匹配） |
| 博查 Bocha | `https://api.bochaai.com/v1/web-search`（或留空自动匹配） |
| Brave | `https://api.search.brave.com/res/v1/web/search`（或留空自动匹配） |
| 智谱 | `https://open.bigmodel.cn/api/paas/v4/web_search`（或留空自动匹配） |

**各源额外参数（extra）怎么填：**

| 搜索源 | extra 填什么 |
|---|---|
| SearXNG | `{}` |
| Tavily | `{}` |
| 博查 Bocha | `{}` |
| Brave | `{}` |
| 智谱 | `{"search_engine": "search_pro"}`，可选 `search_std` / `search_pro_sogou` / `search_pro_quark` |

配置保存后，去 `配置文件 → AI → 能力 → 网页搜索`，下拉框里就能看到你填的源名。

---

## 2. 各搜索源说明

### SearXNG（自部署，推荐）

开源元搜索引擎，自己跑在服务器上，免费、无限制、无广告。

Docker Compose 部署（和 AstrBot 同机）：

```yaml
services:
  searxng:
    image: searxng/searxng:latest
    ports:
      - "127.0.0.1:8088:8080"
    volumes:
      - ./searxng:/etc/searxng
    restart: unless-stopped
  valkey:
    image: valkey/valkey:alpine
    command: --maxmemory 128mb --maxmemory-policy allkeys-lru
    restart: unless-stopped
```

> 注意：SearXNG 的 `settings.yml` 里必须开启 `search.formats: [html, json]`，否则 API 调用 403。
> 端口绑 `127.0.0.1`，不要暴露公网。

### Tavily

- 注册：https://tavily.com
- 免费 1000 次/月，专为 AI 搜索优化
- 地址留空用默认，填 Key 即可

### 博查（Bocha）

- 注册：https://bochaai.com
- 国内搜索 API，中文结果好
- 地址留空用默认，填 Key 即可

### Brave Search

- 注册：https://brave.com/search/api/
- 免费 2000 次/月，隐私导向独立索引
- 地址留空用默认，填 Key 即可

### 智谱（Zhipu）

- 注册：https://open.bigmodel.cn/usercenter/apikeys
- 按次计费
- extra 填 `{"search_engine": "search_pro"}`（可选 search_std / search_pro_sogou / search_pro_quark）

---

## 3. 安装

1. 打包 zip（顶层文件夹为 `astrbot_plugin_multi_search/`）。
2. AstrBot WebUI →「插件」→「安装本地插件」上传。
3. 重载插件，日志显示 `多源搜索已加载 N 个源：...`。

---

## 4. 使用

在 `配置文件 → AI → 能力 → 网页搜索` 中：
1. 打开「启用网页搜索」
2. 下拉框选你要的源
3. 保存

模型需要实时信息时自动调用 `web_search` 工具。切换源只需回下拉框选另一个。

---

## 5. License

MIT

---

## 致谢

本插件由 [Doubao Seed 2.1 Lite](https://www.doubao.com)（豆包 AI 助手）设计与开发。
