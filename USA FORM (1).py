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
        cursor.execute("SELECT role FROM users WHERE LOWER(username) = LOWER(?) AND password = ?", 
                      (username, hashed_password))
        result = cursor.fetchone()
        return result[0] if result else None
    finally:
        conn.close()

def add_group(name, description=''):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO groups (name, description) 
            VALUES (?, ?)
        """, (name, description))
        conn.commit()
        st.success(f"Group {name} added successfully!")
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        st.error(f"Group {name} already exists!")
        return None
    finally:
        conn.close()

def get_groups():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description FROM groups")
        return cursor.fetchall()
    finally:
        conn.close()

def add_user(username, password, role, group_id=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        hashed_password = hash_password(password)
        cursor.execute("""
            INSERT INTO users (username, password, role, group_id) 
            VALUES (?, ?, ?, ?)
        """, (username, hashed_password, role, group_id))
        conn.commit()
        st.success(f"User {username} added successfully!")
    except sqlite3.IntegrityError:
        st.error(f"User {username} already exists!")
    finally:
        conn.close()

def update_user_group(username, group_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET group_id = ? 
            WHERE username = ?
        """, (group_id, username))
        conn.commit()
        st.success(f"Updated group for user {username}")
    except Exception as e:
        st.error(f"Error updating group: {str(e)}")
    finally:
        conn.close()

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Create groups table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT
            )
        """)
        
        # Create tables if they don't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT CHECK(role IN ('agent', 'admin', 'qa')),
                group_id INTEGER,
                FOREIGN KEY(group_id) REFERENCES groups(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vip_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                mentions TEXT
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
                completed INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_leader TEXT,
                agent_name TEXT,
                ticket_id TEXT,
                error_description TEXT,
                timestamp TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                message TEXT,
                timestamp TEXT,
                mentions TEXT
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
                timestamp TEXT
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
                timestamp TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS midshift_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT,
                issue_type TEXT,
                start_time TEXT,
                end_time TEXT,
                timestamp TEXT
            )
        """)
        
        # Create default admin account
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password, role) 
            VALUES (?, ?, ?)
        """, ("taha kirri", hash_password("arise@99"), "admin"))
        
        # Create other admin accounts
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
        
        # Create agent accounts
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
        timestamp = get_casablanca_time()
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

def get_requests(group_id=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group_id is not None:
            # Get requests for a specific group
            cursor.execute("""
                SELECT r.* FROM requests r
                JOIN users u ON r.agent_name = u.username
                WHERE u.group_id = ?
                ORDER BY r.timestamp DESC
            """, (group_id,))
        else:
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
        """, (team_leader, agent_name, ticket_id, error_description, get_casablanca_time()))
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
        timestamp = get_casablanca_time()
        
        # Get sender's group
        cursor.execute("SELECT group_id FROM users WHERE username = ?", (sender,))
        group_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO group_messages (sender, message, timestamp) 
            VALUES (?, ?, ?)
        """, (sender, message, timestamp))
        conn.commit()
    except Exception as e:
        st.error(f"Error sending message: {str(e)}")
    finally:
        conn.close()

def get_group_messages(group_id=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if group_id is not None:
            # Get the current user's group if not specified
            cursor.execute("""
                SELECT sender, message, timestamp 
                FROM group_messages gm
                JOIN users u ON gm.sender = u.username
                WHERE u.group_id = ? 
                ORDER BY timestamp DESC LIMIT 100
            """, (group_id,))
        else:
            cursor.execute("SELECT sender, message, timestamp FROM group_messages ORDER BY timestamp DESC LIMIT 100")
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

def add_user(username, password, role, group_id=None):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role, group_id) VALUES (?, ?, ?, ?)",
                      (username, hash_password(password), role, group_id))
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
        return cursor.fetchall()
    finally:
        conn.close()

def clear_hold_images():
    """Clear all hold images from the database"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM hold_images
        """)
        conn.commit()
        return cursor.rowcount  # Return number of images deleted
    except sqlite3.Error as e:
        print(f"Error clearing hold images: {e}")
        return 0
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
        
        # Get sender's group
        cursor.execute("SELECT group_id FROM users WHERE username = ?", (sender,))
        group_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO group_messages (sender, message, timestamp, mentions) 
            VALUES (?, ?, ?, ?)
        """, (sender, message, get_casablanca_time(), ','.join(mentions)))
        conn.commit()
        return True
    finally:
        conn.close()

