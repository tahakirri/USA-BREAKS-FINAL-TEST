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

# --------------------------
# Break Management Functions
# --------------------------

def add_break_slot(break_name, start_time, end_time, max_users, product, created_by):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO breaks (break_name, start_time, end_time, max_users, product, created_by, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (break_name, start_time, end_time, max_users, product, created_by,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True
    finally:
        conn.close()

def update_break_slot(break_id, break_name, start_time, end_time, max_users, product):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE breaks 
            SET break_name = ?, start_time = ?, end_time = ?, max_users = ?, product = ?
            WHERE id = ?
        """, (break_name, start_time, end_time, max_users, product, break_id))
        conn.commit()
        return True
    finally:
        conn.close()

def get_all_break_slots():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM breaks ORDER BY break_name, start_time")
        return cursor.fetchall()
    finally:
        conn.close()

def get_available_break_slots(date, product=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if product:
            cursor.execute("""
                SELECT b.* 
                FROM breaks b
                LEFT JOIN (
                    SELECT break_id, COUNT(*) as booking_count
                    FROM break_bookings 
                    WHERE booking_date = ?
                    GROUP BY break_id
                ) bb ON b.id = bb.break_id
                WHERE (b.max_users > IFNULL(bb.booking_count, 0)) 
                AND (b.product = ? OR b.product IS NULL)
                ORDER BY b.break_name, b.start_time
            """, (date, product))
        else:
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
                ORDER BY b.break_name, b.start_time
            """, (date,))
        return cursor.fetchall()
    finally:
        conn.close()

def book_break_slot(break_id, user_id, username, product, booking_date):
    if is_killswitch_enabled():
        st.error("System is currently locked. Please contact the developer.")
        return False
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO break_bookings (break_id, user_id, username, product, booking_date, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (break_id, user_id, username, product, booking_date,
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

def get_user_product(username):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        return result[0] if result else None
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
            # Clear existing breaks (optional - you might want to keep them)
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
                )
            
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

# --------------------------
# Streamlit Break Management UI
# --------------------------

def show_breaks_section():
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
