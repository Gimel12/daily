"""
SQLite database for storing DNS query logs and device info.
"""
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from config import DB_PATH

_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
    return _local.conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS dns_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source_ip TEXT NOT NULL,
            source_mac TEXT DEFAULT '',
            domain TEXT NOT NULL,
            query_type TEXT DEFAULT 'A',
            response TEXT DEFAULT '',
            device_name TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_dns_timestamp ON dns_queries(timestamp);
        CREATE INDEX IF NOT EXISTS idx_dns_source_ip ON dns_queries(source_ip);
        CREATE INDEX IF NOT EXISTS idx_dns_domain ON dns_queries(domain);

        CREATE TABLE IF NOT EXISTS devices (
            ip TEXT PRIMARY KEY,
            mac TEXT NOT NULL,
            hostname TEXT DEFAULT '',
            vendor TEXT DEFAULT '',
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        );
    """)
    conn.commit()


def log_dns_query(source_ip: str, domain: str, query_type: str = "A",
                  source_mac: str = "", response: str = "", device_name: str = ""):
    """Insert a DNS query record."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO dns_queries (timestamp, source_ip, source_mac, domain, query_type, response, device_name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), source_ip, source_mac, domain, query_type, response, device_name)
    )
    conn.commit()


def get_recent_queries(limit: int = 100, offset: int = 0) -> List[Dict]:
    """Get most recent DNS queries."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM dns_queries ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    return [dict(r) for r in rows]


def search_queries(term: str, limit: int = 200,
                   from_date: Optional[str] = None,
                   to_date: Optional[str] = None) -> List[Dict]:
    """Search DNS queries by domain substring."""
    conn = get_conn()
    query = "SELECT * FROM dns_queries WHERE domain LIKE ?"
    params: list = [f"%{term}%"]

    if from_date:
        query += " AND timestamp >= ?"
        params.append(from_date)
    if to_date:
        query += " AND timestamp <= ?"
        params.append(to_date)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_queries_by_device(ip: str, limit: int = 200,
                          from_date: Optional[str] = None,
                          to_date: Optional[str] = None) -> List[Dict]:
    """Get DNS queries from a specific device IP."""
    conn = get_conn()
    query = "SELECT * FROM dns_queries WHERE source_ip = ?"
    params: list = [ip]

    if from_date:
        query += " AND timestamp >= ?"
        params.append(from_date)
    if to_date:
        query += " AND timestamp <= ?"
        params.append(to_date)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def get_device_report(ip: str, days: int = 30) -> Dict:
    """Generate a summary report for a device over N days."""
    conn = get_conn()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM dns_queries WHERE source_ip = ? AND timestamp >= ?",
        (ip, since)
    ).fetchone()["cnt"]

    top_domains = conn.execute(
        "SELECT domain, COUNT(*) as cnt FROM dns_queries "
        "WHERE source_ip = ? AND timestamp >= ? "
        "GROUP BY domain ORDER BY cnt DESC LIMIT 50",
        (ip, since)
    ).fetchall()

    daily = conn.execute(
        "SELECT DATE(timestamp) as day, COUNT(*) as cnt FROM dns_queries "
        "WHERE source_ip = ? AND timestamp >= ? "
        "GROUP BY DATE(timestamp) ORDER BY day DESC",
        (ip, since)
    ).fetchall()

    return {
        "ip": ip,
        "days": days,
        "total_queries": total,
        "top_domains": [dict(r) for r in top_domains],
        "daily_breakdown": [dict(r) for r in daily],
    }


def get_query_stats() -> Dict:
    """Get overall stats for the status endpoint."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as cnt FROM dns_queries").fetchone()["cnt"]
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM dns_queries WHERE timestamp >= ?",
        (today,)
    ).fetchone()["cnt"]
    unique_devices = conn.execute(
        "SELECT COUNT(DISTINCT source_ip) as cnt FROM dns_queries"
    ).fetchone()["cnt"]

    return {
        "total_queries": total,
        "queries_today": today_count,
        "unique_devices": unique_devices,
    }


def upsert_device(ip: str, mac: str, hostname: str = "", vendor: str = ""):
    """Insert or update a discovered device."""
    conn = get_conn()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO devices (ip, mac, hostname, vendor, first_seen, last_seen) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(ip) DO UPDATE SET mac=?, hostname=?, vendor=?, last_seen=?",
        (ip, mac, hostname, vendor, now, now, mac, hostname, vendor, now)
    )
    conn.commit()


def get_all_devices() -> List[Dict]:
    """Get all known devices."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    return [dict(r) for r in rows]


def get_unique_domains(ip: str = None, days: int = 7, limit: int = 500) -> List[Dict]:
    """Get unique domains with visit counts, optionally filtered by device IP."""
    conn = get_conn()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    if ip:
        rows = conn.execute(
            "SELECT domain, COUNT(*) as cnt, MIN(timestamp) as first_seen, MAX(timestamp) as last_seen "
            "FROM dns_queries WHERE source_ip = ? AND timestamp >= ? "
            "GROUP BY domain ORDER BY cnt DESC LIMIT ?",
            (ip, since, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT domain, source_ip, COUNT(*) as cnt, MIN(timestamp) as first_seen, MAX(timestamp) as last_seen "
            "FROM dns_queries WHERE timestamp >= ? "
            "GROUP BY domain, source_ip ORDER BY cnt DESC LIMIT ?",
            (since, limit)
        ).fetchall()

    return [dict(r) for r in rows]


def get_all_queries_for_alerts(hours: int = 24) -> List[Dict]:
    """Get all queries from the last N hours for alert scanning."""
    conn = get_conn()
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT * FROM dns_queries WHERE timestamp >= ? ORDER BY id DESC",
        (since,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_activity_timeline(ip: str, days: int = 7) -> List[Dict]:
    """Get hourly activity breakdown for a device."""
    conn = get_conn()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, COUNT(*) as cnt "
        "FROM dns_queries WHERE source_ip = ? AND timestamp >= ? "
        "GROUP BY hour ORDER BY hour DESC",
        (ip, since)
    ).fetchall()
    return [dict(r) for r in rows]
