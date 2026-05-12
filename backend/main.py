"""
键盘监控后端服务
端口: 65500
"""

import os
import sys
import time
import json
import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from threading import Thread, Lock
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 本地模块
from models import (
    init_db, KeystrokeEvent, TypingSession, WordFrequency,
    MoodRecord, DailyStats, ApplicationUsage, RealTimeStats
)
from keyboard_hook import KeyboardHook

# 配置
DB_PATH = os.path.join(os.path.dirname(__file__), "keyboard_monitor.db")
PORT = 65500
WS_PORT = 65500

# MiniMax API配置
def load_minimax_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            return (
                config.get("minimax_api_key", ""),
                config.get("minimax_api_base", "https://api.minimax.chat/v1"),
                config.get("minimax_model", "MiniMax-M2.7-highspeed")
            )
    return os.environ.get("MINIMAX_API_KEY", ""), "https://api.minimax.chat/v1", "MiniMax-M2.7-highspeed"

MINIMAX_API_KEY, MINIMAX_API_BASE, MINIMAX_MODEL = load_minimax_config()

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量
engine, SessionLocal = init_db(DB_PATH)
current_session_id = None
session_lock = Lock()

# MiniMax客户端
minimax_client = None

# 实时数据
realtime_data = {
    "session_id": None,
    "current_wpm": 0,
    "current_cpm": 0,
    "current_mood": "neutral",
    "current_mood_score": 0,
    "keystrokes_count": 0,
    "characters_count": 0,
    "deleted_count": 0,  # 删除次数
    "current_input_method": "unknown",
    "last_key_time": None,
    "recent_keys": [],  # 最近N个按键用于心情分析
    "word_buffer": "",  # 当前输入的词/句
    "start_time": None,
}

# WebSocket 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


# ==================== 数据模型 ====================

class KeystrokeInput(BaseModel):
    key_code: int
    key_name: str
    key_char: Optional[str] = None
    input_method: str = "unknown"
    application: Optional[str] = None
    window_title: Optional[str] = None


class MoodAnalysisInput(BaseModel):
    text: str
    session_id: Optional[str] = None


# ==================== 辅助函数 ====================

def get_current_input_method() -> str:
    """获取当前输入法（macOS）"""
    try:
        import subprocess
        script = '''
        tell application "System Events"
            try
                return value of attribute "AXPrimaryIMMarkedBuffer" of first text area of first window of (first process whose frontmost is true)
            on error
                return ""
            end try
        end tell
        '''
        result = subprocess.run(["osascript", "-e", script],
                              capture_output=True, text=True, timeout=1)
        if result.stdout.strip():
            return "拼音/中文输入"
        return "ABC"
    except:
        return "unknown"


def calculate_wpm(chars: int, seconds: float) -> float:
    """计算WPM (Word Per Minute)"""
    if seconds <= 0:
        return 0
    return (chars / 5) / (seconds / 60)  # 1 word = 5 characters


def calculate_cpm(chars: int, seconds: float) -> float:
    """计算CPM (Characters Per Minute)"""
    if seconds <= 0:
        return 0
    return chars / (seconds / 60)


def analyze_mood(text: str) -> tuple[str, float]:
    """
    心情分析 - 使用 MiniMax API
    返回: (mood_label, mood_score -1.0~1.0)
    """
    if not text or len(text.strip()) < 2:
        return "neutral", 0

    # 优先使用 MiniMax API
    if MINIMAX_API_KEY:
        try:
            return analyze_mood_with_minimax(text)
        except Exception as e:
            logger.warning(f"MiniMax情绪分析失败，使用备用: {e}")

    # 备用：关键词匹配
    return analyze_mood_by_keywords(text)


