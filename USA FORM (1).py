import streamlit as st
import pandas as pd
from datetime import datetime, time
import json
import os

# File paths for storing data
BOOKINGS_FILE = "bookings.json"
SETTINGS_FILE = "settings.json"

# Initialize app state
def initialize_app():
    # Default settings if not exists
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "max_per_slot": 3,
            "shifts": {
                "2pm": {
                    "early_tea": {"start": "15:00", "end": "16:30", "slots": ["15:00", "15:15", "15:30", "15:45", "16:00", "16:15", "16:30"]},
                    "lunch": {"start": "18:30", "end": "20:30", "slots": ["18:30", "19:00", "19:30", "20:00", "20:30"]},
                    "late_tea": {"start": "20:45", "end": "21:30", "slots": ["20:45", "21:00", "21:15", "21:30"]},
                },
                "6pm": {
                    "early_tea": {"start": "19:00", "end": "20:45", "slots": ["19:00", "19:15", "19:30", "19:45", "20:00", "20:15", "20:30", "20:45"]},
                    "lunch": {"start": "21:00", "end": "22:30", "slots": ["21:00", "21:30", "22:00", "22:30"]},
                    "late_tea": {"start": "00:00", "end": "01:30", "slots": ["00:00", "00:15", "00:30", "00:45", "01:00", "01:15", "01:30"]},
                }
            }
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_settings, f)
    
    # Create empty bookings file if not exists
    if not os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, "w") as f:
            json.dump({}, f)

# Load data functions
def load_settings():
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def load_bookings():
    with open(BOOKINGS_FILE, "r") as f:
        return json.load(f)

# Save data functions
def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def save_bookings(bookings):
    with open(BOOKINGS_FILE, "w") as f:
        json.dump(bookings, f)

# Add a booking
def add_booking(agent_id, shift, break_type, slot, date):
    bookings = load_bookings()
    
    # Create date key if not exists
    if date not in bookings:
        bookings[date] = {}
    
    # Create shift key if not exists
    if shift not in bookings[date]:
        bookings[date][shift] = {}
    
    # Create break type key if not exists
    if break_type not in bookings[date][shift]:
        bookings[date][shift][break_type] = {}
    
    # Create slot key if not exists
    if slot not in bookings[date][shift][break_type]:
        bookings[date][shift][break_type][slot] = []
    
    # Add booking if not already booked
    if agent_id not in bookings[date][shift][break_type][slot]:
        bookings[date][shift][break_type][slot].append(agent_id)
        save_bookings(bookings)
        return True
    
    return False

# Remove a booking
def remove_booking(agent_id, shift, break_type, slot, date):
    bookings = load_bookings()
    
    # Check if booking exists
    if (date in bookings and shift in bookings[date] and 
        break_type in bookings[date][shift] and 
        slot in bookings[date][shift][break_type] and 
        agent_id in bookings[date][shift][break_type][slot]):
        
        # Remove booking
        bookings[date][shift][break_type][slot].remove(agent_id)
        
        # Clean up empty structures
        if not bookings[date][shift][break_type][slot]:
            del bookings[date][shift][break_type][slot]
        if not bookings[date][shift][break_type]:
            del bookings[date][shift][break_type]
        if not bookings[date][shift]:
            del bookings[date][shift]
        if not bookings[date]:
            del bookings[date]
        
        save_bookings(bookings)
        return True
    
    return False

# Count bookings for a slot
def count_bookings(shift, break_type, slot, date):
    bookings = load_bookings()
    
    try:
        return len(bookings[date][shift][break_type][slot])
    except KeyError:
        return 0

# Get all agent bookings for a date
def get_agent_bookings(agent_id, date):
    bookings = load_bookings()
    agent_bookings = {"2pm": {}, "6pm": {}}
    
    if date in bookings:
        for shift in bookings[date]:
            for break_type in bookings[date][shift]:
                for slot in bookings[date][shift][break_type]:
                    if agent_id in bookings[date][shift][break_type][slot]:
                        if break_type not in agent_bookings[shift]:
                            agent_bookings[shift][break_type] = []
                        agent_bookings[shift][break_type].append(slot)
    
    return agent_bookings

# Check if an agent already has a booking for a break type on a date
def has_break_booking(agent_id, shift, break_type, date):
    agent_bookings = get_agent_bookings(agent_id, date)
    return break_type in agent_bookings[shift]

