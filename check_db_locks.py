"""
Read-only. Checks Railway Postgres for any long-running or blocking queries
that could explain why /api/cart/ requests are hanging and timing out.

Run from C:\\Users\\texca\\pokemart-api with DATABASE_URL uncommented:
    python manage.py shell -c "exec(open('check_db_locks.py').read())"
"""
from django.db import connection

with connection.cursor() as cursor:
    print("--- Active/idle-in-transaction queries (anything running >5s) ---")
    cursor.execute("""
        SELECT pid, state, now() - query_start AS duration, query, wait_event_type, wait_event
        FROM pg_stat_activity
        WHERE state != 'idle' AND pid != pg_backend_pid()
        ORDER BY duration DESC;
    """)
    rows = cursor.fetchall()
    if not rows:
        print("  None found — no long-running or stuck queries right now.")
    for r in rows:
        pid, state, duration, query, wait_type, wait_event = r
        print(f"  pid={pid} state={state} duration={duration} wait={wait_type}/{wait_event}")
        print(f"    query: {query[:200]}")

    print("\n--- Locks currently held (anything blocking another query) ---")
    cursor.execute("""
        SELECT blocked_locks.pid AS blocked_pid,
               blocking_locks.pid AS blocking_pid,
               blocked_activity.query AS blocked_query,
               blocking_activity.query AS blocking_query
        FROM pg_catalog.pg_locks blocked_locks
        JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
        JOIN pg_catalog.pg_locks blocking_locks
            ON blocking_locks.locktype = blocked_locks.locktype
            AND blocking_locks.database IS DISTINCT FROM NULL
            AND blocking_locks.pid != blocked_locks.pid
        JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
        WHERE NOT blocked_locks.granted;
    """)
    blocks = cursor.fetchall()
    if not blocks:
        print("  None found — nothing is currently blocked on a lock.")
    for b in blocks:
        blocked_pid, blocking_pid, blocked_query, blocking_query = b
        print(f"  pid {blocked_pid} is BLOCKED BY pid {blocking_pid}")
        print(f"    blocked query:  {blocked_query[:150]}")
        print(f"    blocking query: {blocking_query[:150]}")

    print("\n--- Total active connections ---")
    cursor.execute("SELECT count(*) FROM pg_stat_activity;")
    print(f"  {cursor.fetchone()[0]} total connections")
