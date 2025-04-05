import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, time, timedelta
import os
import re
from PIL import Image
import io
import pandas as pd
import time as systime
from threading import Thread

# --------------------------
# Database Functions
# --------------------------
def get_db_connection():
    """Create and return a database connection."""
         os.makedirs("data", exist_ok=True)
           conn = None
            try:
        conn = sqlite3.connect(
            "data/requests.db",
            timeout=10,  # Add timeout
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None  # Add autocommit mode
        )
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection failed: {e}")
        if conn:
            conn.close()
        raise
      
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
                role TEXT CHECK(role IN ('agent', 'admin')),
                product TEXT DEFAULT NULL)
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
                conn.commit()
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            
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
        
        # Enhanced breaks table with product association
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                break_name TEXT,
                start_time TEXT,
                end_time TEXT,
                max_users INTEGER,
                current_users INTEGER DEFAULT 0,
                product TEXT DEFAULT NULL,
                created_by TEXT,
                timestamp TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS break_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                break_id INTEGER,
                user_id INTEGER,
                username TEXT,
                product TEXT,
                booking_date TEXT,
                timestamp TEXT,
                notified INTEGER DEFAULT 0,
                FOREIGN KEY(break_id) REFERENCES breaks(id))
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS break_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER,
                user_id INTEGER,
                break_time TEXT,
                notified_time TEXT,
                FOREIGN KEY(booking_id) REFERENCES break_bookings(id))
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

        # Create default break slots if none exist
        cursor.execute("SELECT COUNT(*) FROM breaks")
        if cursor.fetchone()[0] == 0:
            default_breaks = [
                ("LUNCH BREAK", "19:00", "19:30", 10, "LM_CS_LMUSA_EN", "System"),
                ("LUNCH BREAK", "19:30", "20:00", 10, "LM_CS_LMUSA_EN", "System"),
                ("LUNCH BREAK", "20:00", "20:30", 10, "LM_CS_LMUSA_ES", "System"),
                ("LUNCH BREAK", "20:30", "21:00", 10, "LM_CS_LMUSA_ES", "System"),
                ("LUNCH BREAK", "21:00", "21:30", 10, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "16:00", "16:15", 5, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "16:15", "16:30", 5, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "16:30", "16:45", 5, "LM_CS_LMUSA_ES", "System"),
                ("TEA BREAK", "16:45", "17:00", 5, "LM_CS_LMUSA_ES", "System"),
                ("TEA BREAK", "17:00", "17:15", 5, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "17:15", "17:30", 5, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "21:30", "21:45", 5, "LM_CS_LMUSA_ES", "System"),
                ("TEA BREAK", "21:45", "22:00", 5, "LM_CS_LMUSA_ES", "System"),
                ("TEA BREAK", "22:00", "22:15", 5, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "22:15", "22:30", 5, "LM_CS_LMUSA_EN", "System"),
                ("TEA BREAK", "22:30", "22:45", 5, "LM_CS_LMUSA_ES", "System")
            ]
            for break_name, start, end, max_users, product, creator in default_breaks:
                cursor.execute("""
                    INSERT INTO breaks (break_name, start_time, end_time, max_users, product, created_by, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (break_name, start, end, max_users, product, creator, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # Create agent accounts (agent name as username, workspace ID as password)
        agents = [
            ("Karabila Younes", "30866", "LM_CS_LMUSA_EN"),
            ("Kaoutar Mzara", "30514", "LM_CS_LMUSA_ES"),
            ("Ben Tahar Chahid", "30864", "LM_CS_LMUSA_EN"),
            ("Cherbassi Khadija", "30868", "LM_CS_LMUSA_ES"),
            ("Lekhmouchi Kamal", "30869", "LM_CS_LMUSA_EN"),
            ("Said Kilani", "30626", "LM_CS_LMUSA_ES"),
            ("AGLIF Rachid", "30830", "LM_CS_LMUSA_EN"),
            ("Yacine Adouha", "30577", "LM_CS_LMUSA_ES"),
            ("Manal Elanbi", "30878", "LM_CS_LMUSA_EN"),
            ("Jawad Ouassaddine", "30559", "LM_CS_LMUSA_ES"),
            ("Kamal Elhaouar", "30844", "LM_CS_LMUSA_EN"),
            ("Hoummad Oubella", "30702", "LM_CS_LMUSA_ES"),
            ("Zouheir Essafi", "30703", "LM_CS_LMUSA_EN"),
            ("Anwar Atifi", "30781", "LM_CS_LMUSA_ES"),
            ("Said Elgaouzi", "30782", "LM_CS_LMUSA_EN"),
            ("HAMZA SAOUI", "30716", "LM_CS_LMUSA_ES"),
            ("Ibtissam Mazhari", "30970", "LM_CS_LMUSA_EN"),
            ("Imad Ghazali", "30971", "LM_CS_LMUSA_ES"),
            ("Jamila Lahrech", "30972", "LM_CS_LMUSA_EN"),
            ("Nassim Ouazzani Touhami", "30973", "LM_CS_LMUSA_ES"),
            ("Salaheddine Chaggour", "30974", "LM_CS_LMUSA_EN"),
            ("Omar Tajani", "30711", "LM_CS_LMUSA_ES"),
            ("Nizar Remz", "30728", "LM_CS_LMUSA_EN"),
            ("Abdelouahed Fettah", "30693", "LM_CS_LMUSA_ES"),
            ("Amal Bouramdane", "30675", "LM_CS_LMUSA_EN"),
            ("Fatima Ezzahrae Oubaalla", "30513", "LM_CS_LMUSA_ES"),
            ("Redouane Bertal", "30643", "LM_CS_LMUSA_EN"),
            ("Abdelouahab Chenani", "30789", "LM_CS_LMUSA_ES"),
            ("Imad El Youbi", "30797", "LM_CS_LMUSA_EN"),
            ("Youssef Hammouda", "30791", "LM_CS_LMUSA_ES"),
            ("Anas Ouassifi", "30894", "LM_CS_LMUSA_EN"),
            ("SALSABIL ELMOUSS", "30723", "LM_CS_LMUSA_ES"),
            ("Hicham Khalafa", "30712", "LM_CS_LMUSA_EN"),
            ("Ghita Adib", "30710", "LM_CS_LMUSA_ES"),
            ("Aymane Msikila", "30722", "LM_CS_LMUSA_EN"),
            ("Marouane Boukhadda", "30890", "LM_CS_LMUSA_ES"),
            ("Hamid Boulatouan", "30899", "LM_CS_LMUSA_EN"),
            ("Bouchaib Chafiqi", "30895", "LM_CS_LMUSA_ES"),
            ("Houssam Gouaalla", "30891", "LM_CS_LMUSA_EN"),
            ("Abdellah Rguig", "30963", "LM_CS_LMUSA_ES"),
            ("Abdellatif Chatir", "30964", "LM_CS_LMUSA_EN"),
            ("Abderrahman Oueto", "30965", "LM_CS_LMUSA_ES"),
            ("Fatiha Lkamel", "30967", "LM_CS_LMUSA_EN"),
            ("Abdelhamid Jaber", "30708", "LM_CS_LMUSA_ES"),
            ("Yassine Elkanouni", "30735", "LM_CS_LMUSA_EN")
        ]
        
        for agent_name, workspace_id, product in agents:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, role, product) 
                VALUES (?, ?, ?, ?)
            """, (agent_name, hash_password(workspace_id), "agent", product))
        
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

