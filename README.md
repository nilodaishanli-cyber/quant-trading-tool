# 实时盘中量化交易分析系统

这是一个个人使用的 A 股实时盘中量化交易辅助系统。核心技术为 `Python + Streamlit`，不需要注册、登录、多用户和复杂前后端分离。部署后，手机和电脑浏览器打开网址即可使用。

## 功能

- 股票搜索
- 交易时间自动刷新
- 实时行情：当前价、涨跌幅、开盘价、最高价、最低价、成交量、成交额、换手率
- 实时市场环境：上证指数、深证成指、创业板指数、科创50指数
- 风险评分
- 技术评分
- 资金评分
- 集合竞价分析
- 集合竞价 20/60/250 日历史概率
- 5/10/20/30 日均线买入评估
- 分时黄线 / VWAP 分析
- 黄线突破和跌破概率统计
- 10:30-10:50 方向判断
- 10:50 多空确认：上涨概率、下跌概率、多方评分、空方评分
- 历史概率统计
- 买入区域分析
- K 线图
- CSV 导出

## 数据源说明

第一版使用 AkShare 免费行情：

- 日线行情：腾讯 / 东方财富接口互为备用
- 实时个股：东方财富实时行情接口
- 实时指数：东方财富指数实时行情接口
- 分钟数据：AkShare 1分钟行情接口

限制：

- 免费接口是轮询近实时数据，不是交易所 Level-2 推送。
- 集合竞价未匹配买卖量、盘口委托队列、逐笔成交等字段需要后续接入 Level-2 或第三方数据源。
- 如果免费接口无法稳定提供 250 日逐分钟回放，黄线历史概率会使用日内均价线代理事件统计，并在页面标注口径。

## 项目结构

```text
frontend/          Streamlit 页面
models/            量化模型、风险评分、概率统计、回测
data/data_source.py 统一行情数据源入口
data/realtime_market.py 实时行情、交易时间、分钟线
data/providers/    日线行情数据源
utils/             通用工具
deploy/            Nginx、Docker、systemd 部署文件
backend/           API 预留模块，个人单服务版默认不启动
tasks/             定时任务预留
```

## 本地运行

```bash
pip install -r requirements.txt
streamlit run frontend/streamlit_app.py
```

浏览器访问：

```text
http://127.0.0.1:8501
```

同一局域网手机访问：

1. 电脑和手机连接同一个 Wi-Fi。
2. 查询电脑局域网 IP，例如 macOS：

```bash
ipconfig getifaddr en0
```

3. 用手机浏览器打开：

```text
http://电脑局域网IP:8501
```

如果需要让局域网其他设备访问，启动时使用：

```bash
streamlit run frontend/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

兼容旧入口：

```bash
streamlit run app.py
```

## 服务器部署

推荐：

- 阿里云 ECS 或 腾讯云 CVM
- Ubuntu 22.04 / 24.04
- 2 核 CPU / 4GB 内存 / 40GB SSD 起步
- 开放端口：22、80、443

安装环境：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

部署代码：

```bash
cd /opt/quant-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

测试启动：

```bash
streamlit run frontend/streamlit_app.py \
  --server.address 127.0.0.1 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false
```

## systemd 守护

```bash
sudo cp deploy/systemd/quant-streamlit.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable quant-streamlit
sudo systemctl start quant-streamlit
```

查看状态：

```bash
sudo systemctl status quant-streamlit
```

## Nginx 反向代理

复制 `deploy/nginx.conf`，把 `yourdomain.com` 改成你的域名。

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/quant-platform
sudo ln -s /etc/nginx/sites-available/quant-platform /etc/nginx/sites-enabled/quant-platform
sudo nginx -t
sudo systemctl reload nginx
```

代理关系：

```text
https://你的域名.com -> 127.0.0.1:8501
```

## HTTPS

方案一：阿里云 / 腾讯云免费 SSL 证书

- 在云控制台申请证书
- 下载 Nginx 证书
- 在 Nginx 中配置 `ssl_certificate` 和 `ssl_certificate_key`

方案二：Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d 你的域名.com
```

## 备案提示

如果服务器在中国大陆，并绑定自己的域名，通常需要完成 ICP 备案。

如果暂时不想备案，可以先部署到中国香港服务器。

## Docker 运行

```bash
cd deploy
docker compose up -d
```

然后用 Nginx 代理到：

```text
127.0.0.1:8501
```
