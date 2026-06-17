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

---

## 十、快手与小红书去水印优化实录

> 本章节记录快手、小红书两个平台从"仅能解析"到"支持无水印"的优化过程。

### 1. 优化前的状态

快手和小红书的解析器只做了基础的 HTML 页面提取，存在以下问题：

- **快手**：只提取了一个视频地址，没有区分有水印和无水印
- **小红书**：同样没有区分水印版本，且页面提取规则不够全面
- **第三方兜底**：bugpk.com API 只对接了抖音端点，快手和小红书无法使用兜底
- **调度逻辑**：非抖音平台一律标记 `no_watermark_verified = False`，前端无法确认是否无水印

### 2. 快手优化方案

#### 2.1 页面请求优化

快手分享页对 User-Agent 敏感，使用移动端 UA 只能拿到精简页面，缺少视频地址字段。

**优化**：改用 PC 端 Chrome UA + Referer，获取包含完整 JSON 数据的页面。

```python
html = await self.fetch_html(resolved_url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    "Referer": "https://www.kuaishou.com/",
})
```

#### 2.2 有水印 vs 无水印地址区分

快手页面 JSON 中包含两种视频地址：

| 字段 | 说明 | 水印情况 |
|------|------|---------|
| `srcNoMark` | 无水印播放地址 | 无水印 |
| `photoUrl` | 有水印播放地址 | 带快手Logo |
| `mainMvUrls` | 主视频地址列表 | 通常有水印 |

**优化**：分别提取 `srcNoMark`（无水印）和 `photoUrl`（有水印），填充到 `ParsedVideo` 的对应字段。

#### 2.3 多级兜底策略

```text
srcNoMark（无水印）→ photoUrl → mainMvUrls → hevc.url → og:video meta
```

如果 `srcNoMark` 不存在，依次尝试其他字段，确保至少能拿到一个可播放地址。

### 3. 小红书优化方案

#### 3.1 页面请求优化

与快手类似，小红书也需要 PC 端 UA 才能获取完整页面数据。

#### 3.2 无水印地址提取

小红书的视频地址结构：

| 字段 | 说明 | 水印情况 |
|------|------|---------|
| `masterUrl` | 原始视频地址 | 无水印（小红书视频通常无平台水印） |
| `backupUrls` | 备用地址列表 | 无水印 |
| `originVideoKey` | 原始视频Key | 需拼接域名 |
| `og:video` | meta标签 | 可能有水印 |

**优化**：优先提取 `masterUrl` 作为无水印地址，`og:video` 作为有水印兜底。

#### 3.3 多级兜底策略

```text
masterUrl → h264[].masterUrl → originVideoKey → backupUrls → videoUrl → og:video
```

### 4. 第三方API扩展

#### 4.1 bugpk.com 多平台端点

bugpk.com 为每个平台提供独立的 API 端点：

```python
BUGPK_API_ENDPOINTS = {
    "douyin": "https://api.bugpk.com/api/douyin",
    "kuaishou": "https://api.bugpk.com/api/kuaishou",
    "xiaohongshu": "https://api.bugpk.com/api/xiaohongshu",
}
```

#### 4.2 自动平台检测

根据分享链接的域名自动识别平台，选择对应的 API 端点：

```python
def _detect_platform(self, source_url: str) -> str:
    domain = urlparse(source_url).hostname
    if "kuaishou" in domain:
        return "kuaishou"
    if "xiaohongshu" in domain:
        return "xiaohongshu"
    return "douyin"
```

#### 4.3 统一响应适配

三个平台的 API 返回格式统一为 `{code, msg, data: {title, cover, url, ...}}`，使用同一个适配方法处理，但保留平台标识。

### 5. 解析调度优化

#### 5.1 优化前的调度逻辑

```python
# 优化前：非抖音平台一律不验证
elif platform != "douyin" and parsed_video:
    no_watermark_verified = False
```

#### 5.2 优化后的调度逻辑

```python
# 优化后：快手/小红书有无水印地址则标记验证通过
elif platform in ("kuaishou", "xiaohongshu") and parsed_video:
    if parsed_video.no_watermark_video_url:
        no_watermark_verified = True
    # 无水印地址为空时，自动调用第三方API兜底
    elif self.third_party_service.is_configured():
        third_party_result = await self.third_party_service.parse(raw_url)
        if third_party_result:
            parsed_video = third_party_result
            parse_source = "fallback"
            no_watermark_verified = True
```

**关键改进**：
- 快手/小红书自有解析成功且有无水印地址 → 标记 `verified = True`
- 自有解析未获取到无水印地址 → 自动调用 bugpk.com 对应平台 API 兜底
- native 模式也支持验证状态标记

### 6. 测试结果

| 平台 | 耗时 | 无水印URL来源 | 解析来源 | 验证状态 |
|------|------|-------------|---------|---------|
| 快手 | 18.4秒 | `v23-3.kwaicdn.com` | native | ✅ 通过 |
| 小红书 | 8.0秒 | `sns-video-zl.xhscdn.com` | native | ✅ 通过 |

### 7. 防盗链处理

快手和小红书的 CDN 也有防盗链机制，已在 [http_client.py](file:///f:/Pyhton_Project/WeChatProject/qushuiyin/server/utils/http_client.py) 中统一处理：

```python
if "kuaishou" in url.lower():
    headers["Referer"] = "https://www.kuaishou.com/"
elif "xiaohongshu" in url.lower():
    headers["Referer"] = "https://www.xiaohongshu.com/"
```

### 8. 三平台对比总结

| 特性 | 抖音 | 快手 | 小红书 |
|------|------|------|--------|
| 解析方式 | 官方API + 签名 | 页面HTML提取 | 页面HTML提取 |
| 无水印来源 | `bit_rate[].play_addr` | `srcNoMark` | `masterUrl` |
| 有水印来源 | `download_addr` | `photoUrl` | `og:video`(meta) |
| 第三方兜底 | bugpk.com 抖音端点 | bugpk.com 快手端点 | bugpk.com 小红书端点 |
| 防盗链Referer | `douyin.com` | `kuaishou.com` | `xiaohongshu.com` |
| 是否需要签名 | 是（a_bogus） | 否 | 否 |
| 平均耗时 | 5-10秒 | 15-20秒 | 5-10秒 |