def analyze_mood_with_minimax(text: str) -> tuple[str, float]:
    """
    使用 MiniMax API 进行情绪分析
    """
    global minimax_client

    if not minimax_client:
        try:
            from openai import OpenAI
            minimax_client = OpenAI(
                api_key=MINIMAX_API_KEY,
                base_url=MINIMAX_API_BASE
            )
        except ImportError:
            logger.warning("openai库未安装，使用备用方案")
            return analyze_mood_by_keywords(text)

    system_prompt = """你是一个情绪分析专家。根据用户输入的文本，分析其中的情绪倾向。

请以JSON格式返回分析结果：
{
    "emotion": "happy|sad|angry|anxious|calm|neutral",
    "score": -1.0到1.0之间的数值（负面到正面）,
    "intensity": 0.0到1.0之间的数值（情绪强度）,
    "reason": "简短分析理由"
}

注意：
- score: -1.0表示极度负面/悲伤, 0表示中性, 1.0表示极度正面/开心
- intensity: 0.0表示几乎没有情绪, 1.0表示情绪非常强烈
- 只返回JSON，不要有其他内容"""

    try:
        response = minimax_client.chat.completions.create(
            model=MINIMAX_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请分析这段文字的情绪：{text}"}
            ],
            temperature=0.3,
            max_tokens=200
        )

        result_text = response.choices[0].message.content.strip()

        # 解析JSON响应
        import json
        import re
        try:
            # 清理思考标签和中文引号
            result_text = result_text.replace("<think>", "").replace("</think>", "").strip()
            result_text = result_text.replace(""", '"').replace(""", '"')

            # 尝试提取JSON代码块
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                parts = result_text.split("```")
                for part in parts:
                    if "{" in part:
                        result_text = part
                        break

            # 使用正则提取JSON对象
            json_match = re.search(r'\{[^{}]*"[^{}]*[^{}]*\}', result_text)
            if json_match:
                result_text = json_match.group(0)
            else:
                # 尝试找到最后一个 { 到最后一个 } 之间的内容
                first_brace = result_text.find('{')
                last_brace = result_text.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    result_text = result_text[first_brace:last_brace+1]

            result = json.loads(result_text)

            emotion = result.get("emotion", "neutral")
            score = float(result.get("score", 0))
            intensity = float(result.get("intensity", 0.5))

            logger.debug(f"情绪分析结果: {emotion}, score={score}, intensity={intensity}")

            return emotion, score

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 原文: {result_text}")
            return analyze_mood_by_keywords(text)

    except Exception as e:
        logger.error(f"MiniMax API调用失败: {e}")
        raise  # 让上层catch后使用备用方案


def analyze_mood_by_keywords(text: str) -> tuple[str, float]:
    """
    备用心情分析 - 关键词匹配
    返回: (mood_label, mood_score -1.0~1.0)
    """
    if not text:
        return "neutral", 0

    text_lower = text.lower()

    # 正面词汇
    positive_words = ["好", "棒", "优", "美", "乐", "喜", "赞", "牛", "强", "酷", "开心", "高兴",
                     "good", "great", "nice", "love", "happy", "awesome", "amazing", "excellent"]
    # 负面词汇
    negative_words = ["差", "烂", "糟", "坏", "悲", "怒", "烦", "累", "难", "苦", "难过", "生气",
                     "bad", "shit", "hate", "angry", "sad", "terrible", "awful", "sucks"]
    # 焦虑词汇
    anxious_words = ["焦虑", "紧张", "担心", "怕", "慌", "压力",
                    "anxious", "nervous", "worried", "stress"]

    positive_count = sum(1 for w in positive_words if w in text_lower)
    negative_count = sum(1 for w in negative_words if w in text_lower)
    anxious_count = sum(1 for w in anxious_words if w in text_lower)

    if anxious_count > positive_count and anxious_count > negative_count:
        return "anxious", -0.3 - anxious_count * 0.1
    elif positive_count > negative_count:
        return "happy", min(1.0, 0.3 + positive_count * 0.15)
    elif negative_count > positive_count:
        return "sad", max(-1.0, -0.3 - negative_count * 0.15)

    return "neutral", 0


def detect_char_type(char: str) -> str:
    """检测字符类型"""
    if not char:
        return "unknown"
    code = ord(char)

    # 中文
    if 0x4e00 <= code <= 0x9fff:
        return "chinese"
    # 英文字母
    elif (0x61 <= code <= 0x7a) or (0x41 <= code <= 0x5a):
        return "english"
    # 数字
    elif 0x30 <= code <= 0x39:
        return "digit"
    # 标点
    elif 33 <= code <= 47 or 58 <= code <= 64 or 91 <= code <= 96 or 123 <= code <= 126:
        return "punctuation"
    # 特殊
    else:
        return "special"


