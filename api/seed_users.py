"""
Seed Test Users for API Development
Creates users for each role with known passwords.
"""

import psycopg2
from .auth import hash_password
import os


def seed_test_users():
    """Create test users for all roles."""
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "collectos"),
        user=os.getenv("POSTGRES_USER", "collectos"),
        password=os.getenv("POSTGRES_PASSWORD", "collectos_dev_password_change_in_production"),
    )

    cur = conn.cursor()

    test_users = [
        ("admin", "admin@collectos.local", "admin123", "ADMIN", None),
        ("strategy", "strategy@collectos.local", "strategy123", "STRATEGY", None),
        ("tl_north", "tl1@collectos.local", "tl123", "TL", "TL00001"),
        ("acm_north", "acm1@collectos.local", "acm123", "ACM", "ACM00001"),
        ("fos_delhi", "fos1@collectos.local", "fos123", "AGENT", "FOS00001"),
        ("tc_delhi", "tc1@collectos.local", "tc123", "AGENT", "TC00001"),
        ("auditor", "auditor@collectos.local", "audit123", "AUDITOR", None),
    ]

    for username, email, password, role, agent_id in test_users:
        user_id = f"USR_{username.upper()}"
        password_hash = hash_password(password)

        # Check if user exists
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            print(f"User '{username}' already exists, skipping...")
            continue

        cur.execute("""
            INSERT INTO users (
                user_id, username, email, password_hash, role, agent_id, active
            ) VALUES (%s, %s, %s, %s, %s, %s, true)
        """, (user_id, username, email, password_hash, role, agent_id))

        print(f"✓ Created user: {username} (role={role}, password={password})")

    conn.commit()
    cur.close()
    conn.close()

    print("\n" + "="*60)
    print("Test Users Created Successfully!")
    print("="*60)
    print("\nCredentials:")
    for username, _, password, role, _ in test_users:
        print(f"  {username:12} / {password:12} (role: {role})")
    print("\nLogin at: POST /api/v1/auth/login")
    print("="*60)


if __name__ == "__main__":
    seed_test_users()
