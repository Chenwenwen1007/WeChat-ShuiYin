# 微信小程序短视频去水印解析工具

> 一个基于 **微信小程序 + FastAPI** 的短视频去水印解析工具，支持抖音无水印视频提取、快手和小红书视频解析。适合个人学习、给家人使用（比如帮长辈下载无水印视频）。

## 项目亮点

- 支持 **抖音官方API无水印解析**（非简单的 playwm→play 替换，是真无水印）
- 支持 **快手、小红书** 视频解析
- 支持 **第三方API兜底**（bugpk.com免费API），自有解析失败时自动切换
- 微信小程序一键粘贴、解析、预览、下载保存到相册
- Python FastAPI 后端，轻量高效，可本地运行或部署到云服务器
- 完整签名算法实现（SM3 + RC4 + Base64），从开源项目翻译为 Python

## 技术栈

- 微信小程序前端
- FastAPI Python 后端
- 阿里云 ECS + Nginx + systemd（可选部署）

## 关键词

`微信小程序` `抖音去水印` `视频解析` `短视频下载` `无水印视频` `FastAPI` `Python` `快手解析` `小红书解析` `douyin` `watermark-removal`

## 目录结构

```text
qushuiyin/
├─ api/                      # 小程序请求封装
├─ app.js
├─ app.json
├─ app.less
├─ config.js                 # 小程序后端地址
├─ pages/
│  └─ home/
│     ├─ index.js
│     ├─ index.json
│     ├─ index.less
│     └─ index.wxml
├─ server/
│  ├─ app.py                 # FastAPI 应用入口
│  ├─ main.py                # 本地启动入口
│  ├─ config.py              # 环境变量配置
│  ├─ api/                   # 路由层
│  ├─ parsers/               # 平台解析器
│  │  ├─ douyin.py           # 抖音基础解析器（分享页HTML提取）
│  │  ├─ douyin_api.py       # 抖音官方API解析器（无水印核心）
│  │  ├─ douyin_v2.py        # 抖音v2解析器（备用方案）
│  │  ├─ douyin_sign.py      # 抖音签名算法（SM3+RC4+Base64）
│  │  ├─ kuaishou.py         # 快手解析器
│  │  └─ xiaohongshu.py      # 小红书解析器
│  ├─ schemas/               # 请求与响应模型
│  ├─ services/              # 业务逻辑
│  │  ├─ parser_service.py   # 解析调度服务
│  │  ├─ third_party_service.py # 第三方API兜底服务
│  │  ├─ downloader_service.py  # 下载代理服务
│  │  └─ url_service.py      # URL提取与解析服务
│  └─ utils/                 # 工具函数
│     ├─ http_client.py      # HTTP客户端（含防盗链Referer）
│     └─ text_extractor.py   # 文本提取工具
├─ deploy/
│  ├─ nginx.conf
│  ├─ qushuiyin.service
│  └─ run_nohup.sh
├─ docs/
│  └─ TROUBLESHOOTING.md
├─ .env.example
└─ requirements.txt
```

## 一、本地运行后端

### 1. 安装 Python

建议使用 Python `3.11` 或 `3.12`。

Windows：

```bash
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
```

### 2. 启动 FastAPI

```bash
python -m server.main
```

启动成功后访问：

- `http://127.0.0.1:8001/health`
- `http://127.0.0.1:8001/docs`

## 二、本地运行小程序

### 1. 导入项目

在微信开发者工具中导入当前目录：

```text
F:\Pyhton_Project\WeChatProject\qushuiyin
```

### 2. 检查接口地址

[config.js](/F:/Pyhton_Project/WeChatProject/qushuiyin/config.js) 默认配置为：

```js
export default {
  baseUrl: 'http://127.0.0.1:8001',
};
```

### 3. 本地调试设置

在微信开发者工具里，仅本地测试时开启：

- 不校验合法域名
- 不校验 TLS 版本
- 不校验 HTTPS 证书

这样小程序就可以直接请求本地 FastAPI 服务。

## 三、接口说明

### 1. 解析接口

`POST /api/parse`

请求体：

```json
{
  "text": "这里放分享文案或链接"
}
```

返回示例：