# Agent Interface
def agent_interface():
    st.header("Break Booking System - Agent View")
    
    # Agent ID input
    agent_id = st.text_input("Enter your Agent ID")
    
    # Date selector
    date = st.date_input("Select Date")
    date_str = date.strftime("%Y-%m-%d")
    
    if not agent_id:
        st.warning("Please enter your Agent ID to proceed.")
        return
    
    # Load current bookings for this agent
    agent_bookings = get_agent_bookings(agent_id, date_str)
    
    # Create tabs for the two shifts
    tab1, tab2 = st.tabs(["2:00 PM Shift", "6:00 PM Shift"])
    
    settings = load_settings()
    max_per_slot = settings["max_per_slot"]
    
    # 2 PM Shift
    with tab1:
        st.subheader("2:00 PM Shift")
        col1, col2, col3 = st.columns(3)
        
        # Early Tea Break
        with col1:
            st.markdown("### Early Tea Break")
            early_tea_booked = "early_tea" in agent_bookings["2pm"]
            
            if early_tea_booked:
                st.success(f"Booked: {', '.join(agent_bookings['2pm']['early_tea'])}")
                if st.button("Cancel Early Tea Booking (2PM)"):
                    for slot in agent_bookings["2pm"]["early_tea"]:
                        remove_booking(agent_id, "2pm", "early_tea", slot, date_str)
                    st.experimental_rerun()
            else:
                early_tea_options = []
                for slot in settings["shifts"]["2pm"]["early_tea"]["slots"]:
                    count = count_bookings("2pm", "early_tea", slot, date_str)
                    if count < max_per_slot:
                        early_tea_options.append(f"{slot} ({count}/{max_per_slot})")
                
                if early_tea_options:
                    selected_early_tea = st.selectbox("Select Early Tea Time (2PM)", early_tea_options)
                    if st.button("Book Early Tea Break (2PM)"):
                        slot = selected_early_tea.split(" ")[0]  # Extract time from display format
                        success = add_booking(agent_id, "2pm", "early_tea", slot, date_str)
                        if success:
                            st.success(f"Booked Early Tea Break at {slot}")
                            st.experimental_rerun()
                        else:
                            st.error("Booking failed. Please try again.")
                else:
                    st.info("No available slots for Early Tea Break")
        
        # Lunch Break
        with col2:
            st.markdown("### Lunch Break")
            lunch_booked = "lunch" in agent_bookings["2pm"]
            
            if lunch_booked:
                st.success(f"Booked: {', '.join(agent_bookings['2pm']['lunch'])}")
                if st.button("Cancel Lunch Booking (2PM)"):
                    for slot in agent_bookings["2pm"]["lunch"]:
                        remove_booking(agent_id, "2pm", "lunch", slot, date_str)
                    st.experimental_rerun()
            else:
                lunch_options = []
                for slot in settings["shifts"]["2pm"]["lunch"]["slots"]:
                    count = count_bookings("2pm", "lunch", slot, date_str)
                    if count < max_per_slot:
                        lunch_options.append(f"{slot} ({count}/{max_per_slot})")
                
                if lunch_options:
                    selected_lunch = st.selectbox("Select Lunch Time (2PM)", lunch_options)
                    if st.button("Book Lunch Break (2PM)"):
                        slot = selected_lunch.split(" ")[0]  # Extract time from display format
                        success = add_booking(agent_id, "2pm", "lunch", slot, date_str)
                        if success:
                            st.success(f"Booked Lunch Break at {slot}")
                            st.experimental_rerun()
                        else:
                            st.error("Booking failed. Please try again.")
                else:
                    st.info("No available slots for Lunch Break")
        
        # Late Tea Break
        with col3:
            st.markdown("### Late Tea Break")
            late_tea_booked = "late_tea" in agent_bookings["2pm"]
            
            if late_tea_booked:
                st.success(f"Booked: {', '.join(agent_bookings['2pm']['late_tea'])}")
                if st.button("Cancel Late Tea Booking (2PM)"):
                    for slot in agent_bookings["2pm"]["late_tea"]:
                        remove_booking(agent_id, "2pm", "late_tea", slot, date_str)
                    st.experimental_rerun()
            else:
                late_tea_options = []
                for slot in settings["shifts"]["2pm"]["late_tea"]["slots"]:
                    count = count_bookings("2pm", "late_tea", slot, date_str)
                    if count < max_per_slot:
                        late_tea_options.append(f"{slot} ({count}/{max_per_slot})")
                
                if late_tea_options:
                    selected_late_tea = st.selectbox("Select Late Tea Time (2PM)", late_tea_options)
                    if st.button("Book Late Tea Break (2PM)"):
                        slot = selected_late_tea.split(" ")[0]  # Extract time from display format
                        success = add_booking(agent_id, "2pm", "late_tea", slot, date_str)
                        if success:
                            st.success(f"Booked Late Tea Break at {slot}")
                            st.experimental_rerun()
                        else:
                            st.error("Booking failed. Please try again.")
                else:
                    st.info("No available slots for Late Tea Break")
    
    # 6 PM Shift
    with tab2:
        st.subheader("6:00 PM Shift")
        col1, col2, col3 = st.columns(3)
        
        # Early Tea Break
        with col1:
            st.markdown("### Early Tea Break")
            early_tea_booked = "early_tea" in agent_bookings["6pm"]
            
            if early_tea_booked:
                st.success(f"Booked: {', '.join(agent_bookings['6pm']['early_tea'])}")
                if st.button("Cancel Early Tea Booking (6PM)"):
                    for slot in agent_bookings["6pm"]["early_tea"]:
                        remove_booking(agent_id, "6pm", "early_tea", slot, date_str)
                    st.experimental_rerun()
            else:
                early_tea_options = []
                for slot in settings["shifts"]["6pm"]["early_tea"]["slots"]:
                    count = count_bookings("6pm", "early_tea", slot, date_str)
                    if count < max_per_slot:
                        early_tea_options.append(f"{slot} ({count}/{max_per_slot})")
                
                if early_tea_options:
                    selected_early_tea = st.selectbox("Select Early Tea Time (6PM)", early_tea_options)
                    if st.button("Book Early Tea Break (6PM)"):
                        slot = selected_early_tea.split(" ")[0]  # Extract time from display format
                        success = add_booking(agent_id, "6pm", "early_tea", slot, date_str)
                        if success:
                            st.success(f"Booked Early Tea Break at {slot}")
                            st.experimental_rerun()
                        else:
                            st.error("Booking failed. Please try again.")
                else:
                    st.info("No available slots for Early Tea Break")
        
        # Lunch Break
        with col2:
            st.markdown("### Lunch Break")
            lunch_booked = "lunch" in agent_bookings["6pm"]
            
            if lunch_booked:
                st.success(f"Booked: {', '.join(agent_bookings['6pm']['lunch'])}")
                if st.button("Cancel Lunch Booking (6PM)"):
                    for slot in agent_bookings["6pm"]["lunch"]:
                        remove_booking(agent_id, "6pm", "lunch", slot, date_str)
                    st.experimental_rerun()
            else:
                lunch_options = []
                for slot in settings["shifts"]["6pm"]["lunch"]["slots"]:
                    count = count_bookings("6pm", "lunch", slot, date_str)
                    if count < max_per_slot:
                        lunch_options.append(f"{slot} ({count}/{max_per_slot})")
                
                if lunch_options:
                    selected_lunch = st.selectbox("Select Lunch Time (6PM)", lunch_options)
                    if st.button("Book Lunch Break (6PM)"):
                        slot = selected_lunch.split(" ")[0]  # Extract time from display format
                        success = add_booking(agent_id, "6pm", "lunch", slot, date_str)
                        if success:
                            st.success(f"Booked Lunch Break at {slot}")
                            st.experimental_rerun()
                        else:
                            st.error("Booking failed. Please try again.")
                else:
                    st.info("No available slots for Lunch Break")
        
        # Late Tea Break
        with col3:
            st.markdown("### Late Tea Break")
            late_tea_booked = "late_tea" in agent_bookings["6pm"]
            
            if late_tea_booked:
                st.success(f"Booked: {', '.join(agent_bookings['6pm']['late_tea'])}")
                if st.button("Cancel Late Tea Booking (6PM)"):
                    for slot in agent_bookings["6pm"]["late_tea"]:
                        remove_booking(agent_id, "6pm", "late_tea", slot, date_str)
                    st.experimental_rerun()
            else:
                late_tea_options = []
                for slot in settings["shifts"]["6pm"]["late_tea"]["slots"]:
                    count = count_bookings("6pm", "late_tea", slot, date_str)
                    if count < max_per_slot:
                        late_tea_options.append(f"{slot} ({count}/{max_per_slot})")
                
                if late_tea_options:
                    selected_late_tea = st.selectbox("Select Late Tea Time (6PM)", late_tea_options)
                    if st.button("Book Late Tea Break (6PM)"):
                        slot = selected_late_tea.split(" ")[0]  # Extract time from display format
                        success = add_booking(agent_id, "6pm", "late_tea", slot, date_str)
                        if success:
                            st.success(f"Booked Late Tea Break at {slot}")
                            st.experimental_rerun()
                        else:
                            st.error("Booking failed. Please try again.")
                else:
                    st.info("No available slots for Late Tea Break")

