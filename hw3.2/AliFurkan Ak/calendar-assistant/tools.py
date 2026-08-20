import sqlite3
import os
from datetime import datetime, timedelta
import json

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "calendar.db")

def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        category TEXT DEFAULT 'general',
        status TEXT DEFAULT 'confirmed',
        created_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plans (
        id TEXT PRIMARY KEY,
        goal_name TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

def get_calendar_events(start_date: str, end_date: str, keyword: str = None) -> dict:
    """Query calendar events between start_date (YYYY-MM-DD) and end_date (YYYY-MM-DD) to check schedule and busy slots.
    
    Args:
        start_date: YYYY-MM-DD or YYYY-MM-DD HH:mm start date
        end_date: YYYY-MM-DD or YYYY-MM-DD HH:mm end date
        keyword: Optional search keyword in title or description
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if len(start_date) == 10:
        start_date = f"{start_date} 00:00"
    if len(end_date) == 10:
        end_date = f"{end_date} 23:59"

    query = """
    SELECT id, title, description, start_time, end_time, category, status
    FROM events
    WHERE status != 'cancelled'
      AND (
        (start_time >= ? AND start_time <= ?) OR
        (end_time >= ? AND end_time <= ?) OR
        (start_time <= ? AND end_time >= ?)
      )
    """
    params = [start_date, end_date, start_date, end_date, start_date, end_date]

    if keyword:
        query += " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ?)"
        k_param = f"%{keyword.lower()}%"
        params.extend([k_param, k_param])

    query += " ORDER BY start_time ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    events_list = [dict(r) for r in rows]
    return {
        "count": len(events_list),
        "period": {"start": start_date, "end": end_date},
        "events": events_list
    }

def find_free_slots(date: str, duration_minutes: int = 60, start_hour: int = 8, end_hour: int = 20) -> dict:
    """Find available free time windows in SQLite calendar.
    
    Args:
        date: Target date in YYYY-MM-DD format
        duration_minutes: Required free duration in minutes (default: 60)
        start_hour: Day starting hour (default: 8)
        end_hour: Day ending hour (default: 20)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    day_start_str = f"{date} {start_hour:02d}:00"
    day_end_str = f"{date} {end_hour:02d}:00"

    cursor.execute("""
    SELECT id, title, start_time, end_time FROM events
    WHERE status != 'cancelled' AND start_time < ? AND end_time > ?
    ORDER BY start_time ASC
    """, (day_end_str, day_start_str))
    rows = cursor.fetchall()
    conn.close()

    fmt = "%Y-%m-%d %H:%M"
    day_start_dt = datetime.strptime(day_start_str, fmt)
    day_end_dt = datetime.strptime(day_end_str, fmt)

    free_slots = []
    current_ptr = day_start_dt
    req_delta = timedelta(minutes=duration_minutes)

    for row in rows:
        try:
            b_start = datetime.strptime(row["start_time"], fmt)
            b_end = datetime.strptime(row["end_time"], fmt)
        except ValueError:
            continue

        if b_end <= day_start_dt:
            continue
        if b_start >= day_end_dt:
            break

        gap = b_start - current_ptr
        if gap >= req_delta:
            free_slots.append({
                "start_time": current_ptr.strftime(fmt),
                "end_time": b_start.strftime(fmt),
                "available_minutes": int(gap.total_seconds() / 60)
            })

        if b_end > current_ptr:
            current_ptr = b_end

    if (day_end_dt - current_ptr) >= req_delta:
        free_slots.append({
            "start_time": current_ptr.strftime(fmt),
            "end_time": day_end_dt.strftime(fmt),
            "available_minutes": int((day_end_dt - current_ptr).total_seconds() / 60)
        })

    return {
        "date": date,
        "requested_duration_minutes": duration_minutes,
        "free_slots_found": len(free_slots),
        "free_slots": free_slots
    }

def book_event(title: str, start_time: str, end_time: str, description: str = None, category: str = "general") -> dict:
    """Book an appointment or event (e.g. dentist visit, meetings, workout).
    
    Args:
        title: Title of the event
        start_time: Start date and time in YYYY-MM-DD HH:mm format
        end_time: End date and time in YYYY-MM-DD HH:mm format
        description: Optional detailed description
        category: Category such as medical, work, health, personal, general
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    event_id = f"evt-{int(datetime.utcnow().timestamp() * 1000)}"
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    desc = description or "Booked via Gemini AI Assistant"

    cursor.execute("""
    INSERT INTO events (id, title, description, start_time, end_time, category, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 'confirmed', ?)
    """, (event_id, title, desc, start_time, end_time, category, created_at))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Successfully booked '{title}' in SQLite calendar.",
        "event": {
            "id": event_id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "category": category
        }
    }

def cancel_event(event_id_or_date: str, reason: str = None) -> dict:
    """Cancel appointment or clear day schedule.
    
    Args:
        event_id_or_date: Event ID (e.g. evt-12345) OR date string (YYYY-MM-DD) to clear all events on that day
        reason: Optional cancellation reason
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    is_date = False
    try:
        dt = datetime.strptime(event_id_or_date, "%Y-%m-%d")
        is_date = True
    except ValueError:
        is_date = False

    if is_date:
        day_start = f"{event_id_or_date} 00:00"
        day_end = f"{event_id_or_date} 23:59"
        cursor.execute("""
        UPDATE events SET status = 'cancelled'
        WHERE start_time >= ? AND start_time <= ? AND status != 'cancelled'
        """, (day_start, day_end))
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return {
            "success": True,
            "cancelled_count": count,
            "message": f"Cancelled {count} event(s) scheduled on {event_id_or_date}. {reason or ''}".strip()
        }
    else:
        cursor.execute("UPDATE events SET status = 'cancelled' WHERE id = ?", (event_id_or_date,))
        count = cursor.rowcount
        conn.commit()
        conn.close()

        if count == 0:
            return {"success": False, "error": f"No event found with ID '{event_id_or_date}'."}

        return {
            "success": True,
            "message": f"Event ID '{event_id_or_date}' cancelled successfully. {reason or ''}".strip()
        }

def create_multistep_plan(goal: str, start_date: str, duration_days: int = 3, daily_minutes: int = 60) -> dict:
    """Auto-generate multi-day plan schedule into SQLite.
    
    Args:
        goal: Goal description (e.g. 'Workout plan', 'Exam preparation')
        start_date: Start date YYYY-MM-DD
        duration_days: Number of days for the plan (default: 3)
        daily_minutes: Minutes per session (default: 60)
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    plan_id = f"plan-{int(datetime.utcnow().timestamp() * 1000)}"
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=duration_days)

    cursor.execute("""
    INSERT INTO plans (id, goal_name, start_date, end_date, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (plan_id, goal, start_date, end_dt.strftime("%Y-%m-%d"), now_str))

    created_events = []
    for i in range(duration_days):
        day_dt = start_dt + timedelta(days=i)
        session_start = day_dt.replace(hour=15, minute=0)
        session_end = session_start + timedelta(minutes=daily_minutes)

        s_start_str = session_start.strftime("%Y-%m-%d %H:%M")
        s_end_str = session_end.strftime("%Y-%m-%d %H:%M")
        evt_id = f"evt-plan-{plan_id}-d{i+1}"
        evt_title = f"{goal} - Day {i+1}"
        evt_desc = f"Plan session {i+1} for goal '{goal}'"

        cursor.execute("""
        INSERT INTO events (id, title, description, start_time, end_time, category, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'plan', 'confirmed', ?)
        """, (evt_id, evt_title, evt_desc, s_start_str, s_end_str, now_str))

        created_events.append({
            "id": evt_id,
            "title": evt_title,
            "day": i + 1,
            "start_time": s_start_str,
            "end_time": s_end_str
        })

    conn.commit()
    conn.close()

    return {
        "success": True,
        "plan_id": plan_id,
        "goal": goal,
        "total_events_created": len(created_events),
        "events": created_events
    }

def update_event(event_id: str, new_title: str = None, new_start_time: str = None, new_end_time: str = None, new_description: str = None, new_category: str = None) -> dict:
    """Update an existing calendar event title, start_time, end_time, description, or category.
    
    Args:
        event_id: ID of the event to update (e.g. evt-12345)
        new_title: New title of the event
        new_start_time: New start time in YYYY-MM-DD HH:mm format
        new_end_time: New end time in YYYY-MM-DD HH:mm format
        new_description: New description
        new_category: New category name
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, description, start_time, end_time, category FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": f"No event found with ID '{event_id}'."}

    curr_title, curr_desc, curr_start, curr_end, curr_cat = row

    updated_title = new_title if new_title is not None else curr_title
    updated_desc = new_description if new_description is not None else curr_desc
    updated_start = new_start_time if new_start_time is not None else curr_start
    updated_end = new_end_time if new_end_time is not None else curr_end
    updated_cat = new_category if new_category is not None else curr_cat

    cursor.execute("""
    UPDATE events
    SET title = ?, description = ?, start_time = ?, end_time = ?, category = ?
    WHERE id = ?
    """, (updated_title, updated_desc, updated_start, updated_end, updated_cat, event_id))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "message": f"Successfully updated event '{event_id}'.",
        "updated_event": {
            "id": event_id,
            "title": updated_title,
            "description": updated_desc,
            "start_time": updated_start,
            "end_time": updated_end,
            "category": updated_cat
        }
    }