```json
{
  "success": true,
  "data": {
    "platform": "douyin",
    "platform_label": "抖音",
    "title": "视频标题",
    "author": "作者昵称",
    "cover_url": "https://...",
    "video_url": "https://...",
    "download_url": "http://127.0.0.1:8000/api/download?token=xxx",
    "preview_video_url": "http://127.0.0.1:8001/api/media?token=xxx",
    "raw_url": "https://v.douyin.com/xxxx/",
    "resolved_url": "https://www.douyin.com/video/xxxx"
  }
}
```

### 2. 下载接口

`GET /api/download?token=xxx`

说明：

- 后端会代理拉取视频并流式返回
- 小程序只请求你自己的后端域名即可

## 四、后端实现说明

### 1. 解析流程

1. 从分享文案中提取第一条链接
2. 跟随重定向拿到真实页面地址
3. 根据域名识别平台
4. 请求平台分享页 HTML
5. 从页面 `meta` 或内嵌 JSON 中提取标题、作者、封面、视频地址
6. 构造下载代理地址返回给小程序

### 2. 当前支持平台

- [server/parsers/douyin.py](/F:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/douyin.py)
- [server/parsers/kuaishou.py](/F:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/kuaishou.py)
- [server/parsers/xiaohongshu.py](/F:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/xiaohongshu.py)

说明：

- 解析依赖平台当前公开页面结构
- 平台改版后，优先更新对应 parser 文件中的提取规则

## 五、部署到阿里云 ECS

以下以 Ubuntu 22.04 为例。

### 1. 安装环境

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx git
```

创建部署目录：

```bash
sudo mkdir -p /opt/qushuiyin
sudo chown -R $USER:$USER /opt/qushuiyin
cd /opt/qushuiyin
```

上传代码后执行：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```env
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
APP_BASE_URL=https://your-domain.com
CORS_ORIGINS=https://servicewechat.com,https://your-domain.com
```

### 2. 先本机测试启动

```bash
source /opt/qushuiyin/venv/bin/activate
cd /opt/qushuiyin
python -m server.main
```

另开终端测试：

```bash
curl http://127.0.0.1:8000/health
```

### 3. ECS 安全组放行

在阿里云控制台放行：

- `22`：SSH
- `80`：HTTP
- `443`：HTTPS

如果只让 Nginx 对外，`8000` 不需要开放公网。

### 4. 使用 nohup 常驻

```bash
mkdir -p /opt/qushuiyin/logs
chmod +x /opt/qushuiyin/deploy/run_nohup.sh
cd /opt/qushuiyin
./deploy/run_nohup.sh
```

查看进程：

```bash
ps -ef | grep server.main
```

查看日志：

```bash
tail -f /opt/qushuiyin/logs/server.out
```

### 5. 使用 systemd 常驻

```bash
sudo cp deploy/qushuiyin.service /etc/systemd/system/qushuiyin.service
sudo systemctl daemon-reload
sudo systemctl enable qushuiyin
sudo systemctl start qushuiyin
sudo systemctl status qushuiyin
```

查看日志：

```bash
sudo journalctl -u qushuiyin -f
```

### 6. 配置 Nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/qushuiyin
sudo ln -s /etc/nginx/sites-available/qushuiyin /etc/nginx/sites-enabled/qushuiyin
sudo nginx -t
sudo systemctl reload nginx
```

记得把配置里的 `your-domain.com` 改成你自己的域名。

### 7. 配置 HTTPS 证书

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run
```

## 六、小程序上线前配置

微信小程序后台需要配置：

- `request` 合法域名：`https://your-domain.com`
- `downloadFile` 合法域名：`https://your-domain.com`

说明：

- 本地开发可关闭校验
- 正式发布必须是 HTTPS 域名
- 域名通常需要备案

## 七、维护建议

### 1. 平台规则更新后怎么改

优先修改：

- [server/parsers/douyin.py](/F:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/douyin.py)
- [server/parsers/kuaishou.py](/F:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/kuaishou.py)
- [server/parsers/xiaohongshu.py](/F:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/xiaohongshu.py)

建议每个平台保留几条你自己的测试样本链接。

### 2. 如何快速定位问题

先检查：

