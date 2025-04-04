import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, time
import os
import re
from PIL import Image
import io
import pandas as pd

# --------------------------
# Database Functions
# --------------------------

def get_db_connection():
    """Create and return a database connection."""
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect("data/requests.db")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username, password):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        hashed_password = hash_password(password)
        cursor.execute("SELECT role FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", 
                      (username, hashed_password))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT CHECK(role IN ('agent', 'admin')))
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                request_type TEXT,
                identifier TEXT,
                comment TEXT,
                timestamp TEXT,
                completed INTEGER DEFAULT 0)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_leader TEXT,
                agent_name TEXT,
                ticket_id TEXT,
                error_description TEXT,
                timestamp TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                mentions TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hold_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uploader TEXT,
                image_data BLOB,
                timestamp TEXT)
        """)
        
        # Handle system_settings table schema migration
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_settings'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE system_settings (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    killswitch_enabled INTEGER DEFAULT 0,
                    chat_killswitch_enabled INTEGER DEFAULT 0)
            """)
            cursor.execute("INSERT INTO system_settings (id, killswitch_enabled, chat_killswitch_enabled) VALUES (1, 0, 0)")
        else:
            cursor.execute("PRAGMA table_info(system_settings)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'chat_killswitch_enabled' not in columns:
                cursor.execute("ALTER TABLE system_settings ADD COLUMN chat_killswitch_enabled INTEGER DEFAULT 0")
                cursor.execute("UPDATE system_settings SET chat_killswitch_enabled = 0 WHERE id = 1")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                break_name TEXT,
                start_time TEXT,
                end_time TEXT,
                max_users INTEGER,
                current_users INTEGER DEFAULT 0,
                created_by TEXT,
                timestamp TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS break_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                break_id INTEGER,
                user_id INTEGER,
                username TEXT,
                booking_date TEXT,
                timestamp TEXT,
                FOREIGN KEY(break_id) REFERENCES breaks(id))
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                user TEXT,
                comment TEXT,
                timestamp TEXT,
                FOREIGN KEY(request_id) REFERENCES requests(id))
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS late_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                presence_time TEXT,
                login_time TEXT,
                reason TEXT,
                timestamp TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                issue_type TEXT,
                timing TEXT,
                mobile_number TEXT,
                product TEXT,
                timestamp TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS midshift_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                issue_type TEXT,
                start_time TEXT,
                end_time TEXT,
                timestamp TEXT)
        """)
        
        # Create default admin account
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password, role) 
            VALUES (?, ?, ?)
        """, ("taha kirri", hash_password("arise@99"), "admin"))
        admin_accounts = [
            ("taha kirri", "arise@99"),
            ("Issam Samghini", "admin@2025"),
            ("Loubna Fellah", "admin@99"),
            ("Youssef Kamal", "admin@006"),
            ("Fouad Fathi", "admin@55")
        ]
        
        for username, password in admin_accounts:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, role) 
                VALUES (?, ?, ?)
            """, (username, hash_password(password), "admin"))
        
        # Create agent accounts (agent name as username, workspace ID as password)
        agents = [
            ("Karabila Younes", "30866"),
            ("Kaoutar Mzara", "30514"),
            ("Ben Tahar Chahid", "30864"),
            ("Cherbassi Khadija", "30868"),
            ("Lekhmouchi Kamal", "30869"),
            ("Said Kilani", "30626"),
            ("AGLIF Rachid", "30830"),
            ("Yacine Adouha", "30577"),
            ("Manal Elanbi", "30878"),
            ("Jawad Ouassaddine", "30559"),
            ("Kamal Elhaouar", "30844"),
            ("Hoummad Oubella", "30702"),
            ("Zouheir Essafi", "30703"),
            ("Anwar Atifi", "30781"),
            ("Said Elgaouzi", "30782"),
            ("HAMZA SAOUI", "30716"),
            ("Ibtissam Mazhari", "30970"),
            ("Imad Ghazali", "30971"),
            ("Jamila Lahrech", "30972"),
            ("Nassim Ouazzani Touhami", "30973"),
            ("Salaheddine Chaggour", "30974"),
            ("Omar Tajani", "30711"),
            ("Nizar Remz", "30728"),
            ("Abdelouahed Fettah", "30693"),
            ("Amal Bouramdane", "30675"),
            ("Fatima Ezzahrae Oubaalla", "30513"),
            ("Redouane Bertal", "30643"),
            ("Abdelouahab Chenani", "30789"),
            ("Imad El Youbi", "30797"),
            ("Youssef Hammouda", "30791"),
            ("Anas Ouassifi", "30894"),
            ("SALSABIL ELMOUSS", "30723"),
            ("Hicham Khalafa", "30712"),
            ("Ghita Adib", "30710"),
            ("Aymane Msikila", "30722"),
            ("Marouane Boukhadda", "30890"),
            ("Hamid Boulatouan", "30899"),
            ("Bouchaib Chafiqi", "30895"),
            ("Houssam Gouaalla", "30891"),
            ("Abdellah Rguig", "30963"),
            ("Abdellatif Chatir", "30964"),
            ("Abderrahman Oueto", "30965"),
            ("Fatiha Lkamel", "30967"),
            ("Abdelhamid Jaber", "30708"),
            ("Yassine Elkanouni", "30735")
        ]
        
        for agent_name, workspace_id in agents:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, role) 
                VALUES (?, ?, ?)
            """, (agent_name, hash_password(workspace_id), "agent"))
        
        conn.commit()
    finally:
        conn.close()

def is_killswitch_enabled():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT killswitch_enabled FROM system_settings WHERE id = 1")
        result = cursor.fetchone()
        return bool(result[0]) if result else False
    finally:
        conn.close()

def is_chat_killswitch_enabled():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT chat_killswitch_enabled FROM system_settings WHERE id = 1")
        result = cursor.fetchone()
        return bool(result[0]) if result else False
    finally:
        conn.close()

def toggle_killswitch(enable):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE system_settings SET killswitch_enabled = ? WHERE id = 1",
                      (1 if enable else 0,))
        conn.commit()
        return True
    finally:
        conn.close()

def toggle_chat_killswitch(enable):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE system_settings SET chat_killswitch_enabled = ? WHERE id = 1",
                      (1 if enable else 0,))
        conn.commit()
        return True
    finally:
        conn.close()

