"""
键盘监控后端
数据模型 - SQLite数据库详尽字段设计
"""

from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, DateTime, Text, Boolean, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class KeystrokeEvent(Base):
    """按键事件表 - 记录每一次按键"""
    __tablename__ = 'keystroke_events'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 时间戳
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)

    # 按键信息
    key_code = Column(Integer, nullable=False)
    key_name = Column(String(64), nullable=False)
    key_char = Column(String(8), nullable=True)

    # 输入上下文
    input_method = Column(String(32), nullable=False, index=True)  # ABC/拼音/五笔等
    application = Column(String(128), nullable=True)  # 当前应用
    window_title = Column(String(256), nullable=True)  # 窗口标题

    # 打字速度相关
    interval_ms = Column(Integer, nullable=True)  # 距上次按键的毫秒数
    session_id = Column(String(64), nullable=False, index=True)

    # 字符类型
    is_printable = Column(Boolean, default=False)
    char_type = Column(String(16), nullable=True)  # chinese/english/punctuation/digit/special

    # 创建索引
    __table_args__ = (
        Index('idx_timestamp_session', 'timestamp', 'session_id'),
        Index('idx_session_inputmethod', 'session_id', 'input_method'),
    )


class TypingSession(Base):
    """打字会话表 - 一次会话"""
    __tablename__ = 'typing_sessions'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)

    # 会话时间
    start_time = Column(DateTime, default=datetime.now, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # 打字统计
    total_keystrokes = Column(Integer, default=0)
    total_characters = Column(Integer, default=0)  # 可打印字符数
    total_backspaces = Column(Integer, default=0)
    total_deletes = Column(Integer, default=0)

    # 速度统计 (WPM = words per minute, CPM = characters per minute)
    avg_wpm = Column(Float, nullable=True)
    max_wpm = Column(Float, nullable=True)
    avg_cpm = Column(Float, nullable=True)

    # 输入法使用统计 (JSON格式)
    input_method_usage = Column(Text, nullable=True)  # {"ABC": 150, "拼音": 300}

    # 状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class WordFrequency(Base):
    """词频表 - 记录词/字使用频率"""
    __tablename__ = 'word_frequency'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 词/字信息
    word = Column(String(32), nullable=False, index=True)
    word_type = Column(String(16), nullable=False)  # chinese / english

    # 频率统计
    count = Column(Integer, default=1, nullable=False)
    total_count = Column(BigInteger, default=1)  # 累计使用次数

    # 时间维度 (方便按天/周/月统计)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    session_id = Column(String(64), nullable=True, index=True)

    # 最近使用
    last_used = Column(DateTime, default=datetime.now)

    # 位置统计
    is_first_char = Column(Boolean, default=False)  # 是否是句子开头
    is_last_char = Column(Boolean, default=False)  # 是否是句子结尾

    __table_args__ = (
        Index('idx_word_date', 'word', 'date'),
        Index('idx_date_type_count', 'date', 'word_type', 'count'),
    )


class MoodRecord(Base):
    """心情记录表 - 通过输入内容识别心情"""
    __tablename__ = 'mood_records'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 时间
    timestamp = Column(DateTime, default=datetime.now, nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    session_id = Column(String(64), nullable=True, index=True)

    # 心情分析结果
    mood_score = Column(Float, nullable=False)  # -1.0 ~ 1.0 (负面 ~ 正面)
    mood_label = Column(String(16), nullable=False)  # happy/sad/angry/calm/anxious/neutral

    # 情绪指标
    emotion_intensity = Column(Float, default=0.5)  # 情绪强度 0~1
    sentiment_polarity = Column(Float, nullable=True)  # 情感极性

    # 分析文本片段
    analyzed_text = Column(Text, nullable=True)
    text_length = Column(Integer, nullable=True)

    # 上下文
    input_method = Column(String(32), nullable=True)
    typing_speed = Column(Float, nullable=True)  # 分析时的打字速度

    # 创建索引
    __table_args__ = (
        Index('idx_date_mood', 'date', 'mood_score'),
        Index('idx_session_mood', 'session_id', 'timestamp'),
    )


class DailyStats(Base):
    """每日汇总统计表"""
    __tablename__ = 'daily_stats'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    date = Column(String(10), unique=True, nullable=False, index=True)

    # 打字统计
    total_sessions = Column(Integer, default=0)
    total_typing_time = Column(Integer, default=0)  # 秒
    total_keystrokes = Column(BigInteger, default=0)
    total_characters = Column(BigInteger, default=0)

    # 速度统计
    avg_typing_speed = Column(Float, nullable=True)  # 平均WPM
    max_typing_speed = Column(Float, nullable=True)  # 最大WPM

    # 输入法使用
    most_used_input_method = Column(String(32), nullable=True)
    input_method多样性 = Column(Integer, default=0)  # 使用了几种输入法

    # 心情统计
    avg_mood_score = Column(Float, nullable=True)
    dominant_mood = Column(String(16), nullable=True)
    mood_variance = Column(Float, nullable=True)  # 心情波动程度

    # 词汇统计
    unique_words = Column(Integer, default=0)
    most_productive_hour = Column(Integer, nullable=True)  # 打字最多的小时

    # 创建时间
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ApplicationUsage(Base):
    """应用使用统计表"""
    __tablename__ = 'application_usage'

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    date = Column(String(10), nullable=False, index=True)
    session_id = Column(String(64), nullable=True)

    application_name = Column(String(128), nullable=False, index=True)
    window_title = Column(String(256), nullable=True)

    # 使用统计
    keystrokes = Column(Integer, default=0)
    characters = Column(Integer, default=0)
    active_time = Column(Integer, default=0)  # 秒

    # 时间段
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_date_app', 'date', 'application_name'),
    )


class RealTimeStats(Base):
    """实时统计表 - 当前会话实时数据"""
    __tablename__ = 'real_time_stats'

    id = Column(BigInteger, primary_key=True)

    session_id = Column(String(64), unique=True, nullable=False, index=True)

    # 实时速度
    current_wpm = Column(Float, default=0)
    current_cpm = Column(Float, default=0)

    # 实时心情
    current_mood = Column(String(16), default='neutral')
    current_mood_score = Column(Float, default=0)

    # 实时计数
    keystrokes_in_session = Column(Integer, default=0)
    characters_in_session = Column(Integer, default=0)

    # 输入法
    current_input_method = Column(String(32), default='unknown')

    # 最近活动时间
    last_activity = Column(DateTime, default=datetime.now)

    # 更新戳
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def init_db(db_path: str = "keyboard_monitor.db"):
    """初始化数据库"""
    engine = create_engine(f'sqlite:///{db_path}', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


if __name__ == "__main__":
    init_db()
    print("Database initialized: keyboard_monitor.db")