- `/health` 是否正常
- 解析前的 `raw_url`
- 展开后的 `resolved_url`
- `video_url` 是否能在浏览器中直接访问

更详细排查见 [docs/TROUBLESHOOTING.md](/F:/Pyhton_Project/WeChatProject/qushuiyin/docs/TROUBLESHOOTING.md)

## 八、合规提醒

- 仅处理你本人拥有权利或明确获得授权的素材
- 不建议公开运营、收费、裂变传播
- 平台规则和页面结构会变化，解析功能需要持续维护

---

## 九、抖音去水印开发实录

> 本章节记录从"分享页HTML提取"到"调用官方API获取真无水印地址"的完整踩坑过程，供后续维护参考。

### 1. 技术原理概述

抖音视频有两种地址：

| 类型 | 来源字段 | URL特征 | 水印情况 |
|------|---------|---------|---------|
| **有水印** | `video.download_addr` | 路径含 `/mps/logo/` 或 `watermark=1` | 带抖音平台水印 |
| **无水印** | `video.bit_rate[].play_addr` | 路径含 `/tos/cn/tos-cn-ve-15/` | 纯净视频 |

**核心思路**：调用抖音官方 `/aweme/v1/web/aweme/detail/` 接口，传入合法的 `a_bogus` 签名参数，获取视频完整元数据，从中提取 `play_addr` 作为无水印地址。

### 2. 签名算法翻译（JavaScript → Python）

抖音官方接口需要 `msToken`、`ttwid` Cookie 和 `a_bogus` 签名三个关键参数。其中 `a_bogus` 的生成算法是最大难点。