def get_vip_messages():
    """Get messages from the VIP-only chat"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vip_messages ORDER BY timestamp DESC")
        return cursor.fetchall()
    finally:
        conn.close()", unsafe_allow_html=True)
        else:
            st.error("System is currently locked. Access to mistakes is disabled.")

    elif st.session_state.current_section == "chat":
        if not is_killswitch_enabled():
            # Add notification permission request
            st.markdown('''
            <div id="notification-container"></div>
            <script>
                function requestNotificationPermission() {
                    if (Notification.permission !== 'granted') {
                        Notification.requestPermission().then(function(permission) {
                            if (permission === 'granted') {
                                document.getElementById('notification-container').innerHTML = 'Notifications enabled!';
                            }
                        });
                    }
                }
                requestNotificationPermission();
            </script>
            <div>
                <p style="margin: 0; color: #e2e8f0;">Would you like to receive notifications for new messages?</p>
                <button onclick="requestNotificationPermission()" style="margin-top: 0.5rem; padding: 0.5rem 1rem; background-color: #2563eb; color: white; border: none; border-radius: 0.25rem; cursor: pointer;">
                    Enable Notifications
                </button>
            </div>
            ''', unsafe_allow_html=True)
{{ ... }}
                df = pd.DataFrame(data)
                st.dataframe(df)
            else:
                st.info("You have no mid-shift issue records")

    elif st.session_state.current_section == "admin" and st.session_state.role == "admin":
        if st.session_state.username.lower() == "taha kirri":
            st.subheader("🚨 System Killswitch")
            current = is_killswitch_enabled()
            status = "🔴 ACTIVE" if current else "🟢 INACTIVE"
            st.write(f"Current Killswitch Status: {status}")
            
            with st.form("killswitch_form"):
                enable_switch = st.checkbox("Enable Killswitch", value=current)
                submitted = st.form_submit_button("Update Killswitch")
                if submitted:
                    toggle_killswitch(enable_switch)
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
                # Only show role selection to taha kirri, others can only create agent accounts
                if st.session_state.username.lower() == "taha kirri":
                    role = st.selectbox("Role", ["agent", "admin", "qa"])
                else:
                    role = "agent"  # Default role for accounts created by other admins
                    st.info("Note: New accounts will be created as agent accounts.")
                
                if st.form_submit_button("Add User"):
                    if user and pwd:
                        add_user(user, pwd, role)
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
            for uid, uname, urole in users:
                user_data.append({
                    "ID": uid,
                    "Username": uname,
                    "Role": urole
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
                        [f"{user[0]} - {user[1]} ({user[2]})" for user in users],
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
            for uid, uname, urole in admin_users:
                admin_data.append({
                    "ID": uid,
                    "Username": uname
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
            for uid, uname, urole in agent_users:
                agent_data.append({
                    "ID": uid,
                    "Username": uname
                })
            
            if agent_data:
                st.dataframe(pd.DataFrame(agent_data), use_container_width=True)
                
                # Only admins can delete agent accounts
                with st.form("delete_agent_form"):
                    st.write("### Delete Agent")
                    agent_to_delete = st.selectbox(
                        "Select Agent to Delete",
                        [f"{user[0]} - {user[1]}" for user in agent_users],
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
            for uid, uname, urole in qa_users:
                qa_data.append({
                    "ID": uid,
                    "Username": uname
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
        st.title(" Lycamobile Fancy Number Checker")
        st.subheader("Official Policy: Analyzes last 6 digits only for qualifying patterns")

        phone_input = st.text_input("Enter Phone Number", placeholder="e.g., 1555123456 or 44207123456")

        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button(" Check Number"):
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
                            <h3><span class="fancy-number"> {formatted_num} </span></h3>
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