def add_request(agent_name, request_type, identifier, comment):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO requests (agent_name, request_type, identifier, comment, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """, (agent_name, request_type, identifier, comment, timestamp))
        
        request_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO request_comments (request_id, user, comment, timestamp)
            VALUES (?, ?, ?, ?)
        """, (request_id, agent_name, f"Request created: {comment}", timestamp))
        
        conn.commit()
        return True
    finally:
        conn.close()

def get_requests():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requests ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def search_requests(query):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = f"%{query.lower()}%"
        cursor.execute("""
            SELECT * FROM requests 
            WHERE LOWER(agent_name) LIKE ? 
            OR LOWER(request_type) LIKE ? 
            OR LOWER(identifier) LIKE ? 
            OR LOWER(comment) LIKE ?
            ORDER BY timestamp DESC
        """, (query, query, query, query))
        return cursor.fetchall()
    finally:
        conn.close()

def update_request_status(request_id, completed):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE requests SET completed = ? WHERE id = ?",
                      (1 if completed else 0, request_id))
        conn.commit()
        return True
    finally:
        conn.close()

def add_request_comment(request_id, user, comment):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO request_comments (request_id, user, comment, timestamp)
            VALUES (?, ?, ?, ?)
        """, (request_id, user, comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_request_comments(request_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM request_comments 
            WHERE request_id = ?
            ORDER BY timestamp ASC
        """, (request_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def add_mistake(team_leader, agent_name, ticket_id, error_description):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mistakes (team_leader, agent_name, ticket_id, error_description, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """, (team_leader, agent_name, ticket_id, error_description,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_mistakes():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM mistakes ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def search_mistakes(query):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = f"%{query.lower()}%"
        cursor.execute("""
            SELECT * FROM mistakes 
            WHERE LOWER(agent_name) LIKE ? 
            OR LOWER(ticket_id) LIKE ? 
            OR LOWER(error_description) LIKE ?
            ORDER BY timestamp DESC
        """, (query, query, query))
        return cursor.fetchall()
    finally:
        conn.close()

def send_group_message(sender, message):
    if is_killswitch_enabled() or is_chat_killswitch_enabled():
        st.error("Chat is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        mentions = re.findall(r'@(\w+)', message)
        cursor.execute("""
            INSERT INTO group_messages (sender, message, timestamp, mentions) 
            VALUES (?, ?, ?, ?)
        """, (sender, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
             ','.join(mentions)))
        conn.commit()
        return True
    finally:
        conn.close()

def get_group_messages():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM group_messages ORDER BY timestamp DESC LIMIT 50")
        return cursor.fetchall()
    finally:
        conn.close()

def get_all_users():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users")
        return cursor.fetchall()
    finally:
        conn.close()

def add_user(username, password, role):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                      (username, hash_password(password), role))
        conn.commit()
        return True
    finally:
        conn.close()

def delete_user(user_id):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def add_hold_image(uploader, image_data):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO hold_images (uploader, image_data, timestamp) 
            VALUES (?, ?, ?)
        """, (uploader, image_data, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_hold_images():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hold_images ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def clear_hold_images():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM hold_images")
        conn.commit()
        return True
    finally:
        conn.close()

def clear_all_requests():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM requests")
        cursor.execute("DELETE FROM request_comments")
        conn.commit()
        return True
    finally:
        conn.close()

def clear_all_mistakes():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mistakes")
        conn.commit()
        return True
    finally:
        conn.close()

def clear_all_group_messages():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM group_messages")
        conn.commit()
        return True
    finally:
        conn.close()

def add_break_slot(break_name, start_time, end_time, max_users, created_by):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO breaks (break_name, start_time, end_time, max_users, created_by, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (break_name, start_time, end_time, max_users, created_by,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def update_break_slot(break_id, break_name, start_time, end_time, max_users):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE breaks 
            SET break_name = ?, start_time = ?, end_time = ?, max_users = ?
            WHERE id = ?
        """, (break_name, start_time, end_time, max_users, break_id))
        conn.commit()
        return True
    finally:
        conn.close()

def get_all_break_slots():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM breaks ORDER BY start_time")
        return cursor.fetchall()
    finally:
        conn.close()

def get_available_break_slots(date):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.* 
            FROM breaks b
            LEFT JOIN (
                SELECT break_id, COUNT(*) as booking_count
                FROM break_bookings 
                WHERE booking_date = ?
                GROUP BY break_id
            ) bb ON b.id = bb.break_id
            WHERE b.max_users > IFNULL(bb.booking_count, 0)
            ORDER BY b.start_time
        """, (date,))
        return cursor.fetchall()
    finally:
        conn.close()

def book_break_slot(break_id, user_id, username, booking_date):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO break_bookings (break_id, user_id, username, booking_date, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """, (break_id, user_id, username, booking_date,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_user_bookings(username, date):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT bb.*, b.break_name, b.start_time, b.end_time
            FROM break_bookings bb
            JOIN breaks b ON bb.break_id = b.id
            WHERE bb.username = ? AND bb.booking_date = ?
        """, (username, date))
        return cursor.fetchall()
    finally:
        conn.close()

def get_all_bookings(date):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT bb.*, b.break_name, b.start_time, b.end_time, u.role
            FROM break_bookings bb
            JOIN breaks b ON bb.break_id = b.id
            JOIN users u ON bb.user_id = u.id
            WHERE bb.booking_date = ?
            ORDER BY b.start_time, bb.username
        """, (date,))
        return cursor.fetchall()
    finally:
        conn.close()

def delete_break_slot(break_id):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM breaks WHERE id = ?", (break_id,))
        cursor.execute("DELETE FROM break_bookings WHERE break_id = ?", (break_id,))
        conn.commit()
        return True
    finally:
        conn.close()

def clear_all_break_bookings():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM break_bookings")
        conn.commit()
        return True
    finally:
        conn.close()

def add_late_login(agent_name, presence_time, login_time, reason):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO late_logins (agent_name, presence_time, login_time, reason, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """, (agent_name, presence_time, login_time, reason,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_late_logins():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM late_logins ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def add_quality_issue(agent_name, issue_type, timing, mobile_number, product):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quality_issues (agent_name, issue_type, timing, mobile_number, product, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, issue_type, timing, mobile_number, product,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_quality_issues():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM quality_issues ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def add_midshift_issue(agent_name, issue_type, start_time, end_time):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO midshift_issues (agent_name, issue_type, start_time, end_time, timestamp) 
            VALUES (?, ?, ?, ?, ?)
        """, (agent_name, issue_type, start_time, end_time,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def get_midshift_issues():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM midshift_issues ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def clear_late_logins():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM late_logins")
        conn.commit()
        return True
    finally:
        conn.close()

def clear_quality_issues():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quality_issues")
        conn.commit()
        return True
    finally:
        conn.close()

def clear_midshift_issues():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM midshift_issues")
        conn.commit()
        return True
    finally:
        conn.close()

# --------------------------
# Fancy Number Checker Functions
# --------------------------

def is_sequential(digits, step=1):
    """Check if digits form a sequential pattern with given step"""
    try:
        return all(int(digits[i]) == int(digits[i-1]) + step for i in range(1, len(digits)))
    except:
        return False

def is_fancy_number(phone_number):
    clean_number = re.sub(r'\D', '', phone_number)
    
    # Get last 6 digits according to Lycamobile policy
    if len(clean_number) >= 6:
        last_six = clean_number[-6:]
        last_three = clean_number[-3:]
    else:
        return False, "Number too short (need at least 6 digits)"
    
    patterns = []
    
    # Special case for 13322866688
    if clean_number == "13322866688":
        patterns.append("Special VIP number (13322866688)")
    
    # Check for ABBBAA pattern (like 566655)
    if (len(last_six) == 6 and 
        last_six[0] == last_six[5] and 
        last_six[1] == last_six[2] == last_six[3] and 
        last_six[4] == last_six[0] and 
        last_six[0] != last_six[1]):
        patterns.append("ABBBAA pattern (e.g., 566655)")
    
    # Check for ABBBA pattern (like 233322)
    if (len(last_six) >= 5 and 
        last_six[0] == last_six[4] and 
        last_six[1] == last_six[2] == last_six[3] and 
        last_six[0] != last_six[1]):
        patterns.append("ABBBA pattern (e.g., 233322)")
    
    # 1. 6-digit patterns (strict matches only)
    # All same digits (666666)
    if len(set(last_six)) == 1:
        patterns.append("6 identical digits")
    
    # Consecutive ascending (123456)
    if is_sequential(last_six, 1):
        patterns.append("6-digit ascending sequence")
        
    # Consecutive descending (654321)
    if is_sequential(last_six, -1):
        patterns.append("6-digit descending sequence")
        
    # Palindrome (100001)
    if last_six == last_six[::-1]:
        patterns.append("6-digit palindrome")
    
    # 2. 3-digit patterns (strict matches from image)
    first_triple = last_six[:3]
    second_triple = last_six[3:]
    
    # Double triplets (444555)
    if len(set(first_triple)) == 1 and len(set(second_triple)) == 1 and first_triple != second_triple:
        patterns.append("Double triplets (444555)")
    
    # Similar triplets (121122)
    if (first_triple[0] == first_triple[1] and 
        second_triple[0] == second_triple[1] and 
        first_triple[2] == second_triple[2]):
        patterns.append("Similar triplets (121122)")
    
    # Repeating triplets (786786)
    if first_triple == second_triple:
        patterns.append("Repeating triplets (786786)")
    
    # Nearly sequential (457456) - exactly 1 digit difference
    if abs(int(first_triple) - int(second_triple)) == 1:
        patterns.append("Nearly sequential triplets (457456)")
    
    # 3. 2-digit patterns (strict matches from image)
    # Incremental pairs (111213)
    pairs = [last_six[i:i+2] for i in range(0, 5, 1)]
    try:
        if all(int(pairs[i]) == int(pairs[i-1]) + 1 for i in range(1, len(pairs))):
            patterns.append("Incremental pairs (111213)")
    
        # Repeating pairs (202020)
        if (pairs[0] == pairs[2] == pairs[4] and 
            pairs[1] == pairs[3] and 
            pairs[0] != pairs[1]):
            patterns.append("Repeating pairs (202020)")
    
        # Alternating pairs (010101)
        if (pairs[0] == pairs[2] == pairs[4] and 
            pairs[1] == pairs[3] and 
            pairs[0] != pairs[1]):
            patterns.append("Alternating pairs (010101)")
    
        # Stepping pairs (324252) - Fixed this check
        if (all(int(pairs[i][0]) == int(pairs[i-1][0]) + 1 for i in range(1, len(pairs))) and
            all(int(pairs[i][1]) == int(pairs[i-1][1]) + 2 for i in range(1, len(pairs)))):
            patterns.append("Stepping pairs (324252)")
    except:
        pass
    
    # 4. Exceptional cases (must match exactly)
    exceptional_triplets = ['123', '555', '777', '999']
    if last_three in exceptional_triplets:
        patterns.append(f"Exceptional case ({last_three})")
    
    # Strict validation - only allow patterns that exactly match our rules
    valid_patterns = []
    for p in patterns:
        if any(rule in p for rule in [
            "Special VIP number",
            "ABBBAA pattern",
            "ABBBA pattern",
            "6 identical digits",
            "6-digit ascending sequence",
            "6-digit descending sequence",
            "6-digit palindrome",
            "Double triplets (444555)",
            "Similar triplets (121122)",
            "Repeating triplets (786786)",
            "Nearly sequential triplets (457456)",
            "Incremental pairs (111213)",
            "Repeating pairs (202020)",
            "Alternating pairs (010101)",
            "Stepping pairs (324252)",
            "Exceptional case"
        ]):
            valid_patterns.append(p)
    
    return bool(valid_patterns), ", ".join(valid_patterns) if valid_patterns else "No qualifying fancy pattern"

# --------------------------
# Streamlit App
# --------------------------

st.set_page_config(
    page_title="Request Management System",
    page_icon=":office:",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background-color: #121212; color: #E0E0E0; }
    [data-testid="stSidebar"] { background-color: #1E1E1E; }
    .stButton>button { background-color: #2563EB; color: white; }
    .card { background-color: #1F1F1F; border-radius: 12px; padding: 1.5rem; }
    .metric-card { background-color: #1F2937; border-radius: 10px; padding: 20px; }
    .killswitch-active {
        background-color: #4A1E1E;
        border-left: 5px solid #D32F2F;
        padding: 1rem;
        margin-bottom: 1rem;
        color: #FFCDD2;
    }
    .chat-killswitch-active {
        background-color: #1E3A4A;
        border-left: 5px solid #1E88E5;
        padding: 1rem;
        margin-bottom: 1rem;
        color: #B3E5FC;
    }
    .comment-box {
        margin: 0.5rem 0;
        padding: 0.5rem;
        background: #2D2D2D;
        border-radius: 8px;
    }
    .comment-user {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.25rem;
    }
    .comment-text {
        margin-top: 0.5rem;
    }
    .editable-break {
        background-color: #2D3748;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    .stTimeInput > div > div > input {
        padding: 0.5rem;
    }
    .time-input {
        font-family: monospace;
    }
    /* Fancy number checker styles */
    .fancy-number { color: #00ff00; font-weight: bold; }
    .normal-number { color: #ffffff; }
    .result-box { padding: 15px; border-radius: 5px; margin: 10px 0; }
    .fancy-result { background-color: #1e3d1e; border: 1px solid #00ff00; }
    .normal-result { background-color: #3d1e1e; border: 1px solid #ff0000; }
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.update({
        "authenticated": False,
        "role": None,
        "username": None,
        "current_section": "requests",
        "last_request_count": 0,
        "last_mistake_count": 0,
        "last_message_ids": [],
        "break_edits": {}
    })

init_db()

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🏢 Request Management System")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                if username and password:
                    role = authenticate(username, password)
                    if role:
                        st.session_state.update({
                            "authenticated": True,
                            "role": role,
                            "username": username,
                            "last_request_count": len(get_requests()),
                            "last_mistake_count": len(get_mistakes()),
                            "last_message_ids": [msg[0] for msg in get_group_messages()]
                        })
                        st.rerun()
                    else:
                        st.error("Invalid credentials")

else:
    if is_killswitch_enabled():
        st.markdown("""
        <div class="killswitch-active">
            <h3>⚠️ SYSTEM LOCKED ⚠️</h3>
            <p>The system is currently in read-only mode.</p>
        </div>
        """, unsafe_allow_html=True)
    elif is_chat_killswitch_enabled():
        st.markdown("""
        <div class="chat-killswitch-active">
            <h3>⚠️ CHAT LOCKED ⚠️</h3>
            <p>The chat functionality is currently disabled.</p>
        </div>
        """, unsafe_allow_html=True)

    def show_notifications():
        current_requests = get_requests()
        current_mistakes = get_mistakes()
        current_messages = get_group_messages()
        
        new_requests = len(current_requests) - st.session_state.last_request_count
        if new_requests > 0 and st.session_state.last_request_count > 0:
            st.toast(f"📋 {new_requests} new request(s) submitted!")
        st.session_state.last_request_count = len(current_requests)
        
        new_mistakes = len(current_mistakes) - st.session_state.last_mistake_count
        if new_mistakes > 0 and st.session_state.last_mistake_count > 0:
            st.toast(f"❌ {new_mistakes} new mistake(s) reported!")
        st.session_state.last_mistake_count = len(current_mistakes)
        
        current_message_ids = [msg[0] for msg in current_messages]
        new_messages = [msg for msg in current_messages if msg[0] not in st.session_state.last_message_ids]
        for msg in new_messages:
            if msg[1] != st.session_state.username:
                mentions = msg[4].split(',') if msg[4] else []
                if st.session_state.username in mentions:
                    st.toast(f"💬 You were mentioned by {msg[1]}!")
                else:
                    st.toast(f"💬 New message from {msg[1]}!")
        st.session_state.last_message_ids = current_message_ids

    show_notifications()

    with st.sidebar:
        st.title(f"👋 Welcome, {st.session_state.username}")
        st.markdown("---")
        
        nav_options = [
            ("📋 Requests", "requests"),
            ("📊 Dashboard", "dashboard"),
            ("☕ Breaks", "breaks"),
            ("🖼️ HOLD", "hold"),
            ("❌ Mistakes", "mistakes"),
            ("💬 Chat", "chat"),
            ("📱 Fancy Number", "fancy_number"),
            ("⏰ Late Login", "late_login"),
            ("📞 Quality Issues", "quality_issues"),
            ("🔄 Mid-shift Issues", "midshift_issues")
        ]
        if st.session_state.role == "admin":
            nav_options.append(("⚙️ Admin", "admin"))
        
        for option, value in nav_options:
            if st.button(option, key=f"nav_{value}"):
                st.session_state.current_section = value
                
        st.markdown("---")
        pending_requests = len([r for r in get_requests() if not r[6]])
        new_mistakes = len(get_mistakes())
        unread_messages = len([m for m in get_group_messages() 
                             if m[0] not in st.session_state.last_message_ids 
                             and m[1] != st.session_state.username])
        
        st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <h4>🔔 Notifications</h4>
            <p>📋 Pending requests: {pending_requests}</p>
            <p>❌ Recent mistakes: {new_mistakes}</p>
            <p>💬 Unread messages: {unread_messages}</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.rerun()

    st.title(st.session_state.current_section.title())

    if st.session_state.current_section == "requests":
        if not is_killswitch_enabled():
            with st.expander("➕ Submit New Request"):
                with st.form("request_form"):
                    cols = st.columns([1, 3])
                    request_type = cols[0].selectbox("Type", ["Email", "Phone", "Ticket"])
                    identifier = cols[1].text_input("Identifier")
                    comment = st.text_area("Comment")
                    if st.form_submit_button("Submit"):
                        if identifier and comment:
                            if add_request(st.session_state.username, request_type, identifier, comment):
                                st.success("Request submitted successfully!")
                                st.rerun()
        
        st.subheader("🔍 Search Requests")
        search_query = st.text_input("Search requests...")
        requests = search_requests(search_query) if search_query else get_requests()
        
        st.subheader("All Requests")
        for req in requests:
            req_id, agent, req_type, identifier, comment, timestamp, completed = req
            with st.container():
                cols = st.columns([0.1, 0.9])
                with cols[0]:
                    if not is_killswitch_enabled():
                        st.checkbox("Done", value=bool(completed), 
                                   key=f"check_{req_id}", 
                                   on_change=update_request_status,
                                   args=(req_id, not completed))
                    else:
                        st.checkbox("Done", value=bool(completed), disabled=True)
                with cols[1]:
                    st.markdown(f"""
                    <div class="card">
                        <div style="display: flex; justify-content: space-between;">
                            <h4>#{req_id} - {req_type}</h4>
                            <small>{timestamp}</small>
                        </div>
                        <p>Agent: {agent}</p>
                        <p>Identifier: {identifier}</p>
                        <div style="margin-top: 1rem;">
                            <h5>Status Updates:</h5>
                    """, unsafe_allow_html=True)
                    
                    comments = get_request_comments(req_id)
                    for comment in comments:
                        cmt_id, _, user, cmt_text, cmt_time = comment
                        st.markdown(f"""
                            <div class="comment-box">
                                <div class="comment-user">
                                    <small><strong>{user}</strong></small>
                                    <small>{cmt_time}</small>
                                </div>
                                <div class="comment-text">{cmt_text}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    if st.session_state.role == "admin" and not is_killswitch_enabled():
                        with st.form(key=f"comment_form_{req_id}"):
                            new_comment = st.text_input("Add status update/comment")
                            if st.form_submit_button("Add Comment"):
                                if new_comment:
                                    add_request_comment(req_id, st.session_state.username, new_comment)
                                    st.rerun()

    elif st.session_state.current_section == "dashboard":
        st.subheader("📊 Request Completion Dashboard")
        all_requests = get_requests()
        total = len(all_requests)
        completed = sum(1 for r in all_requests if r[6])
        rate = (completed/total*100) if total > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Requests", total)
        with col2:
            st.metric("Completed", completed)
        with col3:
            st.metric("Completion Rate", f"{rate:.1f}%")
        
        df = pd.DataFrame({
            'Date': [datetime.strptime(r[5], "%Y-%m-%d %H:%M:%S").date() for r in all_requests],
            'Status': ['Completed' if r[6] else 'Pending' for r in all_requests],
            'Type': [r[2] for r in all_requests]
        })
        
        st.subheader("Request Trends")
        st.bar_chart(df['Date'].value_counts())
        
        st.subheader("Request Type Distribution")
        type_counts = df['Type'].value_counts().reset_index()
        type_counts.columns = ['Type', 'Count']
        st.bar_chart(type_counts.set_index('Type'))

    elif st.session_state.current_section == "breaks":
        today = datetime.now().strftime("%Y-%m-%d")
        selected_date = st.date_input("Select date", datetime.now())
        formatted_date = selected_date.strftime("%Y-%m-%d")
        
        if st.session_state.role == "admin":
            st.subheader("Admin: Break Schedule Management")
            
            with st.expander("➕ Add New Break Slot"):
                with st.form("add_break_form"):
                    cols = st.columns(3)
                    break_name = cols[0].text_input("Break Name")
                    start_time = cols[1].text_input("Start Time (HH:MM)")
                    end_time = cols[2].text_input("End Time (HH:MM)")
                    max_users = st.number_input("Max Users", min_value=1, value=1)
                    
                    if st.form_submit_button("Add Break Slot"):
                        if break_name:
                            try:
                                # Validate time formats
                                datetime.strptime(start_time, "%H:%M")
                                datetime.strptime(end_time, "%H:%M")
                                add_break_slot(
                                    break_name,
                                    start_time,
                                    end_time,
                                    max_users,
                                    st.session_state.username
                                )
                                st.success("Break slot added successfully!")
                                st.rerun()
                            except ValueError:
                                st.error("Invalid time format. Please use HH:MM format (e.g., 08:30)")
            
            st.subheader("Current Break Schedule")
            breaks = get_all_break_slots()
            
            # Initialize break_edits if not exists
            if "break_edits" not in st.session_state:
                st.session_state.break_edits = {}
            
            # Store current edits
            for b in breaks:
                b_id, name, start, end, max_u, curr_u, created_by, ts = b
                if b_id not in st.session_state.break_edits:
                    st.session_state.break_edits[b_id] = {
                        "break_name": name,
                        "start_time": start,
                        "end_time": end,
                        "max_users": max_u
                    }
            
            # Display editable breaks
            for b in breaks:
                b_id, name, start, end, max_u, curr_u, created_by, ts = b
                with st.container():
                    st.markdown(f"<div class='editable-break'>", unsafe_allow_html=True)
                    
                    cols = st.columns([3, 2, 2, 1, 1])
                    with cols[0]:
                        st.session_state.break_edits[b_id]["break_name"] = st.text_input(
                            "Break Name", 
                            value=st.session_state.break_edits[b_id]["break_name"],
                            key=f"name_{b_id}"
                        )
                    with cols[1]:
                        st.session_state.break_edits[b_id]["start_time"] = st.text_input(
                            "Start Time (HH:MM)", 
                            value=st.session_state.break_edits[b_id]["start_time"],
                            key=f"start_{b_id}"
                        )
                    with cols[2]:
                        st.session_state.break_edits[b_id]["end_time"] = st.text_input(
                            "End Time (HH:MM)", 
                            value=st.session_state.break_edits[b_id]["end_time"],
                            key=f"end_{b_id}"
                        )
                    with cols[3]:
                        st.session_state.break_edits[b_id]["max_users"] = st.number_input(
                            "Max Users", 
                            min_value=1,
                            value=st.session_state.break_edits[b_id]["max_users"],
                            key=f"max_{b_id}"
                        )
                    with cols[4]:
                        if st.button("❌", key=f"del_{b_id}"):
                            delete_break_slot(b_id)
                            st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
            
            # Single save button for all changes
            if st.button("💾 Save All Changes"):
                errors = []
                for b_id, edits in st.session_state.break_edits.items():
                    try:
                        # Validate time format
                        datetime.strptime(edits["start_time"], "%H:%M")
                        datetime.strptime(edits["end_time"], "%H:%M")
                        update_break_slot(
                            b_id,
                            edits["break_name"],
                            edits["start_time"],
                            edits["end_time"],
                            edits["max_users"]
                        )
                    except ValueError as e:
                        errors.append(f"Break ID {b_id}: Invalid time format. Please use HH:MM format.")
                        continue
                
                if errors:
                    for error in errors:
                        st.error(error)
                else:
                    st.success("All changes saved successfully!")
                    st.rerun()
            
            st.markdown("---")
            st.subheader("All Bookings for Selected Date")
            try:
                bookings = get_all_bookings(formatted_date)
                if bookings:
                    for b in bookings:
                        b_id, break_id, user_id, username, date, ts, break_name, start, end, role = b
                        st.write(f"{username} ({role}) - {break_name} ({start} - {end})")
                else:
                    st.info("No bookings for selected date")
            except Exception as e:
                st.error(f"Error loading bookings: {str(e)}")
            
            if st.button("Clear All Bookings", key="clear_all_bookings"):
                clear_all_break_bookings()
                st.rerun()
        
        else:
            st.subheader("Available Break Slots")
            try:
                available_breaks = get_available_break_slots(formatted_date)
                
                if available_breaks:
                    for b in available_breaks:
                        b_id, name, start, end, max_u, curr_u, created_by, ts = b
                        
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                SELECT COUNT(*) 
                                FROM break_bookings 
                                WHERE break_id = ? AND booking_date = ?
                            """, (b_id, formatted_date))
                            booked_count = cursor.fetchone()[0]
                            remaining = max_u - booked_count
                        except Exception as e:
                            st.error(f"Error checking availability: {str(e)}")
                            continue
                        finally:
                            conn.close()
                        
                        with st.container():
                            cols = st.columns([3, 2, 1])
                            cols[0].write(f"*{name}* ({start} - {end})")
                            cols[1].write(f"Available slots: {remaining}/{max_u}")
                            
                            if cols[2].button("Book", key=f"book_{b_id}"):
                                try:
                                    conn = get_db_connection()
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT id FROM users WHERE username = ?", 
                                                (st.session_state.username,))
                                    user_id = cursor.fetchone()[0]
                                    book_break_slot(b_id, user_id, st.session_state.username, formatted_date)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error booking slot: {str(e)}")
                                finally:
                                    conn.close()
            except Exception as e:
                st.error(f"Error loading break slots: {str(e)}")
            
            st.markdown("---")
            st.subheader("Your Bookings")
            try:
                user_bookings = get_user_bookings(st.session_state.username, formatted_date)
                
                if user_bookings:
                    for b in user_bookings:
                        b_id, break_id, user_id, username, date, ts, break_name, start, end = b
                        st.write(f"{break_name} ({start} - {end})")
                else:
                    st.info("You have no bookings for selected date")
            except Exception as e:
                st.error(f"Error loading your bookings: {str(e)}")

    elif st.session_state.current_section == "mistakes":
        if not is_killswitch_enabled():
            with st.expander("➕ Report New Mistake"):
                with st.form("mistake_form"):
                    cols = st.columns(3)
                    agent_name = cols[0].text_input("Agent Name")
                    ticket_id = cols[1].text_input("Ticket ID")
                    error_description = st.text_area("Error Description")
                    if st.form_submit_button("Submit"):
                        if agent_name and ticket_id and error_description:
                            add_mistake(st.session_state.username, agent_name, ticket_id, error_description)
        
        st.subheader("🔍 Search Mistakes")
        search_query = st.text_input("Search mistakes...")
        mistakes = search_mistakes(search_query) if search_query else get_mistakes()
        
        st.subheader("Mistakes Log")
        for mistake in mistakes:
            m_id, tl, agent, ticket, error, ts = mistake
            st.markdown(f"""
            <div class="card">
                <div style="display: flex; justify-content: space-between;">
                    <h4>#{m_id}</h4>
                    <small>{ts}</small>
                </div>
                <p>Agent: {agent}</p>
                <p>Ticket: {ticket}</p>
                <p>Error: {error}</p>
            </div>
            """, unsafe_allow_html=True)

    elif st.session_state.current_section == "chat":
        if is_chat_killswitch_enabled():
            st.warning("Chat functionality is currently disabled by the administrator.")
        else:
            messages = get_group_messages()
            for msg in reversed(messages):
                msg_id, sender, message, ts, mentions = msg
                is_mentioned = st.session_state.username in (mentions.split(',') if mentions else [])
                st.markdown(f"""
                <div style="background-color: {'#3b82f6' if is_mentioned else '#1F1F1F'};
                            padding: 1rem;
                            border-radius: 8px;
                            margin-bottom: 1rem;">
                    <strong>{sender}</strong>: {message}<br>
                    <small>{ts}</small>
                </div>
                """, unsafe_allow_html=True)
            
            if not is_killswitch_enabled():
                with st.form("chat_form"):
                    message = st.text_input("Type your message...")
                    if st.form_submit_button("Send"):
                        if message:
                            send_group_message(st.session_state.username, message)
                            st.rerun()

    elif st.session_state.current_section == "hold":
        if st.session_state.role == "admin" and not is_killswitch_enabled():
            with st.expander("📤 Upload Image"):
                img = st.file_uploader("Choose image", type=["jpg", "png", "jpeg"])
                if img:
                    add_hold_image(st.session_state.username, img.read())
        
        images = get_hold_images()
        if images:
            for img in images:
                iid, uploader, data, ts = img
                st.markdown(f"""
                <div class="card">
                    <div style="display: flex; justify-content: space-between;">
                        <h4>Image #{iid}</h4>
                        <small>{ts}</small>
                    </div>
                    <p>Uploaded by: {uploader}</p>
                </div>
                """, unsafe_allow_html=True)
                st.image(Image.open(io.BytesIO(data)), use_container_width=True)
        else:
            st.info("No images in HOLD")

    elif st.session_state.current_section == "fancy_number":
        st.header("📱 Lycamobile Fancy Number Checker")
        st.subheader("Official Policy: Analyzes last 6 digits only for qualifying patterns")

        phone_input = st.text_input("Enter Phone Number", 
                                  placeholder="e.g., 1555123456 or 44207123456")

        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🔍 Check Number"):
                if not phone_input:
                    st.warning("Please enter a phone number")
                else:
                    is_fancy, pattern = is_fancy_number(phone_input)
                    clean_number = re.sub(r'\D', '', phone_input)
                    
                    # Extract last 6 digits for display
                    last_six = clean_number[-6:] if len(clean_number) >= 6 else clean_number
                    formatted_num = f"{last_six[:3]}-{last_six[3:]}" if len(last_six) == 6 else last_six

                    if is_fancy:
                        st.markdown(f"""
                        <div class="result-box fancy-result">
                            <h3><span class="fancy-number">✨ {formatted_num} ✨</span></h3>
                            <p>FANCY NUMBER DETECTED!</p>
                            <p><strong>Pattern:</strong> {pattern}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="result-box normal-result">
                            <h3><span class="normal-number">{formatted_num}</span></h3>
                            <p>Standard phone number</p>
                            <p><strong>Reason:</strong> {pattern}</p>
                        </div>
                        """, unsafe_allow_html=True)

        with col2:
            st.markdown("""
            ### Lycamobile Fancy Number Policy
            **Qualifying Patterns (last 6 digits only):**
            
            #### 6-Digit Patterns
            - 123456 (ascending)
            - 987654 (descending)
            - 666666 (repeating)
            - 100001 (palindrome)
            
            #### 3-Digit Patterns  
            - 444 555 (double triplets)
            - 121 122 (similar triplets)
            - 786 786 (repeating triplets)
            - 457 456 (nearly sequential)
            
            #### 2-Digit Patterns
            - 11 12 13 (incremental)
            - 20 20 20 (repeating)
            - 01 01 01 (alternating)
            - 32 42 52 (stepping)
            
            #### Exceptional Cases
            - Ending with 123/555/777/999
            """)

        # Test cases
        debug_mode = st.checkbox("Show test cases", False)
        if debug_mode:
            test_numbers = [
                ("16109055580", False),  # 055580 → No pattern ✗
                ("123456", True),       # 6-digit ascending ✓
                ("444555", True),       # Double triplets ✓
                ("121122", True),       # Similar triplets ✓ 
                ("111213", True),       # Incremental pairs ✓
                ("202020", True),       # Repeating pairs ✓
                ("010101", True),       # Alternating pairs ✓
                ("324252", True),       # Stepping pairs ✓
                ("7900000123", True),   # Ends with 123 ✓
                ("123458", False),      # No pattern ✗
                ("112233", False),      # Not in our strict rules ✗
                ("555555", True)        # 6 identical digits ✓
            ]
            
            st.markdown("### Strict Policy Validation")
            for number, expected in test_numbers:
                is_fancy, pattern = is_fancy_number(number)
                result = "PASS" if is_fancy == expected else "FAIL"
                color = "green" if result == "PASS" else "red"
                st.write(f"<span style='color:{color}'>{number[-6:]}: {result} ({pattern})</span>", unsafe_allow_html=True)

    elif st.session_state.current_section == "late_login":
        st.subheader("⏰ Late Login Report")
        
        if not is_killswitch_enabled():
            with st.form("late_login_form"):
                cols = st.columns(3)
                presence_time = cols[0].text_input("Time of presence (HH:MM)", placeholder="08:30")
                login_time = cols[1].text_input("Time of log in (HH:MM)", placeholder="09:15")
                reason = cols[2].selectbox("Reason", [
                    "Workspace Issue",
                    "Avaya Issue",
                    "Aaad Tool",
                    "Windows Issue",
                    "Reset Password"
                ])
                
                if st.form_submit_button("Submit"):
                    # Validate time formats
                    try:
                        datetime.strptime(presence_time, "%H:%M")
                        datetime.strptime(login_time, "%H:%M")
                        add_late_login(
                            st.session_state.username,
                            presence_time,
                            login_time,
                            reason
                        )
                        st.success("Late login reported successfully!")
                    except ValueError:
                        st.error("Invalid time format. Please use HH:MM format (e.g., 08:30)")
        
        st.subheader("Late Login Records")
        late_logins = get_late_logins()
        
        if st.session_state.role == "admin":
            if late_logins:
                # Prepare data for download
                data = []
                for login in late_logins:
                    _, agent, presence, login_time, reason, ts = login
                    data.append({
                        "Agent's Name": agent,
                        "Time of presence": presence,
                        "Time of log in": login_time,
                        "Reason": reason
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                # Download button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name="late_logins.csv",
                    mime="text/csv"
                )
                
                if st.button("Clear All Records"):
                    clear_late_logins()
                    st.rerun()
            else:
                st.info("No late login records found")
        else:
            # For agents, only show their own records
            user_logins = [login for login in late_logins if login[1] == st.session_state.username]
            if user_logins:
                data = []
                for login in user_logins:
                    _, agent, presence, login_time, reason, ts = login
                    data.append({
                        "Agent's Name": agent,
                        "Time of presence": presence,
                        "Time of log in": login_time,
                        "Reason": reason
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("You have no late login records")

    elif st.session_state.current_section == "quality_issues":
        st.subheader("📞 Quality Related Technical Issue")
        
        if not is_killswitch_enabled():
            with st.form("quality_issue_form"):
                cols = st.columns(4)
                issue_type = cols[0].selectbox("Type of issue", [
                    "Blocage Physical Avaya",
                    "Hold Than Call Drop",
                    "Call Drop From Workspace",
                    "Wrong Space Frozen"
                ])
                timing = cols[1].text_input("Timing (HH:MM)", placeholder="14:30")
                mobile_number = cols[2].text_input("Mobile number")
                product = cols[3].selectbox("Product", [
                    "LM_CS_LMUSA_EN",
                    "LM_CS_LMUSA_ES"
                ])
                
                if st.form_submit_button("Submit"):
                    try:
                        datetime.strptime(timing, "%H:%M")
                        add_quality_issue(
                            st.session_state.username,
                            issue_type,
                            timing,
                            mobile_number,
                            product
                        )
                        st.success("Quality issue reported successfully!")
                    except ValueError:
                        st.error("Invalid time format. Please use HH:MM format (e.g., 14:30)")
        
        st.subheader("Quality Issue Records")
        quality_issues = get_quality_issues()
        
        if st.session_state.role == "admin":
            if quality_issues:
                # Prepare data for download
                data = []
                for issue in quality_issues:
                    _, agent, issue_type, timing, mobile, product, ts = issue
                    data.append({
                        "Agent's Name": agent,
                        "Type of issue": issue_type,
                        "Timing": timing,
                        "Mobile number": mobile,
                        "Product": product
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                # Download button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name="quality_issues.csv",
                    mime="text/csv"
                )
                
                if st.button("Clear All Records"):
                    clear_quality_issues()
                    st.rerun()
            else:
                st.info("No quality issue records found")
        else:
            # For agents, only show their own records
            user_issues = [issue for issue in quality_issues if issue[1] == st.session_state.username]
            if user_issues:
                data = []
                for issue in user_issues:
                    _, agent, issue_type, timing, mobile, product, ts = issue
                    data.append({
                        "Agent's Name": agent,
                        "Type of issue": issue_type,
                        "Timing": timing,
                        "Mobile number": mobile,
                        "Product": product
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("You have no quality issue records")

    elif st.session_state.current_section == "midshift_issues":
        st.subheader("🔄 Mid-shift Technical Issue")
        
        if not is_killswitch_enabled():
            with st.form("midshift_issue_form"):
                cols = st.columns(3)
                issue_type = cols[0].selectbox("Issue Type", [
                    "Default Not Ready",
                    "Frozen Workspace",
                    "Physical Avaya",
                    "Pc Issue",
                    "Aaad Tool",
                    "Disconnected Avaya"
                ])
                start_time = cols[1].text_input("Start time (HH:MM)", placeholder="10:00")
                end_time = cols[2].text_input("End time (HH:MM)", placeholder="10:30")
                
                if st.form_submit_button("Submit"):
                    try:
                        datetime.strptime(start_time, "%H:%M")
                        datetime.strptime(end_time, "%H:%M")
                        add_midshift_issue(
                            st.session_state.username,
                            issue_type,
                            start_time,
                            end_time
                        )
                        st.success("Mid-shift issue reported successfully!")
                    except ValueError:
                        st.error("Invalid time format. Please use HH:MM format (e.g., 10:00)")
        
        st.subheader("Mid-shift Issue Records")
        midshift_issues = get_midshift_issues()
        
        if st.session_state.role == "admin":
            if midshift_issues:
                # Prepare data for download
                data = []
                for issue in midshift_issues:
                    _, agent, issue_type, start_time, end_time, ts = issue
                    data.append({
                        "Agent's Name": agent,
                        "Issue Type": issue_type,
                        "Start time": start_time,
                        "End Time": end_time
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                # Download button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name="midshift_issues.csv",
                    mime="text/csv"
                )
                
                if st.button("Clear All Records"):
                    clear_midshift_issues()
                    st.rerun()
            else:
                st.info("No mid-shift issue records found")
        else:
            # For agents, only show their own records
            user_issues = [issue for issue in midshift_issues if issue[1] == st.session_state.username]
            if user_issues:
                data = []
                for issue in user_issues:
                    _, agent, issue_type, start_time, end_time, ts = issue
                    data.append({
                        "Agent's Name": agent,
                        "Issue Type": issue_type,
                        "Start time": start_time,
                        "End Time": end_time
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("You have no mid-shift issue records")

    elif st.session_state.current_section == "admin" and st.session_state.role == "admin":
        if st.session_state.username.lower() == "taha kirri":
            st.subheader("🚨 System Killswitch")
            current = is_killswitch_enabled()
            status = "🔴 ACTIVE" if current else "🟢 INACTIVE"
            st.write(f"Current Status: {status}")
            
            col1, col2 = st.columns(2)
            if current:
                if col1.button("Deactivate Killswitch"):
                    toggle_killswitch(False)
                    st.rerun()
            else:
                if col1.button("Activate Killswitch"):
                    toggle_killswitch(True)
                    st.rerun()
            
            st.markdown("---")
            
            st.subheader("💬 Chat Killswitch")
            current_chat = is_chat_killswitch_enabled()
            chat_status = "🔴 ACTIVE" if current_chat else "🟢 INACTIVE"
            st.write(f"Current Status: {chat_status}")
            
            col1, col2 = st.columns(2)
            if current_chat:
                if col1.button("Deactivate Chat Killswitch"):
                    toggle_chat_killswitch(False)
                    st.rerun()
            else:
                if col1.button("Activate Chat Killswitch"):
                    toggle_chat_killswitch(True)
                    st.rerun()
            
            st.markdown("---")
        
        st.subheader("🧹 Data Management")
        
        with st.expander("❌ Clear All Requests"):
            with st.form("clear_requests_form"):
                st.warning("This will permanently delete ALL requests and their comments!")
                if st.form_submit_button("Clear All Requests"):
                    if clear_all_requests():
                        st.success("All requests deleted!")
                        st.rerun()

        with st.expander("❌ Clear All Mistakes"):
            with st.form("clear_mistakes_form"):
                st.warning("This will permanently delete ALL mistakes!")
                if st.form_submit_button("Clear All Mistakes"):
                    if clear_all_mistakes():
                        st.success("All mistakes deleted!")
                        st.rerun()

        with st.expander("❌ Clear All Chat Messages"):
            with st.form("clear_chat_form"):
                st.warning("This will permanently delete ALL chat messages!")
                if st.form_submit_button("Clear All Chat"):
                    if clear_all_group_messages():
                        st.success("All chat messages deleted!")
                        st.rerun()

        with st.expander("❌ Clear All HOLD Images"):
            with st.form("clear_hold_form"):
                st.warning("This will permanently delete ALL HOLD images!")
                if st.form_submit_button("Clear All HOLD Images"):
                    if clear_hold_images():
                        st.success("All HOLD images deleted!")
                        st.rerun()

        with st.expander("❌ Clear All Break Bookings"):
            with st.form("clear_breaks_form"):
                st.warning("This will permanently delete ALL break bookings!")
                if st.form_submit_button("Clear All Break Bookings"):
                    if clear_all_break_bookings():
                        st.success("All break bookings deleted!")
                        st.rerun()

        with st.expander("❌ Clear All Late Logins"):
            with st.form("clear_late_logins_form"):
                st.warning("This will permanently delete ALL late login records!")
                if st.form_submit_button("Clear All Late Logins"):
                    if clear_late_logins():
                        st.success("All late login records deleted!")
                        st.rerun()

        with st.expander("❌ Clear All Quality Issues"):
            with st.form("clear_quality_issues_form"):
                st.warning("This will permanently delete ALL quality issue records!")
                if st.form_submit_button("Clear All Quality Issues"):
                    if clear_quality_issues():
                        st.success("All quality issue records deleted!")
                        st.rerun()

        with st.expander("❌ Clear All Mid-shift Issues"):
            with st.form("clear_midshift_issues_form"):
                st.warning("This will permanently delete ALL mid-shift issue records!")
                if st.form_submit_button("Clear All Mid-shift Issues"):
                    if clear_midshift_issues():
                        st.success("All mid-shift issue records deleted!")
                        st.rerun()

        with st.expander("💣 Clear ALL Data"):
            with st.form("nuclear_form"):
                st.error("THIS WILL DELETE EVERYTHING IN THE SYSTEM!")
                if st.form_submit_button("🚨 Execute Full System Wipe"):
                    try:
                        clear_all_requests()
                        clear_all_mistakes()
                        clear_all_group_messages()
                        clear_hold_images()
                        clear_all_break_bookings()
                        clear_late_logins()
                        clear_quality_issues()
                        clear_midshift_issues()
                        st.success("All system data deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error during deletion: {str(e)}")
        
        st.markdown("---")
        st.subheader("User Management")
        if not is_killswitch_enabled():
            with st.form("add_user"):
                user = st.text_input("Username")
                pwd = st.text_input("Password", type="password")
                role = st.selectbox("Role", ["agent", "admin"])
                if st.form_submit_button("Add User"):
                    if user and pwd:
                        add_user(user, pwd, role)
                        st.rerun()
        
        st.subheader("Existing Users")
        users = get_all_users()
        for uid, uname, urole in users:
            cols = st.columns([3, 1, 1])
            cols[0].write(uname)
            cols[1].write(urole)
            if cols[2].button("Delete", key=f"del_{uid}") and not is_killswitch_enabled():
                delete_user(uid)
                st.rerun()

if __name__ == "__main__":
    st.write("Request Management System")
