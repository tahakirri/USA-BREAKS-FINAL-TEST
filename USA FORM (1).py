import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, time, timedelta
import os
import re
from PIL import Image
import io
import pandas as pd
import json
import pytz

# --------------------------
# Timezone Utility Functions
# --------------------------

def get_casablanca_time():
    """Get current time in Casablanca, Morocco timezone"""
    morocco_tz = pytz.timezone('Africa/Casablanca')
    return datetime.now(morocco_tz).strftime("%Y-%m-%d %H:%M:%S")

def convert_to_casablanca_date(date_str):
    """Convert a date string to Casablanca timezone"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        morocco_tz = pytz.timezone('Africa/Casablanca')
        return dt.date()  # Simplified since stored times are already in Casablanca time
    except:
        return None

def get_date_range_casablanca(date):
    """Get start and end of day in Casablanca time"""
    try:
        start = datetime.combine(date, time.min)
        end = datetime.combine(date, time.max)
        return start, end
    except Exception as e:
        st.error(f"Error processing date: {str(e)}")
        return None, None

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
        cursor.execute("SELECT role, user_group FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", 
                      (username, hashed_password))
        result = cursor.fetchone()
        return (result[0], result[1]) if result else (None, None)
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
                role TEXT CHECK(role IN ('agent', 'admin', 'qa')),
                user_group TEXT CHECK(user_group IN ('1', '2', '3', '4', 'admin', 'qa'))
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vip_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                mentions TEXT,
                user_group TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                request_type TEXT,
                identifier TEXT,
                comment TEXT,
                timestamp TEXT,
                completed INTEGER DEFAULT 0,
                user_group TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_leader TEXT,
                agent_name TEXT,
                ticket_id TEXT,
                error_description TEXT,
                timestamp TEXT,
                user_group TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                mentions TEXT,
                user_group TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY,
                killswitch_enabled INTEGER DEFAULT 0,
                chat_killswitch_enabled INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                user TEXT,
                comment TEXT,
                timestamp TEXT,
                FOREIGN KEY(request_id) REFERENCES requests(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hold_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uploader TEXT,
                image_data BLOB,
                timestamp TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS late_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                presence_time TEXT,
                login_time TEXT,
                reason TEXT,
                timestamp TEXT,
                user_group TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                issue_type TEXT,
                timing TEXT,
                mobile_number TEXT,
                product TEXT,
                timestamp TEXT,
                user_group TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS midshift_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                issue_type TEXT,
                start_time TEXT,
                end_time TEXT,
                timestamp TEXT,
                user_group TEXT
            )
        """)
        
        # Initialize system settings if not exists
        cursor.execute("INSERT OR IGNORE INTO system_settings (id, killswitch_enabled, chat_killswitch_enabled) VALUES (1, 0, 0)")
        
        # Create default admin account
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password, role, user_group) 
            VALUES (?, ?, ?, ?)
        """, ("taha kirri", hash_password("arise@99"), "admin", "admin"))
        
        # Create other admin accounts
        admin_accounts = [
            ("taha kirri", "arise@99", "admin", "admin"),
            ("Issam Samghini", "admin@2025", "admin", "admin"),
            ("Loubna Fellah", "admin@99", "admin", "admin"),
            ("Youssef Kamal", "admin@006", "admin", "admin"),
            ("Fouad Fathi", "admin@55", "admin", "admin")
        ]
        
        for username, password, role, group in admin_accounts:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, role, user_group) 
                VALUES (?, ?, ?, ?)
            """, (username, hash_password(password), role, group))
        
        # Create agent accounts with group assignments
        agents = [
            ("Karabila Younes", "30866", "1"),
            ("Kaoutar Mzara", "30514", "1"),
            ("Ben Tahar Chahid", "30864", "2"),
            ("Cherbassi Khadija", "30868", "2"),
            ("Lekhmouchi Kamal", "30869", "3"),
            ("Said Kilani", "30626", "3"),
            ("AGLIF Rachid", "30830", "4"),
            ("Yacine Adouha", "30577", "4"),
            ("Manal Elanbi", "30878", "1"),
            ("Jawad Ouassaddine", "30559", "1"),
            ("Kamal Elhaouar", "30844", "2"),
            ("Hoummad Oubella", "30702", "2"),
            ("Zouheir Essafi", "30703", "3"),
            ("Anwar Atifi", "30781", "3"),
            ("Said Elgaouzi", "30782", "4"),
            ("HAMZA SAOUI", "30716", "4"),
            ("Ibtissam Mazhari", "30970", "1"),
            ("Imad Ghazali", "30971", "1"),
            ("Jamila Lahrech", "30972", "2"),
            ("Nassim Ouazzani Touhami", "30973", "2"),
            ("Salaheddine Chaggour", "30974", "3"),
            ("Omar Tajani", "30711", "3"),
            ("Nizar Remz", "30728", "4"),
            ("Abdelouahed Fettah", "30693", "4"),
            ("Amal Bouramdane", "30675", "1"),
            ("Fatima Ezzahrae Oubaalla", "30513", "1"),
            ("Redouane Bertal", "30643", "2"),
            ("Abdelouahab Chenani", "30789", "2"),
            ("Imad El Youbi", "30797", "3"),
            ("Youssef Hammouda", "30791", "3"),
            ("Anas Ouassifi", "30894", "4"),
            ("SALSABIL ELMOUSS", "30723", "4"),
            ("Hicham Khalafa", "30712", "1"),
            ("Ghita Adib", "30710", "1"),
            ("Aymane Msikila", "30722", "2"),
            ("Marouane Boukhadda", "30890", "2"),
            ("Hamid Boulatouan", "30899", "3"),
            ("Bouchaib Chafiqi", "30895", "3"),
            ("Houssam Gouaalla", "30891", "4"),
            ("Abdellah Rguig", "30963", "4"),
            ("Abdellatif Chatir", "30964", "1"),
            ("Abderrahman Oueto", "30965", "1"),
            ("Fatiha Lkamel", "30967", "2"),
            ("Abdelhamid Jaber", "30708", "2"),
            ("Yassine Elkanouni", "30735", "3")
        ]
        
        for agent_name, workspace_id, group in agents:
            cursor.execute("""
                INSERT OR IGNORE INTO users (username, password, role, user_group) 
                VALUES (?, ?, ?, ?)
            """, (agent_name, hash_password(workspace_id), "agent", group))
        
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

def add_request(agent_name, request_type, identifier, comment, user_group):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        timestamp = get_casablanca_time()
        cursor.execute("""
            INSERT INTO requests (agent_name, request_type, identifier, comment, timestamp, user_group) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, request_type, identifier, comment, timestamp, user_group))
        
        request_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO request_comments (request_id, user, comment, timestamp)
            VALUES (?, ?, ?, ?)
        """, (request_id, agent_name, f"Request created: {comment}", timestamp))
        
        conn.commit()
        return True
    finally:
        conn.close()