参考开源项目 [jiuhunwl/short_videos](https://github.com/jiuhunwl/short_videos/) 的 Cloudflare Workers 版本，其核心算法涉及：

- **SM3 哈希**：对时间戳、用户代理等参数做摘要
- **RC4 加密**：使用密钥 `chr(121)` 对中间结果加密
- **自定义 Base64**：抖音使用变种的 Base64 编码（字母表顺序有调整）

**关键踩坑点**：

```python
# 错误：RC4 输入用 bytes
bb_bytes = bytes(bb)  # ❌ 导致签名无效

# 正确：模拟 JavaScript 的 String.fromCharCode，取模 65536
bb_str = "".join(chr(c & 0xFFFF) for c in bb)  # ✅
return rc4_encrypt(bb_str, chr(121))
```

完整实现见 [server/utils/douyin_sign.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/utils/douyin_sign.py)。

### 3. 官方API调用完整流程

```
用户粘贴链接
    ↓
提取 aweme_id（从短链重定向后的长链接中正则提取）
    ↓
生成 msToken（随机字符串 + 时间戳）
    ↓
获取 ttwid Cookie（访问抖音首页获取，失败则用默认值）
    ↓
生成 a_bogus 签名（基于 URL 参数、Cookie、User-Agent）
    ↓
调用 /aweme/v1/web/aweme/detail/?aweme_id=xxx&msToken=xxx&a_bogus=xxx
    ↓
从返回 JSON 中提取 video.play_addr.url_list[0]（无水印）
    ↓
从 video.download_addr.url_list[0]（有水印，用于对比/兜底）
    ↓
构造下载代理链接返回给前端
```

### 4. 有水印 vs 无水印地址的区分

**常见误区**：以为把 URL 中的 `playwm` 替换成 `play` 就能去水印。实际上抖音早已升级，分享页提取的地址即使替换后仍然带水印。

**正确区分方法**（通过官方API返回的数据）：

```python
# 有水印地址：download_addr，路径特征含 /mps/logo/
watermark_url = detail["video"]["download_addr"]["url_list"][0]

# 无水印地址：bit_rate 或 play_addr，路径特征含 /tos/cn/tos-cn-ve-15/
no_watermark_url = detail["video"]["bit_rate"][0]["play_addr"]["url_list"][0]
```

**下载时的表现**：
- 有水印视频：播放时右下角有抖音Logo，左上角或右下角会跳动
- 无水印视频：纯净画面，无任何平台标识

### 5. 前端数据解析坑点

微信小程序 `wx.request` 返回的数据结构容易嵌套多层，前端解析时必须兼容多种情况：

```javascript
// 容易出错的写法：直接假设 response.data.data 存在
const result = response.data.data;  // ❌ 可能报错

// 正确的兼容写法
let result;
try {
  if (response && response.data && response.data.data) {
    result = response.data.data;      // 标准结构
  } else if (response && response.data) {
    result = response.data;           // 少一层
  } else {
    result = response;                // 直接就是数据
  }
} catch (e) {
  result = response;
}
```

### 6. 防盗链处理（CDN 403 问题）

抖音、快手等平台的视频CDN会校验 `Referer` 头。如果直接用浏览器或小程序下载，会返回 403。

**解决方案**：后端代理下载时带上对应平台的 Referer。

```python
# server/utils/http_client.py
headers = {}
if "douyin" in url.lower():
    headers["Referer"] = "https://www.douyin.com/"
elif "kuaishou" in url.lower():
    headers["Referer"] = "https://www.kuaishou.com/"
```

前端不直接请求视频源地址，而是请求后端的 `/api/download` 或 `/api/media` 代理接口。

### 7. 第三方API兜底（bugpk.com）

当自有解析失效时，可调用第三方免费API作为备选方案。

**配置**（`.env`）：
```env
BUGPK_API_ENABLED=true
```

**请求方式**：
```bash
curl 'https://api.bugpk.com/api/douyin?url=https%3A%2F%2Fv.douyin.com%2Fxxxxx%2F' \
  -H 'Referer: https://api.bugpk.com/doc-douyin.html' \
  -H 'X-Requested-With: XMLHttpRequest'
```

**注意事项**：
- 该API不需要 API Key
- 返回字段名与自有解析不同，需要做字段映射
- 作为 `fallback` 使用，优先走自有解析

### 8. 超时优化经验

解析抖音视频涉及多个网络请求，容易超时。

**优化前的问题**：
- 前端超时 20 秒 → 经常 `request: fail`
- 后端解析完成后还额外发送 `verify_no_watermark` HEAD 请求 → 增加 5-10 秒

**优化措施**：
1. 前端超时改为 60 秒：`api/request.js` 中 `timeout: 60000`
2. 去掉冗余的 `verify_no_watermark` 验证：官方API返回的 `play_addr` 本身就是无水印地址，直接信任即可

### 9. 完整错误排查清单

| 现象 | 可能原因 | 解决方案 |
|------|---------|---------|
| `request: fail` | 后端没启动 | `python -m server.main` |
| `request: fail` | 微信校验域名 | 开发者工具勾选"不校验合法域名" |
| `Error: timeout` | 解析耗时超过前端超时 | 增加 `timeout` 到 60000ms |
| `Error: timeout` | 后端 `verify_no_watermark` 额外请求 | 去掉该验证逻辑 |
| 解析成功但视频有水印 | 使用了 `download_addr` | 改用 `bit_rate[].play_addr` |
| 视频无法下载/播放 | CDN 防盗链 | 后端代理加 Referer |
| 复制链接无效 | 前端解析了错误字段 | 检查 `no_watermark_video_url` 字段 |
| 端口冲突 | 上次进程未退出 | `taskkill /F /IM python.exe` |

### 10. 关键文件速查

| 文件 | 作用 | 修改场景 |
|------|------|---------|
| [server/parsers/douyin_api.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/parsers/douyin_api.py) | 抖音官方API解析核心 | 官方接口改版、字段结构调整 |
| [server/utils/douyin_sign.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/utils/douyin_sign.py) | 签名算法 | 签名失效、API返回签名错误 |
| [server/services/parser_service.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/services/parser_service.py) | 解析调度与兜底逻辑 | 切换解析策略、调整超时 |
| [server/services/third_party_service.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/services/third_party_service.py) | 第三方API集成 | bugpk.com接口变更 |
| [server/utils/http_client.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/utils/http_client.py) | HTTP客户端 | CDN Referer变更、代理配置 |
| [api/request.js](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/api/request.js) | 前端请求封装 | 调整超时、修改header |
| [pages/home/index.js](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/pages/home/index.js) | 前端页面逻辑 | 数据解析、UI交互 |
| [config.js](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/config.js) | 后端地址配置 | 切换环境、修改端口 |
