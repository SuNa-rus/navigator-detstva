"""SQLite persistence for the local educational prototype."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def database_path() -> Path:
    return Path(os.environ.get("NAVIGATOR_DB_PATH", Path(__file__).resolve().parents[1] / "data" / "navigator.sqlite3"))


@contextmanager
def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


CATEGORIES = [
    ("preparation", "Подготовка к приёму", "calendar-check"),
    ("everyday", "Повседневный уход", "heart-handshake"),
    ("development", "Развитие ребёнка", "sprout"),
    ("support", "Помощь родителям", "hand-heart"),
]

ARTICLES = [
    (1, "Как подготовиться к визиту к специалисту", "preparation", "Подготовьте вопросы и необходимые документы заранее.",
     "Перед визитом удобно записать вопросы к специалисту и уточнить, какие документы нужно взять. Если что-то непонятно, попросите объяснить рекомендации простыми словами. Этот демонстрационный материал не заменяет консультацию врача.", 3),
    (2, "Как пользоваться памятками и рекомендациями", "preparation", "Отличаем общую информацию от индивидуальных назначений.",
     "Проверяйте дату публикации и источник памятки. Общая информация помогает подготовиться к разговору со специалистом, но индивидуальные назначения и вопросы здоровья обсуждаются с медицинским работником.", 4),
    (3, "Удобный распорядок дня семьи", "everyday", "Спокойная организация повседневных дел.",
     "Планирование семейных дел может облегчить повседневную нагрузку. Выбирайте подходящий семье ритм, оставляйте время для отдыха и при необходимости обсуждайте возникающие трудности со специалистами.", 3),
    (4, "Где искать информацию о развитии ребёнка", "development", "Ориентируемся в источниках и избегаем самодиагностики.",
     "Развитие каждого ребёнка индивидуально. Используйте проверенные образовательные источники, а возникающие вопросы обсуждайте с профильным специалистом. Материалы проекта не предназначены для постановки диагноза.", 5),
    (5, "Вопросы, которые полезно задать на приёме", "support", "Небольшой список для содержательного разговора.",
     "Можно спросить о цели рекомендаций, порядке дальнейших действий и о том, к кому обращаться при дополнительных вопросах. Записывайте ответы в собственные заметки, не публикуя личную медицинскую информацию.", 2),
    (6, "Как устроен цифровой маршрут", "development", "Знакомимся с примером возрастных разделов.",
     "Маршрут в этой учебной версии показывает общие возрастные разделы. Он не является персональным медицинским планом и не содержит утверждённого графика обследований. Состав и сроки маршрута требуют согласования с больницей.", 3),
]

STAGES = [
    (1, "Первый год", "0–1 год", "Обзор информационных материалов для семей с малышами. Содержание и медицинские мероприятия требуют согласования с заказчиком."),
    (2, "Раннее детство", "1–3 года", "Общие сведения о доступных разделах и подготовке вопросов для специалистов."),
    (3, "Дошкольный возраст", "3–6 лет", "Подборка образовательных материалов для родителей дошкольников."),
    (4, "Школьные годы", "7–11 лет", "Информационный раздел для семей детей младшего школьного возраста."),
    (5, "Подростковый период", "12–17 лет", "Общие образовательные материалы по вопросам взросления и семейной поддержки."),
]


def initialize():
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'parent' CHECK (role IN ('parent', 'medic', 'editor', 'admin')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS categories (
                slug TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                icon TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL REFERENCES categories(slug),
                summary TEXT NOT NULL,
                body TEXT NOT NULL,
                reading_minutes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'review', 'published'))
            );
            CREATE TABLE IF NOT EXISTS stages (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                age TEXT NOT NULL,
                description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS progress (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                stage_id INTEGER NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, stage_id)
            );
        """)
        db.executemany("INSERT OR IGNORE INTO categories (slug, title, icon) VALUES (?, ?, ?)", CATEGORIES)
        db.executemany("""
            INSERT OR IGNORE INTO articles
                (id, title, category, summary, body, reading_minutes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'published')
        """, ARTICLES)
        db.executemany("INSERT OR IGNORE INTO stages (id, title, age, description) VALUES (?, ?, ?, ?)", STAGES)