# Admin Interface
def admin_interface():
    st.header("Break Booking System - Admin View")
    
    # Load settings
    settings = load_settings()
    
    # Create tabs for different admin functions
    tab1, tab2, tab3 = st.tabs(["View Bookings", "Manage Slots", "Settings"])
    
    # Tab 1: View Bookings
    with tab1:
        st.subheader("View All Bookings")
        
        # Date selector
        date = st.date_input("Select Date to View")
        date_str = date.strftime("%Y-%m-%d")
        
        # Load bookings
        bookings = load_bookings()
        
        # Create dataframes for each shift and break type
        if date_str in bookings:
            # 2 PM Shift
            st.markdown("### 2:00 PM Shift")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("#### Early Tea Break")
                if "2pm" in bookings[date_str] and "early_tea" in bookings[date_str]["2pm"]:
                    early_tea_data = []
                    for slot in settings["shifts"]["2pm"]["early_tea"]["slots"]:
                        if slot in bookings[date_str]["2pm"]["early_tea"]:
                            for agent in bookings[date_str]["2pm"]["early_tea"][slot]:
                                early_tea_data.append({"Time": slot, "Agent ID": agent})
                    
                    if early_tea_data:
                        early_tea_df = pd.DataFrame(early_tea_data)
                        st.dataframe(early_tea_df)
                    else:
                        st.info("No bookings for Early Tea Break")
                else:
                    st.info("No bookings for Early Tea Break")
            
            with col2:
                st.markdown("#### Lunch Break")
                if "2pm" in bookings[date_str] and "lunch" in bookings[date_str]["2pm"]:
                    lunch_data = []
                    for slot in settings["shifts"]["2pm"]["lunch"]["slots"]:
                        if slot in bookings[date_str]["2pm"]["lunch"]:
                            for agent in bookings[date_str]["2pm"]["lunch"][slot]:
                                lunch_data.append({"Time": slot, "Agent ID": agent})
                    
                    if lunch_data:
                        lunch_df = pd.DataFrame(lunch_data)
                        st.dataframe(lunch_df)
                    else:
                        st.info("No bookings for Lunch Break")
                else:
                    st.info("No bookings for Lunch Break")
            
            with col3:
                st.markdown("#### Late Tea Break")
                if "2pm" in bookings[date_str] and "late_tea" in bookings[date_str]["2pm"]:
                    late_tea_data = []
                    for slot in settings["shifts"]["2pm"]["late_tea"]["slots"]:
                        if slot in bookings[date_str]["2pm"]["late_tea"]:
                            for agent in bookings[date_str]["2pm"]["late_tea"][slot]:
                                late_tea_data.append({"Time": slot, "Agent ID": agent})
                    
                    if late_tea_data:
                        late_tea_df = pd.DataFrame(late_tea_data)
                        st.dataframe(late_tea_df)
                    else:
                        st.info("No bookings for Late Tea Break")
                else:
                    st.info("No bookings for Late Tea Break")
            
            # 6 PM Shift
            st.markdown("### 6:00 PM Shift")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("#### Early Tea Break")
                if "6pm" in bookings[date_str] and "early_tea" in bookings[date_str]["6pm"]:
                    early_tea_data = []
                    for slot in settings["shifts"]["6pm"]["early_tea"]["slots"]:
                        if slot in bookings[date_str]["6pm"]["early_tea"]:
                            for agent in bookings[date_str]["6pm"]["early_tea"][slot]:
                                early_tea_data.append({"Time": slot, "Agent ID": agent})
                    
                    if early_tea_data:
                        early_tea_df = pd.DataFrame(early_tea_data)
                        st.dataframe(early_tea_df)
                    else:
                        st.info("No bookings for Early Tea Break")
                else:
                    st.info("No bookings for Early Tea Break")
            
            with col2:
                st.markdown("#### Lunch Break")
                if "6pm" in bookings[date_str] and "lunch" in bookings[date_str]["6pm"]:
                    lunch_data = []
                    for slot in settings["shifts"]["6pm"]["lunch"]["slots"]:
                        if slot in bookings[date_str]["6pm"]["lunch"]:
                            for agent in bookings[date_str]["6pm"]["lunch"][slot]:
                                lunch_data.append({"Time": slot, "Agent ID": agent})
                    
                    if lunch_data:
                        lunch_df = pd.DataFrame(lunch_data)
                        st.dataframe(lunch_df)
                    else:
                        st.info("No bookings for Lunch Break")
                else:
                    st.info("No bookings for Lunch Break")
            
            with col3:
                st.markdown("#### Late Tea Break")
                if "6pm" in bookings[date_str] and "late_tea" in bookings[date_str]["6pm"]:
                    late_tea_data = []
                    for slot in settings["shifts"]["6pm"]["late_tea"]["slots"]:
                        if slot in bookings[date_str]["6pm"]["late_tea"]:
                            for agent in bookings[date_str]["6pm"]["late_tea"][slot]:
                                late_tea_data.append({"Time": slot, "Agent ID": agent})
                    
                    if late_tea_data:
                        late_tea_df = pd.DataFrame(late_tea_data)
                        st.dataframe(late_tea_df)
                    else:
                        st.info("No bookings for Late Tea Break")
                else:
                    st.info("No bookings for Late Tea Break")
        else:
            st.info(f"No bookings found for {date_str}")
    
    # Tab 2: Manage Slots
    with tab2:
        st.subheader("Manage Break Slots")
        
        shift_option = st.selectbox("Select Shift", ["2pm", "6pm"])
        break_type_option = st.selectbox("Select Break Type", ["early_tea", "lunch", "late_tea"])
        
        # Display current slots
        current_slots = settings["shifts"][shift_option][break_type_option]["slots"]
        st.write("Current Slots:")
        st.write(", ".join(current_slots))
        
        # Edit slots
        new_slots = st.text_area("Edit Slots (comma-separated times in 24-hour format, e.g., 15:00, 15:15)", 
                                value=", ".join(current_slots))
        
        if st.button("Update Slots"):
            try:
                # Parse and validate slots
                slots_list = [slot.strip() for slot in new_slots.split(",")]
                
                # Simple validation of time format
                for slot in slots_list:
                    # Check if time format is valid (HH:MM)
                    parts = slot.split(":")
                    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                        raise ValueError(f"Invalid time format: {slot}")
                    
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    
                    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                        raise ValueError(f"Invalid time: {slot}")
                
                # Update settings
                settings["shifts"][shift_option][break_type_option]["slots"] = slots_list
                save_settings(settings)
                st.success(f"Slots updated for {shift_option} shift {break_type_option}!")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error updating slots: {str(e)}")
    
    # Tab 3: Settings
    with tab3:
        st.subheader("System Settings")
        
        # Max bookings per slot
        max_per_slot = st.number_input("Maximum Bookings Per Slot", 
                                       min_value=1, 
                                       max_value=20, 
                                       value=settings["max_per_slot"])
        
        if st.button("Update Max Bookings"):
            settings["max_per_slot"] = int(max_per_slot)
            save_settings(settings)
            st.success(f"Maximum bookings per slot updated to {max_per_slot}!")
            st.experimental_rerun()
        
        # Bulk delete bookings
        st.markdown("### Delete All Bookings for a Date")
        delete_date = st.date_input("Select Date to Delete")
        delete_date_str = delete_date.strftime("%Y-%m-%d")
        
        if st.button("Delete All Bookings", type="primary", use_container_width=True):
            bookings = load_bookings()
            if delete_date_str in bookings:
                del bookings[delete_date_str]
                save_bookings(bookings)
                st.success(f"All bookings for {delete_date_str} have been deleted!")
            else:
                st.info(f"No bookings found for {delete_date_str}")

# Main app
def main():
    st.set_page_config(page_title="Break Booking System", layout="wide")
    
    # Initialize app data
    initialize_app()
    
    # App title
    st.title("Break Booking System")
    
    # Create sidebar for navigation
    with st.sidebar:
        st.header("Navigation")
        app_mode = st.radio("Select Mode", ["Agent", "Admin"])
    
    # Show the appropriate interface
    if app_mode == "Agent":
        agent_interface()
    else:
        # Admin authentication (simple password for demo)
        admin_password = st.sidebar.text_input("Admin Password", type="password")
        if admin_password == "admin123":  # In a real app, use a more secure authentication system
            admin_interface()
        else:
            st.warning("Please enter the admin password to access the admin panel.")

if __name__ == "__main__":
    main()
