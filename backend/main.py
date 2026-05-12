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
from sqlalchemy import func

from models import (
    init_db, KeystrokeEvent, TypingSession, WordFrequency,
    MoodRecord, DailyStats, ApplicationUsage, RealTimeStats
)
from keyboard_hook import KeyboardHook

DB_URL = "mysql+pymysql://root@localhost/keyboard_monitor?charset=utf8mb4"
PORT = 65500

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine, SessionLocal = init_db(DB_URL)
session_lock = Lock()

current_session_id = None
session_start_time = None

def get_or_create_session(db):
    global current_session_id, session_start_time
    
    if current_session_id is None:
        current_session_id = str(uuid.uuid4())
        session_start_time = datetime.now()
        session = TypingSession(
            session_id=current_session_id,
            start_time=session_start_time,
            is_active=True
        )
        db.add(session)
        db.commit()
    
    return current_session_id

def is_printable_key(key_name: str, key_char: str = None) -> bool:
    if key_char and key_char.strip():
        return True
    if not key_name or len(key_name) == 0:
        return False
    ignore_keys = ['Key.shift', 'Key.ctrl', 'Key.alt', 'Key.cmd', 'Key.tab',
                  'Key.enter', 'Key.backspace', 'Key.delete', 'Key.esc',
                  'Key.up', 'Key.down', 'Key.left', 'Key.right']
    if any(k in key_name for k in ignore_keys):
        return False
    if key_name.startswith('Key.'):
        return False
    return True

def detect_char_type(char: str) -> str:
    if not char:
        return "special"
    if '\u4e00' <= char <= '\u9fff':
        return "chinese"
    if char.isalpha():
        return "english"
    if char.isdigit():
        return "digit"
    if char == ' ':
        return "space"
    if char in '.,!?;:\'"()-[]{}':
        return "punctuation"
    return "special"

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
    today = datetime.now().strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        keystrokes_count = db.query(KeystrokeEvent).filter(
            func.date(KeystrokeEvent.timestamp) == today
        ).count()
        
        printable_events = db.query(KeystrokeEvent).filter(
            func.date(KeystrokeEvent.timestamp) == today,
            KeystrokeEvent.is_printable == True
        ).count()
        
        delete_events = db.query(KeystrokeEvent).filter(
            func.date(KeystrokeEvent.timestamp) == today,
            KeystrokeEvent.key_name.in_(['Key.backspace', 'Key.delete'])
        ).count()
        
        valid_input = printable_events - delete_events
        
        return {
            "session_id": current_session_id,
            "keystrokes_count": keystrokes_count,
            "characters_count": printable_events,
            "deleted_count": delete_events,
            "valid_input_count": max(0, valid_input),
        }
    finally:
        db.close()

@app.get("/api/stats/daily")
async def get_daily_stats(date: Optional[str] = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    db = SessionLocal()
    try:
        keystrokes_count = db.query(KeystrokeEvent).filter(
            func.date(KeystrokeEvent.timestamp) == date
        ).count()
        
        printable_count = db.query(KeystrokeEvent).filter(
            func.date(KeystrokeEvent.timestamp) == date,
            KeystrokeEvent.is_printable == True
        ).count()
        
        delete_count = db.query(KeystrokeEvent).filter(
            func.date(KeystrokeEvent.timestamp) == date,
            KeystrokeEvent.key_name.in_(['Key.backspace', 'Key.delete'])
        ).count()
        
        sessions_count = db.query(TypingSession).filter(
            func.date(TypingSession.start_time) == date
        ).count()
        
        return {
            "date": date,
            "total_keystrokes": keystrokes_count,
            "total_characters": printable_count,
            "total_deletes": delete_count,
            "total_sessions": sessions_count,
        }
    finally:
        db.close()

@app.get("/api/stats/word-frequency")
async def get_word_frequency(limit: int = 50, date: Optional[str] = None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    db = SessionLocal()
    try:
        from sqlalchemy import func
        word_freq = db.query(
            WordFrequency.word,
            func.sum(WordFrequency.count).label('total_count')
        ).filter(
            WordFrequency.date == date
        ).group_by(
            WordFrequency.word
        ).order_by(
            func.sum(WordFrequency.count).desc()
        ).limit(limit).all()
        
        return [{"word": wf.word, "count": wf.total_count} for wf in word_freq]
    finally:
        db.close()

@app.get("/api/stats/mood-history")
async def get_mood_history(days: int = 7):
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        records = db.query(MoodRecord).filter(
            MoodRecord.date >= start_date
        ).order_by(MoodRecord.timestamp).all()
        
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "mood": r.mood_label,
                "mood_score": r.mood_score,
            }
            for r in records
        ]
    finally:
        db.close()