def get_requests(group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT r.* FROM requests r
                JOIN users u ON r.agent_name = u.username
                WHERE u.user_group = ? OR r.user_group = ?
                ORDER BY r.timestamp DESC
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM requests ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def search_requests(query, group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = f"%{query.lower()}%"
        if group and group != 'admin':
            cursor.execute("""
                SELECT r.* FROM requests r
                JOIN users u ON r.agent_name = u.username
                WHERE (u.user_group = ? OR r.user_group = ?)
                AND (LOWER(r.agent_name) LIKE ? 
                OR LOWER(r.request_type) LIKE ? 
                OR LOWER(r.identifier) LIKE ? 
                OR LOWER(r.comment) LIKE ?)
                ORDER BY r.timestamp DESC
            """, (group, group, query, query, query, query))
        else:
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
        """, (request_id, user, comment, get_casablanca_time()))
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

def add_mistake(team_leader, agent_name, ticket_id, error_description, user_group):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mistakes (team_leader, agent_name, ticket_id, error_description, timestamp, user_group) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (team_leader, agent_name, ticket_id, error_description, get_casablanca_time(), user_group))
        conn.commit()
        return True
    finally:
        conn.close()

def get_mistakes(group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT m.* FROM mistakes m
                JOIN users u ON m.agent_name = u.username
                WHERE u.user_group = ? OR m.user_group = ?
                ORDER BY m.timestamp DESC
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM mistakes ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def search_mistakes(query, group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = f"%{query.lower()}%"
        if group and group != 'admin':
            cursor.execute("""
                SELECT m.* FROM mistakes m
                JOIN users u ON m.agent_name = u.username
                WHERE (u.user_group = ? OR m.user_group = ?)
                AND (LOWER(m.agent_name) LIKE ? 
                OR LOWER(m.ticket_id) LIKE ? 
                OR LOWER(m.error_description) LIKE ?
                ORDER BY m.timestamp DESC
            """, (group, group, query, query, query))
        else:
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

def send_group_message(sender, message, user_group):
    if is_killswitch_enabled() or is_chat_killswitch_enabled():
        st.error("Chat is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        mentions = re.findall(r'@(\w+)', message)
        cursor.execute("""
            INSERT INTO group_messages (sender, message, timestamp, mentions, user_group) 
            VALUES (?, ?, ?, ?, ?)
        """, (sender, message, get_casablanca_time(), ','.join(mentions), user_group))
        conn.commit()
        return True
    finally:
        conn.close()

def get_group_messages(group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT gm.* FROM group_messages gm
                JOIN users u ON gm.sender = u.username
                WHERE u.user_group = ? OR gm.user_group = ? OR u.role = 'admin'
                ORDER BY gm.timestamp DESC LIMIT 50
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM group_messages ORDER BY timestamp DESC LIMIT 50")
        return cursor.fetchall()
    finally:
        conn.close()

def get_all_users():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, user_group FROM users")
        return cursor.fetchall()
    finally:
        conn.close()

def add_user(username, password, role, group=None):
    if is_killswitch_enabled():
        st.error('System is currently locked. Please contact the developer.')
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Check if user already exists
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            st.error(f'User "{username}" already exists. Please choose a different username.')
            return False
        
        # Set group based on role
        if role == 'admin':
            group = 'admin'
        elif role == 'qa':
            group = 'qa'
        elif role == 'agent' and not group:
            group = '1'  # Default group for agents
            
        # If user doesn't exist, proceed with insertion
        cursor.execute('INSERT INTO users (username, password, role, user_group) VALUES (?, ?, ?, ?)',
                       (username, hash_password(password), role, group))
        conn.commit()
        st.success(f'User "{username}" successfully created!')
        return True
    except sqlite3.IntegrityError:
        st.error(f'An error occurred while creating user "{username}". Please try again.')
        return False
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
        
def reset_password(username, new_password):
    """Reset a user's password"""
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        hashed_password = hash_password(new_password)
        cursor.execute("UPDATE users SET password = ? WHERE username = ?", 
                     (hashed_password, username))
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
        """, (uploader, image_data, get_casablanca_time()))
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

def add_late_login(agent_name, presence_time, login_time, reason, user_group):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO late_logins (agent_name, presence_time, login_time, reason, timestamp, user_group) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, presence_time, login_time, reason, get_casablanca_time(), user_group))
        conn.commit()
        return True
    finally:
        conn.close()

def get_late_logins(group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT ll.* FROM late_logins ll
                JOIN users u ON ll.agent_name = u.username
                WHERE u.user_group = ? OR ll.user_group = ?
                ORDER BY ll.timestamp DESC
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM late_logins ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()

def add_quality_issue(agent_name, issue_type, timing, mobile_number, product, user_group):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quality_issues (agent_name, issue_type, timing, mobile_number, product, timestamp, user_group) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agent_name, issue_type, timing, mobile_number, product, get_casablanca_time(), user_group))
        conn.commit()
        return True
    finally:
        conn.close()

def get_quality_issues(group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT qi.* FROM quality_issues qi
                JOIN users u ON qi.agent_name = u.username
                WHERE u.user_group = ? OR qi.user_group = ?
                ORDER BY qi.timestamp DESC
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM quality_issues ORDER BY timestamp DESC")
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Error fetching quality issues: {str(e)}")
    finally:
        conn.close()

def add_midshift_issue(agent_name, issue_type, start_time, end_time, user_group):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO midshift_issues (agent_name, issue_type, start_time, end_time, timestamp, user_group) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, issue_type, start_time, end_time, get_casablanca_time(), user_group))
        conn.commit()
        return True
    finally:
        conn.close()

def get_midshift_issues(group=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT mi.* FROM midshift_issues mi
                JOIN users u ON mi.agent_name = u.username
                WHERE u.user_group = ? OR mi.user_group = ?
                ORDER BY mi.timestamp DESC
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM midshift_issues ORDER BY timestamp DESC")
        return cursor.fetchall()
    except Exception as e:
        st.error(f"Error fetching mid-shift issues: {str(e)}")
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
    except Exception as e:
        st.error(f"Error clearing late logins: {str(e)}")
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
    except Exception as e:
        st.error(f"Error clearing quality issues: {str(e)}")
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
    except Exception as e:
        st.error(f"Error clearing mid-shift issues: {str(e)}")
    finally:
        conn.close()

def send_vip_message(sender, message, user_group):
    """Send a message in the VIP-only chat"""
    if is_killswitch_enabled() or is_chat_killswitch_enabled():
        st.error("Chat is currently locked. Please contact the developer.")
        return False
    
    if not is_vip_user(sender) and sender.lower() != "taha kirri":
        st.error("Only VIP users can send messages in this chat.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        mentions = re.findall(r'@(\w+)', message)
        cursor.execute("""
            INSERT INTO vip_messages (sender, message, timestamp, mentions, user_group) 
            VALUES (?, ?, ?, ?, ?)
        """, (sender, message, get_casablanca_time(), ','.join(mentions), user_group))
        conn.commit()
        return True
    finally:
        conn.close()

def get_vip_messages(group=None):
    """Get messages from the VIP-only chat"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group and group != 'admin':
            cursor.execute("""
                SELECT vm.* FROM vip_messages vm
                JOIN users u ON vm.sender = u.username
                WHERE u.user_group = ? OR vm.user_group = ? OR u.role = 'admin'
                ORDER BY vm.timestamp DESC LIMIT 50
            """, (group, group))
        else:
            cursor.execute("SELECT * FROM vip_messages ORDER BY timestamp DESC LIMIT 50")
        return cursor.fetchall()
    finally:
        conn.close()

# --------------------------
# Break Scheduling Functions
# --------------------------

def init_break_session_state():
    if 'templates' not in st.session_state:
        st.session_state.templates = {}
    if 'current_template' not in st.session_state:
        st.session_state.current_template = None
    if 'agent_bookings' not in st.session_state:
        st.session_state.agent_bookings = {}
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = datetime.now().strftime('%Y-%m-%d')
    if 'timezone_offset' not in st.session_state:
        st.session_state.timezone_offset = 0  # GMT by default
    if 'break_limits' not in st.session_state:
        st.session_state.break_limits = {}
    if 'active_templates' not in st.session_state:
        st.session_state.active_templates = []
    
    # Load data from files if exists
    if os.path.exists('templates.json'):
        with open('templates.json', 'r') as f:
            st.session_state.templates = json.load(f)
    if os.path.exists('break_limits.json'):
        with open('break_limits.json', 'r') as f:
            st.session_state.break_limits = json.load(f)
    if os.path.exists('all_bookings.json'):
        with open('all_bookings.json', 'r') as f:
            st.session_state.agent_bookings = json.load(f)
    if os.path.exists('active_templates.json'):
        with open('active_templates.json', 'r') as f:
            st.session_state.active_templates = json.load(f)

def adjust_template_time(time_str, hours):
    """Adjust a single time string by adding/subtracting hours"""
    try:
        if not time_str.strip():
            return ""
        time_obj = datetime.strptime(time_str.strip(), "%H:%M")
        adjusted_time = (time_obj + timedelta(hours=hours)).time()
        return adjusted_time.strftime("%H:%M")
    except:
        return time_str

def bulk_update_template_times(hours):
    """Update all template times by adding/subtracting hours"""
    if 'templates' not in st.session_state:
        return False
    
    try:
        for template_name in st.session_state.templates:
            template = st.session_state.templates[template_name]
            
            # Update lunch breaks
            template["lunch_breaks"] = [
                adjust_template_time(t, hours) 
                for t in template["lunch_breaks"]
            ]
            
            # Update early tea breaks
            template["tea_breaks"]["early"] = [
                adjust_template_time(t, hours) 
                for t in template["tea_breaks"]["early"]
            ]
            
            # Update late tea breaks
            template["tea_breaks"]["late"] = [
                adjust_template_time(t, hours) 
                for t in template["tea_breaks"]["late"]
            ]
        
        save_break_data()
        return True
    except Exception as e:
        st.error(f"Error updating template times: {str(e)}")
        return False

def save_break_data():
    with open('templates.json', 'w') as f:
        json.dump(st.session_state.templates, f)
    with open('break_limits.json', 'w') as f:
        json.dump(st.session_state.break_limits, f)
    with open('all_bookings.json', 'w') as f:
        json.dump(st.session_state.agent_bookings, f)
    with open('active_templates.json', 'w') as f:
        json.dump(st.session_state.active_templates, f)

def adjust_time(time_str, offset):
    try:
        if not time_str.strip():
            return ""
        time_obj = datetime.strptime(time_str.strip(), "%H:%M")
        adjusted_time = (time_obj + timedelta(hours=offset)).time()
        return adjusted_time.strftime("%H:%M")
    except:
        return time_str

def adjust_template_times(template, offset):
    """Safely adjust template times with proper error handling"""
    try:
        if not template or not isinstance(template, dict):
            return {
                "lunch_breaks": [],
                "tea_breaks": {"early": [], "late": []}
            }
            
        adjusted_template = {
            "lunch_breaks": [adjust_time(t, offset) for t in template.get("lunch_breaks", [])],
            "tea_breaks": {
                "early": [adjust_time(t, offset) for t in template.get("tea_breaks", {}).get("early", [])],
                "late": [adjust_time(t, offset) for t in template.get("tea_breaks", {}).get("late", [])]
            }
        }
        return adjusted_template
    except Exception as e:
        st.error(f"Error adjusting template times: {str(e)}")
        return {
            "lunch_breaks": [],
            "tea_breaks": {"early": [], "late": []}
        }

def count_bookings(date, break_type, time_slot):
    count = 0
    if date in st.session_state.agent_bookings:
        for agent_id, breaks in st.session_state.agent_bookings[date].items():
            if break_type == "lunch" and "lunch" in breaks and breaks["lunch"] == time_slot:
                count += 1
            elif break_type == "early_tea" and "early_tea" in breaks and breaks["early_tea"] == time_slot:
                count += 1
            elif break_type == "late_tea" and "late_tea" in breaks and breaks["late_tea"] == time_slot:
                count += 1
    return count

def display_schedule(template):
    st.header("LM US ENG 3:00 PM shift")
    
    # Lunch breaks table
    st.markdown("### LUNCH BREAKS")
    lunch_df = pd.DataFrame({
        "DATE": [st.session_state.selected_date],
        **{time: [""] for time in template["lunch_breaks"]}
    })
    st.table(lunch_df)
    
    st.markdown("**KINDLY RESPECT THE RULES BELOW**")
    st.markdown("**Non Respect Of Break Rules = Incident**")
    st.markdown("---")
    
    # Tea breaks table
    st.markdown("### TEA BREAK")
    
    # Create two columns for tea breaks
    max_rows = max(len(template["tea_breaks"]["early"]), len(template["tea_breaks"]["late"]))
    tea_data = {
        "Early Tea Break": template["tea_breaks"]["early"] + [""] * (max_rows - len(template["tea_breaks"]["early"])),
        "Late Tea Break": template["tea_breaks"]["late"] + [""] * (max_rows - len(template["tea_breaks"]["late"]))
    }
    tea_df = pd.DataFrame(tea_data)
    st.table(tea_df)
    
    # Rules section
    st.markdown("""
    **NO BREAK IN THE LAST HOUR WILL BE AUTHORIZED**  
    **PS: ONLY 5 MINUTES BIO IS AUTHORIZED IN THE LAST HHOUR BETWEEN 23:00 TILL 23:30 AND NO BREAK AFTER 23:30 !!!**  
    **BREAKS SHOULD BE TAKEN AT THE NOTED TIME AND NEED TO BE CONFIRMED FROM RTA OR TEAM LEADERS**
    """)

def migrate_booking_data():
    if 'agent_bookings' in st.session_state:
        for date in st.session_state.agent_bookings:
            for agent in st.session_state.agent_bookings[date]:
                bookings = st.session_state.agent_bookings[date][agent]
                if "lunch" in bookings and isinstance(bookings["lunch"], str):
                    bookings["lunch"] = {
                        "time": bookings["lunch"],
                        "template": "Default Template",
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                if "early_tea" in bookings and isinstance(bookings["early_tea"], str):
                    bookings["early_tea"] = {
                        "time": bookings["early_tea"],
                        "template": "Default Template",
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                if "late_tea" in bookings and isinstance(bookings["late_tea"], str):
                    bookings["late_tea"] = {
                        "time": bookings["late_tea"],
                        "template": "Default Template",
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
        
        save_break_data()

def clear_all_bookings():
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
    
    try:
        # Clear session state bookings
        st.session_state.agent_bookings = {}
        
        # Clear the bookings file
        if os.path.exists('all_bookings.json'):
            with open('all_bookings.json', 'w') as f:
                json.dump({}, f)
        
        # Save empty state to ensure it's propagated
        save_break_data()
        
        # Force session state refresh
        st.session_state.last_request_count = 0
        st.session_state.last_mistake_count = 0
        st.session_state.last_message_ids = []
        
        return True
    except Exception as e:
        st.error(f"Error clearing bookings: {str(e)}")
        return False

def admin_break_dashboard():
    st.title("Break Schedule Management")
    st.markdown("---")
    
    # Initialize templates if empty
    if 'templates' not in st.session_state:
        st.session_state.templates = {}
    
    # Create default template if no templates exist
    if not st.session_state.templates:
        default_template = {
            "lunch_breaks": ["19:30", "20:00", "20:30", "21:00", "21:30"],
            "tea_breaks": {
                "early": ["16:00", "16:15", "16:30", "16:45", "17:00", "17:15", "17:30"],
                "late": ["21:45", "22:00", "22:15", "22:30"]
            }
        }
        st.session_state.templates["Default Template"] = default_template
        st.session_state.current_template = "Default Template"
        if "Default Template" not in st.session_state.active_templates:
            st.session_state.active_templates.append("Default Template")
        save_break_data()
    
    # Template Activation Management
    st.subheader("🔄 Template Activation")
    st.info("Only activated templates will be available for agents to book breaks from.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("### Active Templates")
        active_templates = st.session_state.active_templates
        template_list = list(st.session_state.templates.keys())
        
        for template in template_list:
            is_active = template in active_templates
            if st.checkbox(f"{template} {'✅' if is_active else ''}", 
                         value=is_active, 
                         key=f"active_{template}"):
                if template not in active_templates:
                    active_templates.append(template)
            else:
                if template in active_templates:
                    active_templates.remove(template)
        
        st.session_state.active_templates = active_templates
        save_break_data()
    
    with col2:
        st.write("### Statistics")
        st.metric("Total Templates", len(template_list))
        st.metric("Active Templates", len(active_templates))
    
    st.markdown("---")
    
    # Template Management
    st.subheader("Template Management")
    
    col1, col2 = st.columns(2)
    with col1:
        template_name = st.text_input("New Template Name:")
    with col2:
        if st.button("Create Template"):
            if template_name and template_name not in st.session_state.templates:
                st.session_state.templates[template_name] = {
                    "lunch_breaks": ["19:30", "20:00", "20:30", "21:00", "21:30"],
                    "tea_breaks": {
                        "early": ["16:00", "16:15", "16:30", "16:45", "17:00", "17:15", "17:30"],
                        "late": ["21:45", "22:00", "22:15", "22:30"]
                    }
                }
                save_break_data()
                st.success(f"Template '{template_name}' created!")
                st.rerun()
    
    # Template Selection and Editing
    selected_template = st.selectbox(
        "Select Template to Edit:",
        list(st.session_state.templates.keys())
    )
    
    if selected_template:
        template = st.session_state.templates[selected_template]
        
        # Time adjustment buttons
        st.subheader("Time Adjustment")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add 1 Hour to All Times"):
                bulk_update_template_times(1)
                st.success("Added 1 hour to all break times")
                st.rerun()
        with col2:
            if st.button("➖ Subtract 1 Hour from All Times"):
                bulk_update_template_times(-1)
                st.success("Subtracted 1 hour from all break times")
                st.rerun()
        
        # Edit Lunch Breaks
        st.subheader("Edit Lunch Breaks")
        lunch_breaks = st.text_area(
            "Enter lunch break times (one per line):",
            "\n".join(template["lunch_breaks"]),
            height=150
        )
        
        # Edit Tea Breaks
        st.subheader("Edit Tea Breaks")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("Early Tea Breaks")
            early_tea = st.text_area(
                "Enter early tea break times (one per line):",
                "\n".join(template["tea_breaks"]["early"]),
                height=200
            )
        
        with col2:
            st.write("Late Tea Breaks")
            late_tea = st.text_area(
                "Enter late tea break times (one per line):",
                "\n".join(template["tea_breaks"]["late"]),
                height=200
            )
        
        # Break Limits
        st.markdown("---")
        st.subheader("Break Limits")
        
        if selected_template not in st.session_state.break_limits:
            st.session_state.break_limits[selected_template] = {
                "lunch": {time: 5 for time in template["lunch_breaks"]},
                "early_tea": {time: 3 for time in template["tea_breaks"]["early"]},
                "late_tea": {time: 3 for time in template["tea_breaks"]["late"]}
            }
        
        limits = st.session_state.break_limits[selected_template]
        
        st.write("Lunch Break Limits")
        cols = st.columns(len(template["lunch_breaks"]))
        for i, time in enumerate(template["lunch_breaks"]):
            with cols[i]:
                limits["lunch"][time] = st.number_input(
                    f"Max at {time}",
                    min_value=1,
                    value=limits["lunch"].get(time, 5),
                    key=f"lunch_limit_{time}"
                )
        
        st.write("Early Tea Break Limits")
        cols = st.columns(len(template["tea_breaks"]["early"]))
        for i, time in enumerate(template["tea_breaks"]["early"]):
            with cols[i]:
                limits["early_tea"][time] = st.number_input(
                    f"Max at {time}",
                    min_value=1,
                    value=limits["early_tea"].get(time, 3),
                    key=f"early_tea_limit_{time}"
                )
        
        st.write("Late Tea Break Limits")
        cols = st.columns(len(template["tea_breaks"]["late"]))
        for i, time in enumerate(template["tea_breaks"]["late"]):
            with cols[i]:
                limits["late_tea"][time] = st.number_input(
                    f"Max at {time}",
                    min_value=1,
                    value=limits["late_tea"].get(time, 3),
                    key=f"late_tea_limit_{time}"
                )
        
        # Consolidated save button
        if st.button("Save All Changes", type="primary"):
            template["lunch_breaks"] = [t.strip() for t in lunch_breaks.split("\n") if t.strip()]
            template["tea_breaks"]["early"] = [t.strip() for t in early_tea.split("\n") if t.strip()]
            template["tea_breaks"]["late"] = [t.strip() for t in late_tea.split("\n") if t.strip()]
            save_break_data()
            st.success("All changes saved successfully!")
            st.rerun()
        
        if st.button("Delete Template") and len(st.session_state.templates) > 1:
            del st.session_state.templates[selected_template]
            if selected_template in st.session_state.active_templates:
                st.session_state.active_templates.remove(selected_template)
            save_break_data()
            st.success(f"Template '{selected_template}' deleted!")
            st.rerun()
    
    # View Bookings with template information
    st.markdown("---")
    st.subheader("View All Bookings")
    
    dates = list(st.session_state.agent_bookings.keys())
    if dates:
        selected_date = st.selectbox("Select Date:", dates, index=len(dates)-1)
        
        # Add clear bookings button with proper confirmation
        if 'confirm_clear' not in st.session_state:
            st.session_state.confirm_clear = False
            
        col1, col2 = st.columns([1, 3])
        with col1:
            if not st.session_state.confirm_clear:
                if st.button("Clear All Bookings"):
                    st.session_state.confirm_clear = True
            
        if st.session_state.confirm_clear:
            st.warning("⚠️ Are you sure you want to clear all bookings? This cannot be undone!")
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("Yes, Clear All"):
                    if clear_all_bookings():
                        st.success("All bookings have been cleared!")
                        st.session_state.confirm_clear = False
                        st.rerun()
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_clear = False
                    st.rerun()
        
        if selected_date in st.session_state.agent_bookings:
            bookings_data = []
            for agent, breaks in st.session_state.agent_bookings[selected_date].items():
                # Get template name from any break type (they should all be the same)
                template_name = None
                for break_type in ['lunch', 'early_tea', 'late_tea']:
                    if break_type in breaks and isinstance(breaks[break_type], dict):
                        template_name = breaks[break_type].get('template', 'Unknown')
                        break
                
                booking = {
                    "Agent": agent,
                    "Template": template_name or "Unknown",
                    "Lunch": breaks.get("lunch", {}).get("time", "-") if isinstance(breaks.get("lunch"), dict) else breaks.get("lunch", "-"),
                    "Early Tea": breaks.get("early_tea", {}).get("time", "-") if isinstance(breaks.get("early_tea"), dict) else breaks.get("early_tea", "-"),
                    "Late Tea": breaks.get("late_tea", {}).get("time", "-") if isinstance(breaks.get("late_tea"), dict) else breaks.get("late_tea", "-")
                }
                bookings_data.append(booking)
            
            if bookings_data:
                df = pd.DataFrame(bookings_data)
                st.dataframe(df)
                
                # Export option
                if st.button("Export to CSV"):
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "Download CSV",
                        csv,
                        f"break_bookings_{selected_date}.csv",
                        "text/csv"
                    )
            else:
                st.info("No bookings found for this date")
    else:
        st.info("No bookings available")

def time_to_minutes(time_str):
    """Convert time string (HH:MM) to minutes since midnight"""
    try:
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    except:
        return None

def times_overlap(time1, time2, duration_minutes=15):
    """Check if two time slots overlap, assuming each break is duration_minutes long"""
    t1 = time_to_minutes(time1)
    t2 = time_to_minutes(time2)
    
    if t1 is None or t2 is None:
        return False
        
    # Check if the breaks overlap
    return abs(t1 - t2) < duration_minutes

def check_break_conflicts(selected_breaks):
    """Check for conflicts between selected breaks"""
    times = []
    
    # Collect all selected break times
    if selected_breaks.get("lunch"):
        times.append(("lunch", selected_breaks["lunch"]))
    if selected_breaks.get("early_tea"):
        times.append(("early_tea", selected_breaks["early_tea"]))
    if selected_breaks.get("late_tea"):
        times.append(("late_tea", selected_breaks["late_tea"]))
    
    # Check each pair of breaks for overlap
    for i in range(len(times)):
        for j in range(i + 1, len(times)):
            break1_type, break1_time = times[i]
            break2_type, break2_time = times[j]
            
            if times_overlap(break1_time, break2_time, 30 if "lunch" in (break1_type, break2_type) else 15):
                return f"Conflict detected between {break1_type.replace('_', ' ')} ({break1_time}) and {break2_type.replace('_', ' ')} ({break2_time})"
    
    return None

def agent_break_dashboard():
    st.title("Break Booking")
    st.markdown("---")
    
    if is_killswitch_enabled():
        st.error("System is currently locked. Break booking is disabled.")
        return
    
    # Get the agent's group
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT user_group FROM users WHERE username = ?", (st.session_state.username,))
        agent_group = cursor.fetchone()[0]
    finally:
        conn.close()
    
    # Initialize session state
    if 'agent_bookings' not in st.session_state:
        st.session_state.agent_bookings = {}
    if 'temp_bookings' not in st.session_state:
        st.session_state.temp_bookings = {}
    if 'booking_confirmed' not in st.session_state:
        st.session_state.booking_confirmed = False
    if 'selected_template_name' not in st.session_state:
        st.session_state.selected_template_name = None
    
    agent_id = st.session_state.username
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Check if agent already has confirmed bookings
    has_confirmed_bookings = (
        current_date in st.session_state.agent_bookings and 
        agent_id in st.session_state.agent_bookings[current_date]
    )
    
    if has_confirmed_bookings:
        st.success("Your breaks have been confirmed for today")
        st.subheader("Your Confirmed Breaks")
        bookings = st.session_state.agent_bookings[current_date][agent_id]
        template_name = None
        for break_type in ['lunch', 'early_tea', 'late_tea']:
            if break_type in bookings and isinstance(bookings[break_type], dict):
                template_name = bookings[break_type].get('template')
                break
        
        if template_name:
            st.info(f"Template: **{template_name}**")
        
        for break_type, display_name in [
            ("lunch", "Lunch Break"),
            ("early_tea", "Early Tea Break"),
            ("late_tea", "Late Tea Break")
        ]:
            if break_type in bookings:
                if isinstance(bookings[break_type], dict):
                    st.write(f"**{display_name}:** {bookings[break_type]['time']}")
                else:
                    st.write(f"**{display_name}:** {bookings[break_type]}")
        return
    
    # Step 1: Template Selection
    if not st.session_state.selected_template_name:
        st.subheader("Step 1: Select Break Schedule")
        available_templates = st.session_state.active_templates
        if not available_templates:
            st.error("No break schedules available. Please contact admin.")
            return
        
        selected_template = st.selectbox(
            "Choose your break schedule:",
            available_templates,
            index=None,
            placeholder="Select a template..."
        )
        
        if selected_template:
            if st.button("Continue to Break Selection"):
                st.session_state.selected_template_name = selected_template
                st.rerun()
        return
    
    # Step 2: Break Selection
    template = st.session_state.templates[st.session_state.selected_template_name]
    
    st.subheader("Step 2: Select Your Breaks")
    st.info(f"Selected Template: **{st.session_state.selected_template_name}**")
    
    if st.button("Change Template"):
        st.session_state.selected_template_name = None
        st.session_state.temp_bookings = {}
        st.rerun()
    
    # Break selection
    with st.form("break_selection_form"):
        st.write("**Lunch Break** (30 minutes)")
        lunch_time = st.selectbox(
            "Select Lunch Break",
            [""] + template["lunch_breaks"],
            format_func=lambda x: "No selection" if x == "" else x
        )
        
        st.write("**Early Tea Break** (15 minutes)")
        early_tea = st.selectbox(
            "Select Early Tea Break",
            [""] + template["tea_breaks"]["early"],
            format_func=lambda x: "No selection" if x == "" else x
        )
        
        st.write("**Late Tea Break** (15 minutes)")
        late_tea = st.selectbox(
            "Select Late Tea Break",
            [""] + template["tea_breaks"]["late"],
            format_func=lambda x: "No selection" if x == "" else x
        )
        
        # Validate and confirm
        if st.form_submit_button("Confirm Breaks"):
            if not (lunch_time or early_tea or late_tea):
                st.error("Please select at least one break.")
                return
            
            # Check for time conflicts
            selected_breaks = {
                "lunch": lunch_time if lunch_time else None,
                "early_tea": early_tea if early_tea else None,
                "late_tea": late_tea if late_tea else None
            }
            
            conflict = check_break_conflicts(selected_breaks)
            if conflict:
                st.error(conflict)
                return
            
            # Check limits for each selected break
            can_book = True
            if lunch_time:
                count = sum(1 for bookings in st.session_state.agent_bookings.get(current_date, {}).values()
                           if isinstance(bookings.get("lunch"), dict) and bookings["lunch"]["time"] == lunch_time)
                limit = st.session_state.break_limits.get(st.session_state.selected_template_name, {}).get("lunch", {}).get(lunch_time, 5)
                if count >= limit:
                    st.error(f"Lunch break at {lunch_time} is full.")
                    can_book = False
            
            if early_tea:
                count = sum(1 for bookings in st.session_state.agent_bookings.get(current_date, {}).values()
                           if isinstance(bookings.get("early_tea"), dict) and bookings["early_tea"]["time"] == early_tea)
                limit = st.session_state.break_limits.get(st.session_state.selected_template_name, {}).get("early_tea", {}).get(early_tea, 3)
                if count >= limit:
                    st.error(f"Early tea break at {early_tea} is full.")
                    can_book = False
            
            if late_tea:
                count = sum(1 for bookings in st.session_state.agent_bookings.get(current_date, {}).values()
                           if isinstance(bookings.get("late_tea"), dict) and bookings["late_tea"]["time"] == late_tea)
                limit = st.session_state.break_limits.get(st.session_state.selected_template_name, {}).get("late_tea", {}).get(late_tea, 3)
                if count >= limit:
                    st.error(f"Late tea break at {late_tea} is full.")
                    can_book = False
            
            if can_book:
                # Save the bookings
                if current_date not in st.session_state.agent_bookings:
                    st.session_state.agent_bookings[current_date] = {}
                
                bookings = {}
                if lunch_time:
                    bookings["lunch"] = {
                        "time": lunch_time,
                        "template": st.session_state.selected_template_name,
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                if early_tea:
                    bookings["early_tea"] = {
                        "time": early_tea,
                        "template": st.session_state.selected_template_name,
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                if late_tea:
                    bookings["late_tea"] = {
                        "time": late_tea,
                        "template": st.session_state.selected_template_name,
                        "booked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                
                st.session_state.agent_bookings[current_date][agent_id] = bookings
                save_break_data()
                st.success("Your breaks have been confirmed!")
                st.rerun()

def is_vip_user(username):
    """Check if a user has VIP status"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT is_vip FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return bool(result[0]) if result else False
    finally:
        conn.close()

def is_sequential(digits, step=1):
    """Check if digits form a sequential pattern with given step"""
    try:
        return all(int(digits[i]) == int(digits[i-1]) + step for i in range(1, len(digits)))
    except:
        return False

def is_fancy_number(phone_number):
    """Check if a phone number has a fancy pattern"""
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
    
    # More flexible ascending/descending patterns (like 141516)
    def is_flexible_sequential(digits, step=1):
        digits = [int(d) for d in digits]
        for i in range(1, len(digits)):
            if digits[i] - digits[i-1] != step:
                return False
        return True
    
    # Check for flexible ascending (e.g., 141516)
    if is_flexible_sequential(last_six, 1):
        patterns.append("Flexible ascending sequence (e.g., 141516)")
    
    # Check for flexible descending
    if is_flexible_sequential(last_six, -1):
        patterns.append("Flexible descending sequence")
        
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
            "Flexible ascending sequence",
            "Flexible descending sequence",
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

def lycamobile_fancy_number_checker():
    phone_number = st.text_input("Enter a phone number")
    if phone_number:
        is_fancy, pattern = is_fancy_number(phone_number)
        if is_fancy:
            st.success(f"The phone number {phone_number} has a fancy pattern: {pattern}")
        else:
            st.error(f"The phone number {phone_number} does not have a fancy pattern: {pattern}")

def set_vip_status(username, is_vip):
    """Set or remove VIP status for a user"""
    if not username:
        return False
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_vip = ? WHERE username = ?", 
                      (1 if is_vip else 0, username))
        conn.commit()
        return True
    finally:
        conn.close()

# --------------------------
# Streamlit App
# --------------------------

# Add this at the beginning of the file, after the imports
if 'color_mode' not in st.session_state:
    st.session_state.color_mode = 'dark'

def inject_custom_css():
    # Add notification JavaScript
    st.markdown("""
    <script>
    // Request notification permission on page load
    document.addEventListener('DOMContentLoaded', function() {
        if (Notification.permission !== 'granted') {
            Notification.requestPermission();
        }
    });

    // Function to show browser notification
    function showNotification(title, body) {
        if (Notification.permission === 'granted') {
            const notification = new Notification(title, {
                body: body,
                icon: '🔔'
            });
            
            notification.onclick = function() {
                window.focus();
                notification.close();
            };
        }
    }

    // Function to check for new messages
    async function checkNewMessages() {
        try {
            const response = await fetch('/check_messages');
            const data = await response.json();
            
            if (data.new_messages) {
                data.messages.forEach(msg => {
                    showNotification('New Message', `${msg.sender}: ${msg.message}`);
                });
            }
        } catch (error) {
            console.error('Error checking messages:', error);
        }
    }

    // Check for new messages every 30 seconds
    setInterval(checkNewMessages, 30000);
    </script>
    """, unsafe_allow_html=True)

    # Define color schemes for both modes
    colors = {
        'dark': {
            'bg': '#0f172a',
            'sidebar': '#1e293b',
            'card': '#1e293b',
            'text': '#e2e8f0',
            'text_secondary': '#94a3b8',
            'border': '#334155',
            'accent': '#2563eb',  # Bright blue
            'accent_hover': '#1d4ed8',
            'muted': '#94a3b8',
            'input_bg': '#1e293b',
            'input_text': '#e2e8f0',
            'my_message_bg': '#2563eb',
            'other_message_bg': '#334155',
            'hover_bg': '#334155',
            'notification_bg': '#1e293b',
            'notification_text': '#e2e8f0',
            'button_bg': '#2563eb',
            'button_text': '#ffffff',
            'button_hover': '#1d4ed8',
            'dropdown_bg': '#1e293b',
            'dropdown_text': '#e2e8f0',
            'dropdown_hover': '#334155',
            'table_header': '#1e293b',
            'table_row_even': '#1e293b',
            'table_row_odd': '#0f172a',
            'table_border': '#334155'
        },
        'light': {
            'bg': '#f8fafc',  # Soft, light neutral background
            'sidebar': '#ffffff',  # Pure white sidebar
            'card': '#ffffff',  # White cards
            'text': '#2d3748',  # Slightly softer dark text
            'text_secondary': '#4a5568',
            'border': '#e2e8f0',  # Soft, muted border
            'accent': '#3182ce',  # Softer blue accent
            'accent_hover': '#2c5282',
            'muted': '#718096',  # Softer muted text
            'input_bg': '#ffffff',
            'input_text': '#2d3748',
            'my_message_bg': '#3182ce',  # Blue message background
            'other_message_bg': '#f7fafc',
            'hover_bg': '#edf2f7',
            'notification_bg': '#ffffff',
            'notification_text': '#2d3748',
            'button_bg': '#3182ce',  # Soft blue buttons
            'button_text': '#ffffff',
            'button_hover': '#2c5282',
            'dropdown_bg': '#ffffff',
            'dropdown_text': '#2d3748',
            'dropdown_hover': '#edf2f7',
            'table_header': '#f7fafc',  # Very light blue-gray header
            'table_row_even': '#ffffff',
            'table_row_odd': '#f8fafc',
            'table_border': '#e2e8f0'
        }
    }

    # Use the appropriate color scheme based on the session state
    c = colors['dark'] if st.session_state.color_mode == 'dark' else colors['light']
    
    st.markdown(f"""
    <style>
        /* Global Styles */
        .stApp {{
            background-color: {c['bg']};
            color: {c['text']};
        }}
        
        /* Button Styling */
        .stButton > button {{
            background-color: {c['button_bg']} !important;
            color: {c['button_text']} !important;
            border: none !important;
            border-radius: 1rem !important;
            padding: 0.5rem 1rem !important;
            font-weight: 500 !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        .stButton > button:hover {{
            background-color: {c['button_hover']} !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }}
        
        /* Dropdown and Date Picker Styling */
        .stSelectbox [data-baseweb="select"],
        .stSelectbox [data-baseweb="select"] div,
        .stSelectbox [data-baseweb="select"] input,
        .stSelectbox [data-baseweb="popover"] ul,
        .stSelectbox [data-baseweb="select"] span,
        .stDateInput input,
        .stDateInput div[data-baseweb="calendar"] {{
            background-color: {c['input_bg']} !important;
            color: {c['text']} !important;
            border-color: {c['border']} !important;
        }}
        
        .stSelectbox [data-baseweb="select"] {{    
            border: 1px solid {c['border']} !important;
        }}
        
        .stSelectbox [data-baseweb="select"]:hover {{    
            border-color: {c['accent']} !important;
        }}
        
        .stSelectbox [data-baseweb="popover"] {{    
            background-color: {c['input_bg']} !important;
        }}
        
        .stSelectbox [data-baseweb="popover"] ul {{    
            background-color: {c['input_bg']} !important;
            border: 1px solid {c['border']} !important;
        }}
        
        .stSelectbox [data-baseweb="popover"] ul li {{    
            background-color: {c['input_bg']} !important;
            color: {c['text']} !important;
        }}
        
        .stSelectbox [data-baseweb="popover"] ul li:hover {{    
            background-color: {c['dropdown_hover']} !important;
        }}
        
        /* Template selection specific */
        .template-selector {{    
            margin-bottom: 1rem;
        }}
        
        .template-selector label,
        .default-template,
        .template-name {{    
            color: {c['text']} !important;
            font-weight: 500;
        }}
        
        /* Template text styles */
        div[data-testid="stMarkdownContainer"] p strong,

        /* Extended message duration */
        .stAlert {{    
            transition: opacity 0.5s ease-in-out;
            animation: fadeOut 10s forwards;
        }}

        @keyframes fadeOut {{
            0%, 90% {{ opacity: 1; }}
            100% {{ opacity: 0; display: none; }}
        }}
        div[data-testid="stMarkdownContainer"] p em,
        div[data-testid="stMarkdownContainer"] p {{    
            color: {c['text']} !important;
        }}
        
        .template-info {{    
            background-color: {c['card']} !important;
            border: 1px solid {c['border']} !important;
            padding: 0.75rem;
            border-radius: 0.375rem;
            margin-bottom: 1rem;
        }}
        
        .template-info p {{    
            color: {c['text']} !important;
            margin: 0;
        }}
        
        /* Input Fields and Labels */
        .stTextInput input, 
        .stTextArea textarea,
        .stNumberInput input {{    
            background-color: {c['input_bg']} !important;
            color: {c['input_text']} !important;
            border-color: {c['border']} !important;
            caret-color: {c['text']} !important;
        }}
        
        /* Input focus and selection */
        .stTextInput input:focus,
        .stTextArea textarea:focus,
        .stNumberInput input:focus {{    
            border-color: {c['accent']} !important;
            box-shadow: 0 0 0 1px {c['accent']} !important;
        }}
        
        ::selection {{    
            background-color: {c['accent']} !important;
            color: #ffffff !important;
        }}
        
        /* Input Labels and Text */
        .stTextInput label,
        .stTextArea label,
        .stNumberInput label,
        .stSelectbox label,
        .stDateInput label,
        div[data-baseweb="input"] label,
        .stMarkdown p,
        .element-container label,
        .stDateInput div,
        .stSelectbox div[data-baseweb="select"] div,
        .streamlit-expanderHeader,
        .stAlert p {{    
            color: {c['text']} !important;
        }}
        
        /* Message Alerts */
        .stAlert {{    
            background-color: {c['card']} !important;
            color: {c['text']} !important;
            padding: 1rem !important;
            border-radius: 1rem !important;
            margin-bottom: 1rem !important;
            border: 1px solid {c['border']} !important;
        }}
        
        .stAlert p,
        .stSuccess p,
        .stError p,
        .stWarning p,
        .stInfo p {{    
            color: {c['text']} !important;
        }}
        
        /* Empty state messages */
        .empty-state {{    
            color: {c['text']} !important;
            background-color: {c['card']} !important;
            border: 1px solid {c['border']} !important;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            margin: 2rem 0;
        }}
        
        /* Cards */
        .card {{
            background-color: {c['card']};
            border: 1px solid {c['border']};
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            color: {c['text']};
        }}
        
        /* Chat Message Styling */
        .chat-message {{
            display: flex;
            margin-bottom: 1rem;
            max-width: 80%;
            animation: fadeIn 0.3s ease-in-out;
        }}
        
        .chat-message.received {{
            margin-right: auto;
        }}
        
        .chat-message.sent {{
            margin-left: auto;
            flex-direction: row-reverse;
        }}
        
        .message-content {{
            padding: 0.75rem 1rem;
            border-radius: 1rem;
            position: relative;
        }}
        
        .received .message-content {{
            background-color: {c['other_message_bg']};
            color: {c['text']};
            border-bottom-left-radius: 0.25rem;
            margin-right: 1rem;
            border: 1px solid {c['border']};
        }}
        
        .sent .message-content {{
            background-color: {c['my_message_bg']};
            color: #ffffff;
            border-bottom-right-radius: 0.25rem;
            margin-left: 1rem;
            border: 1px solid {c['accent_hover']};
        }}
        
        .message-meta {{
            font-size: 0.75rem;
            color: {c['text_secondary']};
            margin-top: 0.25rem;
        }}
        
        .message-avatar {{
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 50%;
            background-color: {c['accent']};
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-weight: bold;
            font-size: 1rem;
        }}
        
        /* Table Styling */
        .stDataFrame {{
            background-color: {c['card']} !important;
            border: 1px solid {c['table_border']} !important;
            border-radius: 1rem !important;
            overflow: hidden !important;
        }}
        
        .stDataFrame td {{
            color: {c['text']} !important;
            border-color: {c['table_border']} !important;
            background-color: {c['table_row_even']} !important;
        }}
        
        .stDataFrame tr:nth-child(odd) td {{
            background-color: {c['table_row_odd']} !important;
        }}
        
        .stDataFrame th {{
            color: {c['text']} !important;
            background-color: {c['table_header']} !important;
            border-color: {c['table_border']} !important;
            font-weight: 600 !important;
        }}
        
        /* Buttons */
        .stButton button,
        button[kind="primary"],
        .stDownloadButton button,
        div[data-testid="stForm"] button,
        button[data-testid="baseButton-secondary"],
        .stButton > button {{    
            background-color: {c['button_bg']} !important;
            color: #ffffff !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            border-radius: 0.75rem !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        .stButton button:hover,
        button[kind="primary"]:hover,
        .stDownloadButton button:hover,
        div[data-testid="stForm"] button:hover,
        button[data-testid="baseButton-secondary"]:hover,
        .stButton > button:hover {{    
            background-color: {c['button_hover']} !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        }}
        
        /* Secondary Buttons */
        .secondary-button,
        button[data-testid="baseButton-secondary"],
        div[data-baseweb="button"] {{    
            background-color: {c['button_bg']} !important;
            color: #ffffff !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            border-radius: 0.75rem !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        .secondary-button:hover,
        button[data-testid="baseButton-secondary"]:hover,
        div[data-baseweb="button"]:hover {{    
            background-color: {c['button_hover']} !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        }}
        
        /* VIP Button */
        .vip-button {{    
            background-color: {c['accent']} !important;
            color: #ffffff !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            border-radius: 0.75rem !important;
            font-weight: 600 !important;
            transition: all 0.2s ease-in-out !important;
        }}
        
        .vip-button:hover {{    
            background-color: {c['accent_hover']} !important;
            transform: translateY(-1px) !important;
        }}
        
        /* Checkbox Styling */
        .stCheckbox > label {{
            color: {c['text']} !important;
        }}
        
        .stCheckbox > div[role="checkbox"] {{
            background-color: {c['input_bg']} !important;
            border-color: {c['border']} !important;
        }}
        
        /* Date Input Styling */
        .stDateInput > div > div {{
            background-color: {c['input_bg']} !important;
            color: {c['input_text']} !important;
            border-color: {c['border']} !important;
        }}
        
        /* Expander Styling */
        .streamlit-expanderHeader {{
            background-color: {c['card']} !important;
            color: {c['text']} !important;
            border-color: {c['border']} !important;
        }}
        
        /* Tabs Styling */
        .stTabs [data-baseweb="tab-list"] {{
            background-color: {c['card']} !important;
            border-color: {c['border']} !important;
        }}
        
        .stTabs [data-baseweb="tab"] {{
            color: {c['text']} !important;
        }}
        
        /* Theme Toggle Switch */
        .theme-toggle {{
            display: flex;
            align-items: center;
            padding: 0.5rem;
            margin-bottom: 1rem;
            border-radius: 0.5rem;
            background-color: {c['card']};
            border: 1px solid {c['border']};
        }}
        
        .theme-toggle label {{
            margin-right: 0.5rem;
            color: {c['text']};
        }}
    </style>
    """, unsafe_allow_html=True)

st.set_page_config(
    page_title="Lyca Management System",
    page_icon=":office:",
    layout="wide",
    initial_sidebar_state="expanded"
)

if "authenticated" not in st.session_state:
    st.session_state.update({
        "authenticated": False,
        "role": None,
        "username": None,
        "user_group": None,
        "current_section": "requests",
        "last_request_count": 0,
        "last_mistake_count": 0,
        "last_message_ids": []
    })

init_db()
init_break_session_state()

if not st.session_state.authenticated:
    st.markdown("""
        <div class="login-container">
            <h1 style="text-align: center; margin-bottom: 2rem;">🏢 Lyca Management System</h1>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_col1, submit_col2, submit_col3 = st.columns([1, 2, 1])
        with submit_col2:
            if st.form_submit_button("Login", use_container_width=True):
                if username and password:
                    role, user_group = authenticate(username, password)
                    if role:
                        st.session_state.update({
                            "authenticated": True,
                            "role": role,
                            "username": username,
                            "user_group": user_group,
                            "last_request_count": len(get_requests(user_group)),
                            "last_mistake_count": len(get_mistakes(user_group)),
                            "last_message_ids": [msg[0] for msg in get_group_messages(user_group)]
                        })
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
    
    st.markdown("</div>", unsafe_allow_html=True)

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
        current_requests = get_requests(st.session_state.user_group)
        current_mistakes = get_mistakes(st.session_state.user_group)
        current_messages = get_group_messages(st.session_state.user_group)
        
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
        
        # Theme toggle
        col1, col2 = st.columns([1, 6])
        with col1:
            current_icon = "🌙" if st.session_state.color_mode == 'dark' else "☀️"
            st.write(current_icon)
        with col2:
            if st.toggle("", value=st.session_state.color_mode == 'light', key='theme_toggle', label_visibility="collapsed"):
                if st.session_state.color_mode != 'light':
                    st.session_state.color_mode = 'light'
                    st.rerun()
            else:
                if st.session_state.color_mode != 'dark':
                    st.session_state.color_mode = 'dark'
                    st.rerun()
        st.markdown("---")
        
        # Base navigation options available to all users
        nav_options = []
        
        # QA users only see quality issues and fancy number
        if st.session_state.role == "qa":
            nav_options.extend([
                ("📞 Quality Issues", "quality_issues"),
                ("📱 Fancy Number", "fancy_number")
            ])
        # Admin and agent see all regular options
        elif st.session_state.role in ["admin", "agent"]:
            nav_options.extend([
                ("📋 Requests", "requests"),
                ("☕ Breaks", "breaks"),
                ("🖼️ HOLD", "hold"),
                ("❌ Mistakes", "mistakes"),
                ("💬 Chat", "chat"),
                ("⏰ Late Login", "late_login"),
                ("📞 Quality Issues", "quality_issues"),
                ("🔄 Mid-shift Issues", "midshift_issues"),
                ("📱 Fancy Number", "fancy_number")
            ])
        
        # Add admin option for admin users
        if st.session_state.role == "admin":
            nav_options.append(("⚙️ Admin", "admin"))
        
        for option, value in nav_options:
            if st.button(option, key=f"nav_{value}", use_container_width=True):
                st.session_state.current_section = value
        
        st.markdown("---")
        
        # Show notifications only for admin and agent roles
        if st.session_state.role in ["admin", "agent"]:
            pending_requests = len([r for r in get_requests(st.session_state.user_group) if not r[6]])
            new_mistakes = len(get_mistakes(st.session_state.user_group))
            unread_messages = len([m for m in get_group_messages(st.session_state.user_group) 
                                 if m[0] not in st.session_state.last_message_ids 
                                 and m[1] != st.session_state.username])
            
            st.markdown(f"""
            <div style="
                background-color: {'#1e293b' if st.session_state.color_mode == 'dark' else '#ffffff'};
                padding: 1rem;
                border-radius: 0.5rem;
                border: 1px solid {'#334155' if st.session_state.color_mode == 'dark' else '#e2e8f0'};
                margin-bottom: 20px;
            ">
                <h4 style="
                    color: {'#e2e8f0' if st.session_state.color_mode == 'dark' else '#1e293b'};
                    margin-bottom: 1rem;
                ">🔔 Notifications</h4>
                <p style="
                    color: {'#94a3b8' if st.session_state.color_mode == 'dark' else '#475569'};
                    margin-bottom: 0.5rem;
                ">📋 Pending requests: {pending_requests}</p>
                <p style="
                    color: {'#94a3b8' if st.session_state.color_mode == 'dark' else '#475569'};
                    margin-bottom: 0.5rem;
                ">❌ Recent mistakes: {new_mistakes}</p>
                <p style="
                    color: {'#94a3b8' if st.session_state.color_mode == 'dark' else '#475569'};
                ">💬 Unread messages: {unread_messages}</p>
            </div>
            """, unsafe_allow_html=True)
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    st.title(st.session_state.current_section.title())

    if st.session_state.current_section == "requests":
        if not is_killswitch_enabled():
            # Add group filter for admins
            if st.session_state.role == "admin":
                group_filter = st.selectbox(
                    "Filter by Group", 
                    ["All", "1", "2", "3", "4"],
                    key="request_group_filter"
                )
            else:
                group_filter = st.session_state.user_group if st.session_state.role == "agent" else None
            
            with st.expander("➕ Submit New Request"):
                with st.form("request_form"):
                    cols = st.columns([1, 3])
                    request_type = cols[0].selectbox("Type", ["Email", "Phone", "Ticket"])
                    identifier = cols[1].text_input("Identifier")
                    comment = st.text_area("Comment")
                    if st.form_submit_button("Submit"):
                        if identifier and comment:
                            if add_request(st.session_state.username, request_type, identifier, comment, st.session_state.user_group):
                                st.success("Request submitted successfully!")
                                st.rerun()
        
            st.subheader("🔍 Search Requests")
            search_query = st.text_input("Search requests...")
            
            # Get requests with group filter
            if st.session_state.role == "admin" and group_filter != "All":
                requests = search_requests(search_query, group_filter) if search_query else get_requests(group_filter)
            else:
                requests = search_requests(search_query, st.session_state.user_group) if search_query else get_requests(st.session_state.user_group)
                
            st.subheader("All Requests")
            for req in requests:
                req_id, agent, req_type, identifier, comment, timestamp, completed, group = req
                with st.container():
                    cols = st.columns([0.1, 0.9])
                    with cols[0]:
                        st.checkbox("Done", value=bool(completed), 
                                   key=f"check_{req_id}", 
                                   on_change=update_request_status,
                                   args=(req_id, not completed))
                    with cols[1]:
                        st.markdown(f"""
                        <div class="card">
                            <div style="display: flex; justify-content: space-between;">
                                <h4>#{req_id} - {req_type}</h4>
                                <small>{timestamp}</small>
                            </div>
                            <p>Agent: {agent} (Group: {group})</p>
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
                        
                        if st.session_state.role == "admin":
                            with st.form(key=f"comment_form_{req_id}"):
                                new_comment = st.text_input("Add status update/comment")
                                if st.form_submit_button("Add Comment"):
                                    if new_comment:
                                        add_request_comment(req_id, st.session_state.username, new_comment)
                                        st.rerun()
        else:
            st.error("System is currently locked. Access to requests is disabled.")

    elif st.session_state.current_section == "mistakes":
        if not is_killswitch_enabled():
            # Only show mistake reporting form to admin users
            if st.session_state.role == "admin":
                with st.expander("➕ Report New Mistake"):
                    with st.form("mistake_form"):
                        cols = st.columns(3)
                        agent_name = cols[0].text_input("Agent Name")
                        ticket_id = cols[1].text_input("Ticket ID")
                        error_description = st.text_area("Error Description")
                        if st.form_submit_button("Submit"):
                            if agent_name and ticket_id and error_description:
                                add_mistake(st.session_state.username, agent_name, ticket_id, error_description, st.session_state.user_group)
                                st.success("Mistake reported successfully!")
                                st.rerun()
        
            st.subheader("🔍 Search Mistakes")
            search_query = st.text_input("Search mistakes...")
            mistakes = search_mistakes(search_query, st.session_state.user_group) if search_query else get_mistakes(st.session_state.user_group)
            
            st.subheader("Mistakes Log")
            for mistake in mistakes:
                m_id, tl, agent, ticket, error, ts, group = mistake
                st.markdown(f"""
                <div class="card">
                    <div style="display: flex; justify-content: space-between;">
                        <h4>#{m_id}</h4>
                        <small>{ts}</small>
                    </div>
                    <p>Agent: {agent} (Group: {group})</p>
                    <p>Ticket: {ticket}</p>
                    <p>Error: {error}</p>
                    <p><small>Reported by: {tl}</small></p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.error("System is currently locked. Access to mistakes is disabled.")

    elif st.session_state.current_section == "chat":
        if not is_killswitch_enabled():
            # Add notification permission request
            st.markdown("""
            <div id="notification-container"></div>
            <script>
            // Check if notifications are supported
            if ('Notification' in window) {
                const container = document.getElementById('notification-container');
                if (Notification.permission === 'default') {
                    container.innerHTML = `
                        <div style="padding: 1rem; margin-bottom: 1rem; border-radius: 0.5rem; background-color: #1e293b; border: 1px solid #334155;">
                            <p style="margin: 0; color: #e2e8f0;">Would you like to receive notifications for new messages?</p>
                            <button onclick="requestNotificationPermission()" style="margin-top: 0.5rem; padding: 0.5rem 1rem; background-color: #2563eb; color: white; border: none; border-radius: 0.25rem; cursor: pointer;">
                                Enable Notifications
                            </button>
                        </div>
                    `;
                }
            }

            async function requestNotificationPermission() {
                const permission = await Notification.requestPermission();
                if (permission === 'granted') {
                    document.getElementById('notification-container').style.display = 'none';
                }
            }
            </script>
            """, unsafe_allow_html=True)
            
            if is_chat_killswitch_enabled():
                st.warning("Chat functionality is currently disabled by the administrator.")
            else:
                # Add group filter for admins
                if st.session_state.role == "admin":
                    group_filter = st.selectbox(
                        "Filter by Group", 
                        ["All", "1", "2", "3", "4"],
                        key="chat_group_filter"
                    )
                else:
                    group_filter = st.session_state.user_group if st.session_state.role == "agent" else None
                
                # Get messages with group filter
                if st.session_state.role == "admin" and group_filter != "All":
                    messages = get_group_messages(group_filter)
                else:
                    messages = get_group_messages(st.session_state.user_group)
                
                st.subheader("Group Chat")
                st.markdown('<div class="chat-container">', unsafe_allow_html=True)
                for msg in reversed(messages):
                    msg_id, sender, message, ts, mentions, group = msg
                    is_sent = sender == st.session_state.username
                    is_mentioned = st.session_state.username in (mentions.split(',') if mentions else [])
                    
                    st.markdown(f"""
                    <div class="chat-message {'sent' if is_sent else 'received'}">
                        <div class="message-avatar">
                            {sender[0].upper()}
                        </div>
                        <div class="message-content">
                            <div>{message}</div>
                            <div class="message-meta">{sender} (Group: {group}) • {ts}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
                
                with st.form("chat_form", clear_on_submit=True):
                    message = st.text_input("Type your message...", key="chat_input")
                    col1, col2 = st.columns([5,1])
                    with col2:
                        if st.form_submit_button("Send"):
                            if message:
                                send_group_message(st.session_state.username, message, st.session_state.user_group)
                                st.rerun()
        else:
            st.error("System is currently locked. Access to chat is disabled.")

    elif st.session_state.current_section == "hold":
        if not is_killswitch_enabled():
            st.subheader("🖼️ HOLD Images")
            
            # Only show upload option to admin users
            if st.session_state.role == "admin":
                uploaded_file = st.file_uploader("Upload HOLD Image", type=['png', 'jpg', 'jpeg'])
                if uploaded_file is not None:
                    try:
                        # Convert the file to bytes
                        img_bytes = uploaded_file.getvalue()
                        
                        # Clear existing images before adding new one
                        clear_hold_images()
                        
                        # Add to database
                        if add_hold_image(st.session_state.username, img_bytes):
                            st.success("Image uploaded successfully!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error uploading image: {str(e)}")
            
            # Display images (visible to all users)
            images = get_hold_images()
            if images:
                # Get only the most recent image
                img = images[0]  # Since images are ordered by timestamp DESC
                img_id, uploader, img_data, timestamp = img
                st.markdown(f"""
                <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 20px; border-radius: 5px;">
                    <p><strong>Uploaded by:</strong> {uploader}</p>
                    <p><small>Uploaded at: {timestamp}</small></p>
                </div>
                """, unsafe_allow_html=True)
                try:
                    image = Image.open(io.BytesIO(img_data))
                    st.image(image, use_container_width=True)  # Updated parameter
                except Exception as e:
                    st.error(f"Error displaying image: {str(e)}")
            else:
                st.info("No HOLD images available")
        else:
            st.error("System is currently locked. Access to HOLD images is disabled.")

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
                    try:
                        datetime.strptime(presence_time, "%H:%M")
                        datetime.strptime(login_time, "%H:%M")
                        add_late_login(
                            st.session_state.username,
                            presence_time,
                            login_time,
                            reason,
                            st.session_state.user_group
                        )
                        st.success("Late login reported successfully!")
                    except ValueError:
                        st.error("Invalid time format. Please use HH:MM format (e.g., 08:30)")
        
        st.subheader("Late Login Records")
        late_logins = get_late_logins(st.session_state.user_group)
        
        if st.session_state.role == "admin":
            # Search and date filter only for admin users
            col1, col2 = st.columns([2, 1])
            with col1:
                search_query = st.text_input("🔍 Search late login records...", key="late_login_search")
            with col2:
                date_filter = st.date_input("📅 Filter by date (Casablanca time)", key="late_login_date")
            
            if search_query or date_filter:
                filtered_logins = []
                
                for login in late_logins:
                    matches_search = True
                    matches_date = True
                    
                    if search_query:
                        matches_search = (
                            search_query.lower() in login[1].lower() or  # Agent name
                            search_query.lower() in login[4].lower() or  # Reason
                            search_query in login[2] or  # Presence time
                            search_query in login[3]     # Login time
                        )
                    
                    if date_filter:
                        try:
                            record_date = datetime.strptime(login[5], "%Y-%m-%d %H:%M:%S").date()
                            matches_date = record_date == date_filter
                        except:
                            matches_date = False
                    
                    if matches_search and matches_date:
                        filtered_logins.append(login)
                
                late_logins = filtered_logins
            
            if late_logins:
                data = []
                for login in late_logins:
                    _, agent, presence, login_time, reason, ts, group = login
                    data.append({
                        "Agent's Name": agent,
                        "Group": group,
                        "Time of presence": presence,
                        "Time of log in": login_time,
                        "Reason": reason,
                        "Reported At": ts
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name=f"late_logins_{date_filter.strftime('%Y-%m-%d') if date_filter else 'all'}.csv",
                    mime="text/csv"
                )
                
                if st.button("Clear All Records"):
                    clear_late_logins()
                    st.rerun()
            else:
                st.info("No late login records found")
        else:
            # Regular users only see their own records without search
            user_logins = [login for login in late_logins if login[1] == st.session_state.username]
            if user_logins:
                data = []
                for login in user_logins:
                    _, agent, presence, login_time, reason, ts, group = login
                    data.append({
                        "Time of presence": presence,
                        "Time of log in": login_time,
                        "Reason": reason,
                        "Reported At": ts
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("You have no late login records")

    elif st.session_state.current_section == "fancy_number":
        st.subheader("📱 Fancy Number Checker")
        
        # Input for phone number
        phone_number = st.text_input("Enter Phone Number", placeholder="e.g. +1 (123) 456-7890")
        
        # Check button
        if st.button("Check Fancy Number"):
            if phone_number:
                # Clean the phone number
                cleaned_number = re.sub(r'\D', '', phone_number)
                
                # Check if the last 6 digits form a fancy pattern
                if len(cleaned_number) >= 6:
                    last_six_digits = cleaned_number[-6:]
                    
                    # Check for various fancy patterns
                    is_fancy = (
                        # Repeating digits
                        len(set(last_six_digits)) <= 2 or
                        
                        # Sequential digits
                        last_six_digits in ['123456', '234567', '345678', '456789', '567890'] or
                        last_six_digits in ['654321', '543210', '432109', '321098', '210987'] or
                        
                        # Palindrome
                        last_six_digits == last_six_digits[::-1] or
                        
                        # Special patterns
                        last_six_digits in ['111111', '222222', '333333', '444444', '555555', '666666', '777777', '888888', '999999'] or
                        last_six_digits in ['112233', '223344', '334455', '445566', '556677', '667788', '778899']
                    )
                    
                    if is_fancy:
                        st.success(f"🎉 Fancy Number Found! The last 6 digits ({last_six_digits}) form a fancy pattern.")
                    else:
                        st.info(f"🔍 Not a Fancy Number. The last 6 digits ({last_six_digits}) do not form a special pattern.")
                else:
                    st.warning("Please enter a valid phone number with at least 6 digits.")
            else:
                st.warning("Please enter a phone number.")

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
                            product,
                            st.session_state.user_group
                        )
                        st.success("Quality issue reported successfully!")
                    except ValueError:
                        st.error("Invalid time format. Please use HH:MM format (e.g., 14:30)")
        
        st.subheader("Quality Issue Records")
        quality_issues = get_quality_issues(st.session_state.user_group)
        
        # Allow both admin and QA roles to see all records and use search/filter
        if st.session_state.role in ["admin", "qa"]:
            # Search and date filter for admin and QA users
            col1, col2 = st.columns([2, 1])
            with col1:
                search_query = st.text_input("🔍 Search quality issues...", key="quality_issues_search")
            with col2:
                date_filter = st.date_input("📅 Filter by date (Casablanca time)", key="quality_issues_date")
            
            if search_query or date_filter:
                filtered_issues = []
                
                for issue in quality_issues:
                    matches_search = True
                    matches_date = True
                    
                    if search_query:
                        matches_search = (
                            search_query.lower() in issue[1].lower() or  # Agent name
                            search_query.lower() in issue[2].lower() or  # Issue type
                            search_query in issue[3] or  # Timing
                            search_query in issue[4] or  # Mobile number
                            search_query.lower() in issue[5].lower()  # Product
                        )
                    
                    if date_filter:
                        try:
                            record_date = datetime.strptime(issue[6], "%Y-%m-%d %H:%M:%S").date()
                            matches_date = record_date == date_filter
                        except:
                            matches_date = False
                    
                    if matches_search and matches_date:
                        filtered_issues.append(issue)
                
                quality_issues = filtered_issues
            
            if quality_issues:
                data = []
                for issue in quality_issues:
                    _, agent, issue_type, timing, mobile, product, ts, group = issue
                    data.append({
                        "Agent's Name": agent,
                        "Group": group,
                        "Type of issue": issue_type,
                        "Timing": timing,
                        "Mobile number": mobile,
                        "Product": product,
                        "Reported At": ts
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name=f"quality_issues_{date_filter.strftime('%Y-%m-%d') if date_filter else 'all'}.csv",
                    mime="text/csv"
                )
                
                # Only admin can clear records
                if st.session_state.role == "admin" and st.button("Clear All Records"):
                    clear_quality_issues()
                    st.rerun()
            else:
                st.info("No quality issue records found")
        else:
            # Regular users only see their own records without search
            user_issues = [issue for issue in quality_issues if issue[1] == st.session_state.username]
            if user_issues:
                data = []
                for issue in user_issues:
                    _, agent, issue_type, timing, mobile, product, ts, group = issue
                    data.append({
                        "Type of issue": issue_type,
                        "Timing": timing,
                        "Mobile number": mobile,
                        "Product": product,
                        "Reported At": ts
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
                            end_time,
                            st.session_state.user_group
                        )
                        st.success("Mid-shift issue reported successfully!")
                    except ValueError:
                        st.error("Invalid time format. Please use HH:MM format (e.g., 10:00)")
        
        st.subheader("Mid-shift Issue Records")
        midshift_issues = get_midshift_issues(st.session_state.user_group)
        
        if st.session_state.role == "admin":
            # Search and date filter only for admin users
            col1, col2 = st.columns([2, 1])
            with col1:
                search_query = st.text_input("🔍 Search mid-shift issues...", key="midshift_issues_search")
            with col2:
                date_filter = st.date_input("📅 Filter by date (Casablanca time)", key="midshift_issues_date")
            
            if search_query or date_filter:
                filtered_issues = []
                
                for issue in midshift_issues:
                    matches_search = True
                    matches_date = True
                    
                    if search_query:
                        matches_search = (
                            search_query.lower() in issue[1].lower() or  # Agent name
                            search_query.lower() in issue[2].lower() or  # Issue type
                            search_query in issue[3] or  # Start time
                            search_query in issue[4]     # End time
                        )
                    
                    if date_filter:
                        try:
                            record_date = datetime.strptime(issue[5], "%Y-%m-%d %H:%M:%S").date()
                            matches_date = record_date == date_filter
                        except:
                            matches_date = False
                    
                    if matches_search and matches_date:
                        filtered_issues.append(issue)
                
                midshift_issues = filtered_issues
            
            if midshift_issues:
                data = []
                for issue in midshift_issues:
                    _, agent, issue_type, start_time, end_time, ts, group = issue
                    data.append({
                        "Agent's Name": agent,
                        "Group": group,
                        "Issue Type": issue_type,
                        "Start time": start_time,
                        "End Time": end_time,
                        "Reported At": ts
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download as CSV",
                    data=csv,
                    file_name=f"midshift_issues_{date_filter.strftime('%Y-%m-%d') if date_filter else 'all'}.csv",
                    mime="text/csv"
                )
                
                if st.button("Clear All Records"):
                    clear_midshift_issues()
                    st.rerun()
            else:
                st.info("No mid-shift issue records found")
        else:
            # Regular users only see their own records without search
            user_issues = [issue for issue in midshift_issues if issue[1] == st.session_state.username]
            if user_issues:
                data = []
                for issue in user_issues:
                    _, agent, issue_type, start_time, end_time, ts, group = issue
                    data.append({
                        "Issue Type": issue_type,
                        "Start time": start_time,
                        "End Time": end_time,
                        "Reported At": ts
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
        
        with st.form("data_clear_form"):
            clear_options = {
                "Requests": clear_all_requests,
                "Mistakes": clear_all_mistakes,
                "Chat Messages": clear_all_group_messages,
                "HOLD Images": clear_hold_images,
                "Late Logins": clear_late_logins,
                "Quality Issues": clear_quality_issues,
                "Mid-shift Issues": clear_midshift_issues,
                "ALL System Data": lambda: all([
                    clear_all_requests(),
                    clear_all_mistakes(),
                    clear_all_group_messages(),
                    clear_hold_images(),
                    clear_late_logins(),
                    clear_quality_issues(),
                    clear_midshift_issues()
                ])
            }
            
            # Dropdown for selecting what to clear
            selected_clear_option = st.selectbox(
                "Select Data to Clear", 
                list(clear_options.keys()),
                help="Choose the type of data you want to permanently delete"
            )
            
            # Warning based on selected option
            warning_messages = {
                "Requests": "This will permanently delete ALL requests and their comments!",
                "Mistakes": "This will permanently delete ALL mistakes!",
                "Chat Messages": "This will permanently delete ALL chat messages!",
                "HOLD Images": "This will permanently delete ALL HOLD images!",
                "Late Logins": "This will permanently delete ALL late login records!",
                "Quality Issues": "This will permanently delete ALL quality issue records!",
                "Mid-shift Issues": "This will permanently delete ALL mid-shift issue records!",
                "ALL System Data": "🚨 THIS WILL DELETE EVERYTHING IN THE SYSTEM! 🚨"
            }
            
            # Display appropriate warning
            if selected_clear_option == "ALL System Data":
                st.error(warning_messages[selected_clear_option])
            else:
                st.warning(warning_messages[selected_clear_option])
            
            # Confirmation checkbox for destructive actions
            confirm_clear = st.checkbox(f"I understand and want to clear {selected_clear_option}")
            
            # Submit button
            if st.form_submit_button("Clear Data"):
                if confirm_clear:
                    try:
                        # Call the corresponding clear function
                        if clear_options[selected_clear_option]():
                            st.success(f"{selected_clear_option} deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Deletion failed. Please try again.")
                    except Exception as e:
                        st.error(f"Error during deletion: {str(e)}")
                else:
                    st.warning("Please confirm the deletion by checking the checkbox.")
        
        st.markdown("---")
        st.subheader("User Management")
        if not is_killswitch_enabled():
            # Show add user form to all admins, but with different options
            with st.form("add_user"):
                user = st.text_input("Username")
                pwd = st.text_input("Password", type="password")
                # Allow all admin users to create admin and QA accounts
                if st.session_state.role == 'admin':
                    role = st.selectbox("Role", ["agent", "admin", "qa"])
                    if role == "agent":
                        group = st.selectbox("Group", ["1", "2", "3", "4"])
                    else:
                        group = role  # admin or qa
                else:
                    role = "agent"  # Default role for accounts created by non-admin users
                    st.info("Note: You can only create agent accounts.")
                    group = "1"  # Default group
                
                if st.form_submit_button("Add User"):
                    if user and pwd:
                        add_user(user, pwd, role, group)
                        st.rerun()
        
        st.subheader("Existing Users")
        users = get_all_users()
        
        # Create tabs for different user types
        user_tabs = st.tabs(["All Users", "Admins", "Agents", "QA"])
        
        with user_tabs[0]:
            # All users view
            st.write("### All Users")
            
            # Create a dataframe for better display
            user_data = []
            for uid, uname, urole, ugroup in users:
                user_data.append({
                    "ID": uid,
                    "Username": uname,
                    "Role": urole,
                    "Group": ugroup
                })
            
            df = pd.DataFrame(user_data)
            st.dataframe(df, use_container_width=True)
            
            # User deletion with dropdown
            if st.session_state.username.lower() == "taha kirri":
                # Taha can delete any user
                with st.form("delete_user_form"):
                    st.write("### Delete User")
                    user_to_delete = st.selectbox(
                        "Select User to Delete",
                        [f"{user[0]} - {user[1]} ({user[2]}, Group: {user[3]})" for user in users],
                        key="delete_user_select"
                    )
                    
                    if st.form_submit_button("Delete User") and not is_killswitch_enabled():
                        user_id = int(user_to_delete.split(' - ')[0])
                        if delete_user(user_id):
                            st.success(f"User deleted successfully!")
                            st.rerun()
        
        with user_tabs[1]:
            # Admins view
            admin_users = [user for user in users if user[2] == "admin"]
            st.write(f"### Admin Users ({len(admin_users)})")
            
            admin_data = []
            for uid, uname, urole, ugroup in admin_users:
                admin_data.append({
                    "ID": uid,
                    "Username": uname,
                    "Group": ugroup
                })
            
            if admin_data:
                st.dataframe(pd.DataFrame(admin_data), use_container_width=True)
            else:
                st.info("No admin users found")
        
        with user_tabs[2]:
            # Agents view
            agent_users = [user for user in users if user[2] == "agent"]
            st.write(f"### Agent Users ({len(agent_users)})")
            
            agent_data = []
            for uid, uname, urole, ugroup in agent_users:
                agent_data.append({
                    "ID": uid,
                    "Username": uname,
                    "Group": ugroup
                })
            
            if agent_data:
                st.dataframe(pd.DataFrame(agent_data), use_container_width=True)
                
                # Only admins can delete agent accounts
                with st.form("delete_agent_form"):
                    st.write("### Delete Agent")
                    agent_to_delete = st.selectbox(
                        "Select Agent to Delete",
                        [f"{user[0]} - {user[1]} (Group: {user[3]})" for user in agent_users],
                        key="delete_agent_select"
                    )
                    
                    if st.form_submit_button("Delete Agent") and not is_killswitch_enabled():
                        agent_id = int(agent_to_delete.split(' - ')[0])
                        if delete_user(agent_id):
                            st.success(f"Agent deleted successfully!")
                            st.rerun()
            else:
                st.info("No agent users found")
        
        with user_tabs[3]:
            # QA view
            qa_users = [user for user in users if user[2] == "qa"]
            st.write(f"### QA Users ({len(qa_users)})")
            
            qa_data = []
            for uid, uname, urole, ugroup in qa_users:
                qa_data.append({
                    "ID": uid,
                    "Username": uname,
                    "Group": ugroup
                })
            
            if qa_data:
                st.dataframe(pd.DataFrame(qa_data), use_container_width=True)
            else:
                st.info("No QA users found")

        st.subheader("🔑 Password Management")
        
        # Get all users
        users = get_all_users()
        
        # Filter users based on role
        if st.session_state.username.lower() == "taha kirri":
            # Taha can reset passwords for all users
            with st.form("reset_password_form_admin"):
                st.write("Reset Password for Admin/QA Users")
                admin_qa_users = [user for user in users if user[2] in ["admin", "qa"]]
                selected_admin = st.selectbox(
                    "Select Admin/QA User",
                    [user[1] for user in admin_qa_users],
                    key="admin_select"
                )
                new_admin_pwd = st.text_input("New Password", type="password", key="admin_pwd")
                
                if st.form_submit_button("Reset Password"):
                    if selected_admin and new_admin_pwd:
                        if reset_password(selected_admin, new_admin_pwd):
                            st.success(f"Password reset for {selected_admin}")
                            st.rerun()
        
        # All admins can reset agent passwords
        with st.form("reset_password_form_agent"):
            st.write("Reset Password for Agent Users")
            agent_users = [user for user in users if user[2] == "agent"]
            selected_agent = st.selectbox(
                "Select Agent",
                [user[1] for user in agent_users],
                key="agent_select"
            )
            new_agent_pwd = st.text_input("New Password", type="password", key="agent_pwd")
            
            if st.form_submit_button("Reset Password"):
                if selected_agent and new_agent_pwd:
                    if reset_password(selected_agent, new_agent_pwd):
                        st.success(f"Password reset for {selected_agent}")
                        st.rerun()
        
        st.markdown("---")

    elif st.session_state.current_section == "breaks":
        if st.session_state.role == "admin":
            admin_break_dashboard()
        else:
            agent_break_dashboard()
    
    elif st.session_state.current_section == "fancy_number":
        st.title("📱 Lycamobile Fancy Number Checker")
        st.subheader("Official Policy: Analyzes last 6 digits only for qualifying patterns")

        phone_input = st.text_input("Enter Phone Number", placeholder="e.g., 1555123456 or 44207123456")

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

        debug_mode = st.checkbox("Show test cases", False)
        if debug_mode:
            st.subheader("Test Cases")
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
            
            for number, expected in test_numbers:
                is_fancy, pattern = is_fancy_number(number)
                result = "PASS" if is_fancy == expected else "FAIL"
                color = "green" if result == "PASS" else "red"
                st.write(f"<span style='color:{color}'>{number[-6:]}: {result} ({pattern})</span>", unsafe_allow_html=True)

def get_new_messages(last_check_time):
    """Get new messages since last check"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sender, message, timestamp, mentions 
            FROM group_messages 
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, (last_check_time,))
        return cursor.fetchall()
    finally:
        conn.close()

def handle_message_check():
    if not st.session_state.authenticated:
        return {"new_messages": False, "messages": []}
    
    current_time = datetime.now()
    if 'last_message_check' not in st.session_state:
        st.session_state.last_message_check = current_time
    
    new_messages = get_new_messages(st.session_state.last_message_check.strftime("%Y-%m-%d %H:%M:%S"))
    st.session_state.last_message_check = current_time
    
    if new_messages:
        messages_data = []
        for msg in new_messages:
            msg_id, sender, message, ts, mentions = msg
            if sender != st.session_state.username:  # Don't notify about own messages
                mentions_list = mentions.split(',') if mentions else []
                if st.session_state.username in mentions_list:
                    message = f"@{st.session_state.username} {message}"
                messages_data.append({
                    "sender": sender,
                    "message": message
                })
        return {"new_messages": bool(messages_data), "messages": messages_data}
    return {"new_messages": False, "messages": []}

def convert_to_casablanca_date(date_str):
    """Convert a date string to Casablanca timezone"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        morocco_tz = pytz.timezone('Africa/Casablanca')
        return pytz.UTC.localize(dt).astimezone(morocco_tz).date()
    except:
        return None

def get_date_range_casablanca(date):
    """Get start and end of day in Casablanca time"""
    morocco_tz = pytz.timezone('Africa/Casablanca')
    start = morocco_tz.localize(datetime.combine(date, time.min))
    end = morocco_tz.localize(datetime.combine(date, time.max))
    return start, end

if __name__ == "__main__":
    # Initialize color mode if not set
    if 'color_mode' not in st.session_state:
        st.session_state.color_mode = 'dark'
        
    inject_custom_css()
    
    # Add route for message checking
    if st.query_params.get("check_messages"):
        st.json(handle_message_check())
        st.stop()
    
    st.write("Lyca Management System")
