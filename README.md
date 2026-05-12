# 键盘监控服务

实时监控键盘输入，记录打字速度、输入法使用、词频统计和心情变化。

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

- ⌨️ **实时按键监控** - 记录每一次按键
- 📊 **打字速度统计** - WPM/CPM 实时计算
- 🌐 **输入法检测** - 识别拼音/ABC/五笔等
- 🔤 **词频统计** - 中英文分开统计高频字词
- 😊 **心情识别** - 通过输入内容分析情绪变化
- 📈 **数据可视化** - 实时刷新的仪表盘
- 🚀 **系统服务** - 开机自动启动，静默运行
- ✅ **有效输入统计** - 总字符数减去删除次数

## 架构

```
keyboard_monitor/
├── backend/
│   ├── main.py           # FastAPI 主服务 (端口 65500)
│   ├── models.py         # SQLite 数据模型
│   ├── keyboard_hook.py  # 键盘监控模块
│   └── requirements.txt
├── frontend/
│   ├── index.html        # 监控仪表盘
│   └── server.py         # 前端服务器 (端口 1314)
├── logs/                 # 服务日志
├── start.sh              # 手动启动脚本
├── install_service.sh    # 安装系统服务
└── uninstall_service.sh  # 卸载系统服务
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
| `/api/stats/mood-history` | GET | 获取心情历史 |
| `/api/keystroke` | POST | 记录按键 |
| `/ws` | WebSocket | 实时数据推送 |

### 实时统计返回字段

| 字段 | 说明 |
|------|------|
| `characters_count` | 总输入字符数 |
| `deleted_count` | 删除次数（退格/删除键） |
| `valid_input_count` | 有效输入数 = 字符数 - 删除次数 |
| `keystrokes_count` | 按键总次数 |
| `current_wpm` | 当前打字速度 (WPM) |
| `current_cpm` | 当前打字速度 (CPM) |
| `current_mood` | 当前心情 |
| `current_input_method` | 当前输入法 |

## 数据库

使用 SQLite 存储，主要表：

- `keystroke_events` - 按键事件
- `typing_sessions` - 打字会话
- `word_frequency` - 词频统计
- `mood_records` - 心情记录
- `daily_stats` - 每日汇总