def is_printable_key(key_name: str) -> bool:
    """判断是否是可打印字符"""
    if not key_name or len(key_name) == 0:
        return False
    # 过滤功能键
    ignore_keys = ['Key.shift', 'Key.ctrl', 'Key.alt', 'Key.cmd', 'Key.tab',
                  'Key.enter', 'Key.backspace', 'Key.delete', 'Key.esc',
                  'Key.space', 'Key.up', 'Key.down', 'Key.left', 'Key.right']
    if any(k in key_name for k in ignore_keys):
        return False
    if key_name.startswith('Key.'):
        return False
    return True


# ==================== API路由 ====================

app = FastAPI(title="Keyboard Monitor API", port=PORT)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "keyboard_monitor", "port": PORT}


@app.get("/api/stats/realtime")
async def get_realtime_stats():
    """获取实时统计"""
    return {
        "session_id": realtime_data["session_id"],
        "current_wpm": round(realtime_data["current_wpm"], 1),
        "current_cpm": round(realtime_data["current_cpm"], 1),
        "current_mood": realtime_data["current_mood"],
        "current_mood_score": realtime_data["current_mood_score"],
        "keystrokes_count": realtime_data["keystrokes_count"],
        "characters_count": realtime_data["characters_count"],
        "deleted_count": realtime_data["deleted_count"],
        "valid_input_count": realtime_data["characters_count"] - realtime_data["deleted_count"],
        "current_input_method": realtime_data["current_input_method"],
        "elapsed_seconds": (datetime.now() - realtime_data["start_time"]).seconds if realtime_data["start_time"] else 0
    }