@app.post("/api/keystroke")
async def record_keystroke_api(data: dict):
    db = SessionLocal()
    try:
        session_id = get_or_create_session(db)
        
        key_name = data.get("key_name", "")
        key_char = data.get("key_char")
        key_code = data.get("key_code", 0)
        input_method = data.get("input_method", "unknown")
        application = data.get("application", "Unknown")
        
        event = KeystrokeEvent(
            key_code=key_code,
            key_name=key_name,
            key_char=key_char,
            input_method=input_method,
            application=application,
            session_id=session_id,
            is_printable=is_printable_key(key_name, key_char),
            char_type=detect_char_type(key_char) if key_char else None
        )
        db.add(event)
        
        if is_printable_key(key_name, key_char) and key_char:
            char_type = detect_char_type(key_char)
            today = datetime.now().strftime("%Y-%m-%d")
            existing = db.query(WordFrequency).filter(
                WordFrequency.word == key_char,
                WordFrequency.date == today,
                WordFrequency.session_id == session_id
            ).first()
            
            if existing:
                existing.count += 1
            else:
                word_freq = WordFrequency(
                    word=key_char,
                    word_type=char_type,
                    count=1,
                    date=today,
                    session_id=session_id
                )
                db.add(word_freq)
        
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording keystroke: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

keyboard_hook = None

def on_keystroke_callback(data):
    db = SessionLocal()
    try:
        session_id = get_or_create_session(db)
        
        key_name = data.get("key_name", "")
        key_char = data.get("key_char")
        key_code = data.get("key_code", 0)
        input_method = data.get("input_method", "unknown")
        application = data.get("application", "Unknown")
        
        event = KeystrokeEvent(
            key_code=key_code,
            key_name=key_name,
            key_char=key_char,
            input_method=input_method,
            application=application,
            session_id=session_id,
            is_printable=is_printable_key(key_name, key_char),
            char_type=detect_char_type(key_char) if key_char else None
        )
        db.add(event)
        
        if is_printable_key(key_name, key_char) and key_char:
            char_type = detect_char_type(key_char)
            today = datetime.now().strftime("%Y-%m-%d")
            existing = db.query(WordFrequency).filter(
                WordFrequency.word == key_char,
                WordFrequency.date == today,
                WordFrequency.session_id == session_id
            ).first()
            
            if existing:
                existing.count += 1
            else:
                word_freq = WordFrequency(
                    word=key_char,
                    word_type=char_type,
                    count=1,
                    date=today,
                    session_id=session_id
                )
                db.add(word_freq)
        
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error in on_keystroke_callback: {e}")
    finally:
        db.close()

def run_server():
    global keyboard_hook
    
    keyboard_hook = KeyboardHook(on_keystroke=on_keystroke_callback)
    keyboard_hook.start()
    logger.info("Keyboard hook started")
    
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")

if __name__ == "__main__":
    print(f"🚀 Keyboard Monitor Backend started on port {PORT}")
    print(f"📊 API docs at http://127.0.0.1:{PORT}/docs")
    print(f"⌨️  Keyboard hook active - capturing keystrokes")
    run_server()