def upload_break_schedule(file):
    try:
        if file.name.endswith('.xlsx'):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)
        
        required_cols = ["break_name", "start_time", "end_time", "max_users", "product"]
        if not all(col in df.columns for col in required_cols):
            return False, "Missing required columns in the file"
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Clear existing breaks
            cursor.execute("DELETE FROM breaks")
            
            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO breaks (break_name, start_time, end_time, max_users, product, created_by, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['break_name'],
                    row['start_time'],
                    row['end_time'],
                    row['max_users'],
                    row['product'],
                    "Excel Upload",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
            
            conn.commit()
            return True, "Break schedule uploaded successfully"
        finally:
            conn.close()
    except Exception as e:
        return False, f"Error processing file: {str(e)}"

def check_and_send_reminders():
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                # Get all bookings for today that haven't been notified yet
                cursor.execute("""
                    SELECT bb.id, bb.user_id, b.start_time 
                    FROM break_bookings bb
                    JOIN breaks b ON bb.break_id = b.id
                    WHERE bb.booking_date = ? AND bb.notified = 0
                """, (current_date,))
                
                bookings = cursor.fetchall()
                
                for booking_id, user_id, break_time in bookings:
                    try:
                        # Calculate reminder time (5 minutes before break)
                        break_dt = datetime.strptime(f"{current_date} {break_time}", "%Y-%m-%d %H:%M")
                        reminder_time = (break_dt - timedelta(minutes=5)).strftime("%H:%M")
                        
                        if current_time >= reminder_time:
                            # Mark as notified
                            cursor.execute("""
                                UPDATE break_bookings SET notified = 1 WHERE id = ?
                            """, (booking_id,))
                            
                            # Log the reminder
                            cursor.execute("""
                                INSERT INTO break_reminders (booking_id, user_id, break_time, notified_time)
                                VALUES (?, ?, ?, ?)
                            """, (booking_id, user_id, break_time, current_time))
                            
                            conn.commit()
                    except Exception as e:
                        print(f"Error processing reminder for booking {booking_id}: {str(e)}")
                        continue
            finally:
                conn.close()
        except Exception as e:
            print(f"Error in reminder service: {str(e)}")
        
        # Check every minute
        systime.sleep(60)

# Start the reminder thread when the module loads
reminder_thread = Thread(target=check_and_send_reminders, daemon=True)
reminder_thread.start()

def get_user_product(username):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None
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
    /* Break Slots Styling */
    .break-container {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 20px;
    }
    .break-card {
        background-color: #2D3748;
        border-radius: 10px;
        padding: 15px;
        width: calc(33% - 10px);
        min-width: 250px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: transform 0.2s;
    }
    .break-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    .break-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .break-title {
        font-weight: bold;
        font-size: 1.1rem;
        color: #E2E8F0;
    }
    .break-time {
        font-size: 0.9rem;
        color: #A0AEC0;
    }
    .break-details {
        display: flex;
        justify-content: space-between;
        margin-top: 10px;
    }
    .break-availability {
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .break-available {
        color: #48BB78;
        font-weight: bold;
    }
    .break-full {
        color: #F56565;
        font-weight: bold;
    }
    .break-button {
        width: 100%;
        margin-top: 10px;
    }
    .break-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .lunch-tag {
        background-color: #2C5282;
        color: #BEE3F8;
    }
    .tea-tag {
        background-color: #553C9A;
        color: #E9D8FD;
    }
    .break-section {
        margin-bottom: 30px;
    }
    .break-section-title {
        font-size: 1.3rem;
        margin-bottom: 15px;
        color: #E2E8F0;
        border-bottom: 1px solid #4A5568;
        padding-bottom: 8px;
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
            
            with st.expander("📤 Upload Break Schedule (Excel/CSV)"):
                uploaded_file = st.file_uploader("Upload Break Schedule", type=["xlsx", "csv"])
                if uploaded_file:
                    success, message = upload_break_schedule(uploaded_file)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                
                st.download_button(
                    label="Download Template",
                    data=pd.DataFrame(columns=["break_name", "start_time", "end_time", "max_users", "product"]).to_csv(index=False),
                    file_name="break_schedule_template.csv",
                    mime="text/csv"
                )
            
            with st.expander("➕ Add New Break Slot"):
                with st.form("add_break_form"):
                    cols = st.columns(3)
                    break_name = cols[0].selectbox("Break Name", ["LUNCH BREAK", "TEA BREAK"])
                    start_time = cols[1].text_input("Start Time (HH:MM)")
                    end_time = cols[2].text_input("End Time (HH:MM)")
                    max_users = st.number_input("Max Users", min_value=1, value=5)
                    product = st.selectbox("Product", ["LM_CS_LMUSA_EN", "LM_CS_LMUSA_ES", None], 
                                          format_func=lambda x: "All Products" if x is None else x)
                    
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
                                    product,
                                    st.session_state.username
                                )
                                st.success("Break slot added successfully!")
                                st.rerun()
                            except ValueError:
                                st.error("Invalid time format. Please use HH:MM format (e.g., 08:30)")
            
            st.subheader("Current Break Schedule")
            breaks = get_all_break_slots()
            
            # Group breaks by type and product
            lunch_breaks = [b for b in breaks if b[1] == "LUNCH BREAK"]
            tea_breaks = [b for b in breaks if b[1] == "TEA BREAK"]
            
            # Display Lunch Breaks
            st.markdown('<div class="break-section">', unsafe_allow_html=True)
            st.markdown('<div class="break-section-title">🍽️ LUNCH BREAKS</div>', unsafe_allow_html=True)
            
            # Group by product
            lunch_by_product = {}
            for b in lunch_breaks:
                product = b[5] if b[5] else "All Products"
                if product not in lunch_by_product:
                    lunch_by_product[product] = []
                lunch_by_product[product].append(b)
            
            for product, product_breaks in lunch_by_product.items():
                st.markdown(f'<div style="margin-left: 20px; margin-bottom: 10px;"><strong>Product: {product}</strong></div>', unsafe_allow_html=True)
                st.markdown('<div class="break-container">', unsafe_allow_html=True)
                
                for break_slot in product_breaks:
                    b_id, name, start, end, max_u, curr_u, product, created_by, ts = break_slot
                    
                    # Get booking count for this date
                    conn = get_db_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM break_bookings 
                            WHERE break_id = ? AND booking_date = ?
                        """, (b_id, formatted_date))
                        booked_count = cursor.fetchone()[0]
                        remaining = max_u - booked_count
                        is_available = remaining > 0
                    except Exception as e:
                        st.error(f"Error checking availability: {str(e)}")
                        continue
                    finally:
                        conn.close()
                    
                    st.markdown(f"""
                    <div class="break-card">
                        <div class="break-header">
                            <div class="break-title">Lunch Break</div>
                            <span class="break-tag lunch-tag">Lunch</span>
                        </div>
                        <div class="break-time">{start} - {end}</div>
                        <div class="break-details">
                            <div class="break-availability">
                                <span>Available:</span>
                                <span class="{'break-available' if is_available else 'break-full'}">{remaining}/{max_u}</span>
                            </div>
                            <div>Product: {product if product else 'All'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Display Tea Breaks
            st.markdown('<div class="break-section">', unsafe_allow_html=True)
            st.markdown('<div class="break-section-title">☕ TEA BREAKS</div>', unsafe_allow_html=True)
            
            # Group by product
            tea_by_product = {}
            for b in tea_breaks:
                product = b[5] if b[5] else "All Products"
                if product not in tea_by_product:
                    tea_by_product[product] = []
                tea_by_product[product].append(b)
            
            for product, product_breaks in tea_by_product.items():
                st.markdown(f'<div style="margin-left: 20px; margin-bottom: 10px;"><strong>Product: {product}</strong></div>', unsafe_allow_html=True)
                st.markdown('<div class="break-container">', unsafe_allow_html=True)
                
                for break_slot in product_breaks:
                    b_id, name, start, end, max_u, curr_u, product, created_by, ts = break_slot
                    
                    # Get booking count for this date
                    conn = get_db_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT COUNT(*) 
                            FROM break_bookings 
                            WHERE break_id = ? AND booking_date = ?
                        """, (b_id, formatted_date))
                        booked_count = cursor.fetchone()[0]
                        remaining = max_u - booked_count
                        is_available = remaining > 0
                    except Exception as e:
                        st.error(f"Error checking availability: {str(e)}")
                        continue
                    finally:
                        conn.close()
                    
                    st.markdown(f"""
                    <div class="break-card">
                        <div class="break-header">
                            <div class="break-title">Tea Break</div>
                            <span class="break-tag tea-tag">Tea</span>
                        </div>
                        <div class="break-time">{start} - {end}</div>
                        <div class="break-details">
                            <div class="break-availability">
                                <span>Available:</span>
                                <span class="{'break-available' if is_available else 'break-full'}">{remaining}/{max_u}</span>
                            </div>
                            <div>Product: {product if product else 'All'}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Initialize break_edits if not exists
            if "break_edits" not in st.session_state:
                st.session_state.break_edits = {}
            
            # Store current edits
            for b in breaks:
                b_id, name, start, end, max_u, curr_u, product, created_by, ts = b
                if b_id not in st.session_state.break_edits:
                    st.session_state.break_edits[b_id] = {
                        "break_name": name,
                        "start_time": start,
                        "end_time": end,
                        "max_users": max_u,
                        "product": product
                    }
            
            # Display editable breaks
            st.subheader("Edit Break Slots")
            for b in breaks:
                b_id, name, start, end, max_u, curr_u, product, created_by, ts = b
                with st.container():
                    st.markdown(f"<div class='editable-break'>", unsafe_allow_html=True)
                    
                    cols = st.columns([2, 2, 2, 1, 1, 1])
                    with cols[0]:
                        st.session_state.break_edits[b_id]["break_name"] = st.selectbox(
                            "Break Name", 
                            ["LUNCH BREAK", "TEA BREAK"],
                            index=0 if name == "LUNCH BREAK" else 1,
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
                        st.session_state.break_edits[b_id]["product"] = st.selectbox(
                            "Product",
                            ["LM_CS_LMUSA_EN", "LM_CS_LMUSA_ES", None],
                            index=0 if st.session_state.break_edits[b_id]["product"] == "LM_CS_LMUSA_EN" 
                                   else 1 if st.session_state.break_edits[b_id]["product"] == "LM_CS_LMUSA_ES" 
                                   else 2,
                            format_func=lambda x: "All Products" if x is None else x,
                            key=f"product_{b_id}"
                        )
                    with cols[5]:
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
                            edits["max_users"],
                            edits["product"]
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
                    df = pd.DataFrame([{
                        "Agent": b[3],
                        "Role": b[9],
                        "Break": b[7],
                        "Time": f"{b[8]} - {b[9]}",
                        "Product": b[4]
                    } for b in bookings])
                    st.dataframe(df)
                    
                    # Download button
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download as CSV",
                        data=csv,
                        file_name=f"break_bookings_{formatted_date}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No bookings for selected date")
            except Exception as e:
                st.error(f"Error loading bookings: {str(e)}")
            
            if st.button("Clear All Bookings", key="clear_all_bookings"):
                clear_all_break_bookings()
                st.rerun()
        
        else:
            # Agent view
            user_product = get_user_product(st.session_state.username)
            st.subheader(f"Available Break Slots for {user_product}")
            
            try:
                available_breaks = get_available_break_slots(formatted_date, user_product)
                
                # Group by break type
                lunch_breaks = [b for b in available_breaks if b[1] == "LUNCH BREAK"]
                tea_breaks = [b for b in available_breaks if b[1] == "TEA BREAK"]
                
                # Display Lunch Breaks
                st.markdown('<div class="break-section">', unsafe_allow_html=True)
                st.markdown('<div class="break-section-title">🍽️ LUNCH BREAKS</div>', unsafe_allow_html=True)
                st.markdown('<div class="break-container">', unsafe_allow_html=True)
                
                for break_slot in lunch_breaks:
                    b_id, name, start, end, max_u, curr_u, product, created_by, ts = break_slot
                    
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
                        is_available = remaining > 0
                    except Exception as e:
                        st.error(f"Error checking availability: {str(e)}")
                        continue
                    finally:
                        conn.close()
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="break-card">
                            <div class="break-header">
                                <div class="break-title">Lunch Break</div>
                                <span class="break-tag lunch-tag">Lunch</span>
                            </div>
                            <div class="break-time">{start} - {end}</div>
                            <div class="break-details">
                                <div class="break-availability">
                                    <span>Available:</span>
                                    <span class="{'break-available' if is_available else 'break-full'}">{remaining}/{max_u}</span>
                                </div>
                                <div>Product: {product if product else 'All'}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if is_available:
                            if st.button("Book Now", key=f"book_lunch_{b_id}"):
                                # Get user ID
                                conn = get_db_connection()
                                try:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT id FROM users WHERE username = ?", (st.session_state.username,))
                                    user_id = cursor.fetchone()[0]
                                    
                                    book_break_slot(
                                        b_id,
                                        user_id,
                                        st.session_state.username,
                                        user_product,
                                        formatted_date
                                    )
                                    st.success(f"Booked lunch break from {start} to {end}!")
                                    st.rerun()
                                finally:
                                    conn.close()
                
                st.markdown('</div></div>', unsafe_allow_html=True)
                
                # Display Tea Breaks
                st.markdown('<div class="break-section">', unsafe_allow_html=True)
                st.markdown('<div class="break-section-title">☕ TEA BREAKS</div>', unsafe_allow_html=True)
                st.markdown('<div class="break-container">', unsafe_allow_html=True)
                
                for break_slot in tea_breaks:
                    b_id, name, start, end, max_u, curr_u, product, created_by, ts = break_slot
                    
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
                        is_available = remaining > 0
                    except Exception as e:
                        st.error(f"Error checking availability: {str(e)}")
                        continue
                    finally:
                        conn.close()
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="break-card">
                            <div class="break-header">
                                <div class="break-title">Tea Break</div>
                                <span class="break-tag tea-tag">Tea</span>
                            </div>
                            <div class="break-time">{start} - {end}</div>
                            <div class="break-details">
                                <div class="break-availability">
                                    <span>Available:</span>
                                    <span class="{'break-available' if is_available else 'break-full'}">{remaining}/{max_u}</span>
                                </div>
                                <div>Product: {product if product else 'All'}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if is_available:
                            if st.button("Book Now", key=f"book_tea_{b_id}"):
                                # Get user ID
                                conn = get_db_connection()
                                try:
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT id FROM users WHERE username = ?", (st.session_state.username,))
                                    user_id = cursor.fetchone()[0]
                                    
                                    book_break_slot(
                                        b_id,
                                        user_id,
                                        st.session_state.username,
                                        user_product,
                                        formatted_date
                                    )
                                    st.success(f"Booked tea break from {start} to {end}!")
                                    st.rerun()
                                finally:
                                    conn.close()
                
                st.markdown('</div></div>', unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Error loading break slots: {str(e)}")
            
            st.markdown("---")
            st.subheader("Your Bookings")
            try:
                user_bookings = get_user_bookings(st.session_state.username, formatted_date)
                
                if user_bookings:
                    for b in user_bookings:
                        b_id, break_id, user_id, username, date, ts, break_name, start, end = b
                        st.markdown(f"""
                        <div class="card">
                            <div style="display: flex; justify-content: space-between;">
                                <h4>{break_name}</h4>
                                <small>{date}</small>
                            </div>
                            <p>Time: {start} - {end}</p>
                            <p>Status: Booked</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Check if break is within 5 minutes and show reminder
                        now = datetime.now()
                        break_time = datetime.strptime(f"{date} {start}", "%Y-%m-%d %H:%M")
                        time_diff = (break_time - now).total_seconds() / 60  # in minutes
                        
                        if 0 < time_diff <= 5:
                            st.warning(f"⏰ Your break starts soon at {start}!") 
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