@app.get("/api/stats/daily")
async def get_daily_stats(date: Optional[str] = None):
    """获取每日统计"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        stats = db.query(DailyStats).filter(DailyStats.date == date).first()
        if not stats:
            return {"date": date, "message": "No data for this date"}

        return {
            "date": stats.date,
            "total_sessions": stats.total_sessions,
            "total_typing_time": stats.total_typing_time,
            "total_keystrokes": stats.total_keystrokes,
            "total_characters": stats.total_characters,
            "avg_typing_speed": stats.avg_typing_speed,
            "max_typing_speed": stats.max_typing_speed,
            "most_used_input_method": stats.most_used_input_method,
            "avg_mood_score": stats.avg_mood_score,
            "dominant_mood": stats.dominant_mood,
            "unique_words": stats.unique_words
        }
    finally:
        db.close()


@app.get("/api/stats/word-frequency")
async def get_word_frequency(limit: int = 20, date: Optional[str] = None, word_type: Optional[str] = None):
    """获取词频统计"""
    db = SessionLocal()
    try:
        query = db.query(WordFrequency)

        if date:
            query = query.filter(WordFrequency.date == date)
        if word_type:
            query = query.filter(WordFrequency.word_type == word_type)

        words = query.order_by(WordFrequency.count.desc()).limit(limit).all()

        return [
            {
                "word": w.word,
                "count": w.count,
                "word_type": w.word_type,
                "date": w.date
            }
            for w in words
        ]
    finally:
        db.close()


@app.get("/api/stats/mood-history")
async def get_mood_history(days: int = 7):
    """获取心情历史"""
    db = SessionLocal()
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        records = db.query(MoodRecord).filter(
            MoodRecord.date >= start_date
        ).order_by(MoodRecord.timestamp).all()

        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "date": r.date,
                "mood": r.mood_label,
                "mood_score": r.mood_score,
                "emotion_intensity": r.emotion_intensity,
                "analyzed_text": r.analyzed_text[:50] if r.analyzed_text else None
            }
            for r in records
        ]
    finally:
        db.close()


@app.get("/api/stats/typing-speed")
async def get_typing_speed_history(days: int = 7):
    """获取打字速度历史"""
    db = SessionLocal()
    try:
        sessions = db.query(TypingSession).filter(
            TypingSession.start_time >= datetime.now() - timedelta(days=days),
            TypingSession.is_active == False
        ).order_by(TypingSession.start_time).all()

        return [
            {
                "date": s.start_time.strftime("%Y-%m-%d %H:%M"),
                "avg_wpm": s.avg_wpm,
                "max_wpm": s.max_wpm,
                "total_characters": s.total_characters,
                "duration": s.duration_seconds
            }
            for s in sessions if s.avg_wpm
        ]
    finally:
        db.close()


@app.post("/api/keystroke")
async def record_keystroke(data: KeystrokeInput):
    """记录按键事件"""
    global realtime_data

    db = SessionLocal()
    try:
        # 更新实时数据
        with session_lock:
            if not realtime_data["session_id"]:
                realtime_data["session_id"] = str(uuid.uuid4())
                realtime_data["start_time"] = datetime.now()

            realtime_data["keystrokes_count"] += 1

            # 计算间隔
            now = datetime.now()
            interval_ms = 0
            if realtime_data["last_key_time"]:
                interval_ms = int((now - realtime_data["last_key_time"]).total_seconds() * 1000)
            realtime_data["last_key_time"] = now

            # 更新速度
            elapsed = (now - realtime_data["start_time"]).total_seconds()
            if elapsed > 0:
                realtime_data["current_wpm"] = calculate_wpm(realtime_data["characters_count"], elapsed)
                realtime_data["current_cpm"] = calculate_cpm(realtime_data["characters_count"], elapsed)

            # 更新输入法
            realtime_data["current_input_method"] = data.input_method

            # 检测删除键
            if data.key_name in ['Key.backspace', 'Key.delete']:
                realtime_data["deleted_count"] += 1

            # 记录可打印字符
            is_printable = is_printable_key(data.key_name)
            if is_printable and data.key_char:
                realtime_data["characters_count"] += 1
                realtime_data["word_buffer"] += data.key_char

                # 实时心情分析（累积一定字符后）
                if len(realtime_data["word_buffer"]) >= 10:
                    mood, score = analyze_mood(realtime_data["word_buffer"])
                    realtime_data["current_mood"] = mood
                    realtime_data["current_mood_score"] = score

                # 记录词频
                char_type = detect_char_type(data.key_char)
                if char_type in ["chinese", "english"]:
                    word_freq = WordFrequency(
                        word=data.key_char,
                        word_type=char_type,
                        count=1,
                        date=now.strftime("%Y-%m-%d"),
                        session_id=realtime_data["session_id"]
                    )
                    db.add(word_freq)

            # 记录按键事件
            event = KeystrokeEvent(
                key_code=data.key_code,
                key_name=data.key_name,
                key_char=data.key_char,
                input_method=data.input_method,
                application=data.application,
                window_title=data.window_title,
                interval_ms=interval_ms,
                session_id=realtime_data["session_id"],
                is_printable=is_printable,
                char_type=detect_char_type(data.key_char) if data.key_char else None
            )
            db.add(event)
            db.commit()

        # 广播更新
        await manager.broadcast({
            "type": "keystroke",
            "data": {
                "wpm": round(realtime_data["current_wpm"], 1),
                "cpm": round(realtime_data["current_cpm"], 1),
                "mood": realtime_data["current_mood"],
                "mood_score": realtime_data["current_mood_score"],
                "keystrokes": realtime_data["keystrokes_count"],
                "characters": realtime_data["characters_count"],
                "deleted_count": realtime_data["deleted_count"],
                "valid_input_count": realtime_data["characters_count"] - realtime_data["deleted_count"],
                "input_method": realtime_data["current_input_method"]
            }
        })

        return {"status": "ok"}

    except Exception as e:
        db.rollback()
        logger.error(f"Error recording keystroke: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/api/session/end")
async def end_session():
    """结束当前会话"""
    global realtime_data

    with session_lock:
        if not realtime_data["session_id"]:
            return {"status": "no_active_session"}

        db = SessionLocal()
        try:
            elapsed = (datetime.now() - realtime_data["start_time"]).total_seconds() if realtime_data["start_time"] else 0

            session = TypingSession(
                session_id=realtime_data["session_id"],
                start_time=realtime_data["start_time"],
                end_time=datetime.now(),
                duration_seconds=int(elapsed),
                total_keystrokes=realtime_data["keystrokes_count"],
                total_characters=realtime_data["characters_count"],
                avg_wpm=realtime_data["current_wpm"],
                max_wpm=realtime_data["current_wpm"],
                avg_cpm=realtime_data["current_cpm"],
                is_active=False
            )
            db.add(session)
            db.commit()

            # 重置
            realtime_data = {
                "session_id": None,
                "current_wpm": 0,
                "current_cpm": 0,
                "current_mood": "neutral",
                "current_mood_score": 0,
                "keystrokes_count": 0,
                "characters_count": 0,
                "current_input_method": "unknown",
                "last_key_time": None,
                "recent_keys": [],
                "word_buffer": "",
                "start_time": None,
            }

            return {"status": "session_ended"}

        finally:
            db.close()


# ==================== WebSocket ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket实时通信"""
    await manager.connect(websocket)
    try:
        # 发送当前状态
        await websocket.send_json({
            "type": "init",
            "data": {
                "session_id": realtime_data["session_id"],
                "current_wpm": realtime_data["current_wpm"],
                "current_cpm": realtime_data["current_cpm"],
                "current_mood": realtime_data["current_mood"],
                "keystrokes_count": realtime_data["keystrokes_count"],
                "characters_count": realtime_data["characters_count"],
                "deleted_count": realtime_data["deleted_count"],
                "valid_input_count": realtime_data["characters_count"] - realtime_data["deleted_count"],
                "current_input_method": realtime_data["current_input_method"]
            }
        })

        while True:
            # 保持连接
            data = await websocket.receive_text()
            # 可以处理客户端消息
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ==================== 键盘钩子 ====================

