import streamlit as st
import numpy as np

st.title("Shift Schedule Optimizer")

# Input parameters
calls_forecast = st.slider("Expected Calls per Hour", 50, 500, 200)
service_level = st.slider("Target Service Level (%)", 70, 100, 80)
max_agents = st.slider("Maximum Available Agents", 5, 50, 20)

# Simple Erlang C calculation (simplified)
required_agents = int(calls_forecast / (60 / 3.5) * (service_level/80))  # Simplified formula

st.subheader("Recommended Staffing")
col1, col2 = st.columns(2)
col1.metric("Agents Required", required_agents)
col2.metric("Coverage", f"{min(100, (required_agents/max_agents)*100):.1f}%")

if required_agents > max_agents:
    st.warning("Not enough agents to meet service level target!")
