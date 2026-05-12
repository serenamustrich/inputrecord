# 键盘监控服务

实时监控键盘输入，记录按键频率、输入统计和键盘热力图。

## 🚀 快速安装（推荐）

```bash
# 一键安装系统服务（开机自动启动，静默运行）
./install_service.sh
```

安装后：
- ✅ 开机自动启动
- ✅ 静默运行（无终端窗口）
- ✅ 进程崩溃自动重启
- ✅ 日志输出到 `logs/` 目录

卸载服务：
```bash
./uninstall_service.sh
```

---

## 功能特性

- ⌨️ **全按键监控** - 记录所有按键（包括功能键、空格、回车等）
- 📊 **按键频率统计** - 每个按键的使用次数
- 🔤 **有效输入统计** - 总字符数减去删除次数
- 🎨 **键盘热力图** - 可视化显示按键频率
- 📈 **数据持久化** - MySQL 存储，重启不丢失

## 架构

```
keyboard_monitor/
├── backend/
│   ├── main.py           # FastAPI 主服务 (端口 65500)
│   ├── models.py         # MySQL 数据模型
│   ├── keyboard_hook.py  # 键盘监控模块
│   └── requirements.txt
├── frontend/
│   ├── index.html        # 监控仪表盘
│   └── server.py         # 前端服务器 (端口 1314)
├── logs/                 # 服务日志
├── start.sh              # 手动启动脚本
├── install_service.sh    # 安装系统服务
├── uninstall_service.sh  # 卸载系统服务
└── restart_service.sh    # 重启服务
```

## 快速启动

### 手动启动

```bash
cd keyboard_monitor

# 启动所有服务
./start.sh

# 或分别启动
cd backend && python3 main.py      # 后端
cd frontend && python3 server.py   # 前端
```

### 安装系统服务（推荐）

开机自动启动，静默运行，无需终端窗口：

```bash
# 安装服务
./install_service.sh

# 卸载服务
./uninstall_service.sh
```

**服务特性：**
- ✅ 开机自动启动
- ✅ 静默运行（无终端窗口）
- ✅ 进程崩溃自动重启
- ✅ 日志输出到 `logs/` 目录

## 访问

- 仪表盘: http://127.0.0.1:1314
- API文档: http://127.0.0.1:65500/docs

## 查看日志

```bash
tail -f logs/backend.log
tail -f logs/frontend.log
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stats/realtime` | GET | 获取实时统计 |
| `/api/stats/daily` | GET | 获取每日统计 |
| `/api/stats/word-frequency` | GET | 获取词频统计 |
| `/api/keystroke` | POST | 记录按键 |

### 实时统计返回字段

| 字段 | 说明 |
|------|------|
| `keystrokes_count` | 按键总次数 |
| `characters_count` | 可打印字符数 |
| `deleted_count` | 删除次数（退格/删除键） |
| `valid_input_count` | 有效输入数 = 字符数 - 删除次数 |

### 词频统计返回字段

| 字段 | 说明 |
|------|------|
| `word` | 按键名称（如 "a", "Key.space", "Key.enter"） |
| `count` | 使用次数 |

## 数据库

使用 MySQL 存储，数据库名：`keyboard_monitor`

主要表：

- `keystroke_events` - 所有按键事件
- `word_frequency` - 按键频率统计
- `typing_sessions` - 打字会话

### 数据库配置

```python
DB_URL = "mysql+pymysql://root@localhost/keyboard_monitor?charset=utf8mb4"
```

### 创建数据库

```sql
CREATE DATABASE keyboard_monitor CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## 依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- fastapi
- uvicorn
- pynput (键盘监控)
- sqlalchemy
- pymysql (MySQL 连接)