keyboard_hook = None

def on_keystroke_callback(data):
    """键盘钩子回调函数"""
    global realtime_data
    
    with session_lock:
        if not realtime_data["session_id"]:
            realtime_data["session_id"] = str(uuid.uuid4())
            realtime_data["start_time"] = datetime.now()
        
        realtime_data["keystrokes_count"] += 1
        
        now = datetime.now()
        interval_ms = 0
        if realtime_data["last_key_time"]:
            interval_ms = int((now - realtime_data["last_key_time"]).total_seconds() * 1000)
        realtime_data["last_key_time"] = now
        
        elapsed = (now - realtime_data["start_time"]).total_seconds()
        if elapsed > 0:
            realtime_data["current_wpm"] = calculate_wpm(realtime_data["characters_count"], elapsed)
            realtime_data["current_cpm"] = calculate_cpm(realtime_data["characters_count"], elapsed)
        
        realtime_data["current_input_method"] = data.get("input_method", "unknown")
        
        key_name = data.get("key_name", "")
        if key_name in ['Key.backspace', 'Key.delete']:
            realtime_data["deleted_count"] += 1
        
        is_printable = is_printable_key(key_name)
        if is_printable and data.get("key_char"):
            realtime_data["characters_count"] += 1
            realtime_data["word_buffer"] += data["key_char"]
            
            if len(realtime_data["word_buffer"]) >= 10:
                mood, score = analyze_mood(realtime_data["word_buffer"])
                realtime_data["current_mood"] = mood
                realtime_data["current_mood_score"] = score
            
            char_type = detect_char_type(data["key_char"])
            if char_type in ["chinese", "english"]:
                db = SessionLocal()
                try:
                    word_freq = WordFrequency(
                        word=data["key_char"],
                        word_type=char_type,
                        count=1,
                        date=now.strftime("%Y-%m-%d"),
                        session_id=realtime_data["session_id"]
                    )
                    db.add(word_freq)
                    db.commit()
                finally:
                    db.close()
        
        # Broadcast to WebSocket
        asyncio.run(manager.broadcast({
            "type": "keystroke",
            "data": {
                "wpm": round(realtime_data["current_wpm"], 1),
                "cpm": round(realtime_data["current_cpm"], 1),
                "mood": realtime_data["current_mood"],
                "mood_score": realtime_data["current_mood_score"],
                "keystrokes": realtime_data["keystrokes_count"],
                "characters": realtime_data["characters_count"],
                "deleted_count": realtime_data["deleted_count"],
                "valid_input_count": realtime_data["characters_count"] - realtime_data["deleted_count"],
                "input_method": realtime_data["current_input_method"]
            }
        }))


# ==================== 启动 ====================

def run_server():
    """运行服务器"""
    global keyboard_hook
    
    # Start keyboard hook
    keyboard_hook = KeyboardHook(on_keystroke=on_keystroke_callback)
    keyboard_hook.start()
    logger.info("Keyboard hook started")
    
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")


if __name__ == "__main__":
    print(f"🚀 Keyboard Monitor Backend started on port {PORT}")
    print(f"📊 WebSocket available at ws://127.0.0.1:{PORT}/ws")
    print(f"🌐 API docs at http://127.0.0.1:{PORT}/docs")
    print(f"⌨️  Keyboard hook active - capturing keystrokes")
    run_server()
