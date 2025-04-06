import streamlit as st
import numpy as np
import math

st.title("Call Center Schedule Optimizer with AHT Analysis")

# Input parameters
st.header("Input Parameters")
col1, col2 = st.columns(2)

with col1:
    calls_forecast = st.slider("Expected Calls per Hour", 50, 500, 200)
    service_level_target = st.slider("Target Service Level (%)", 70, 100, 80)
    max_agents = st.slider("Maximum Available Agents", 5, 50, 20)
    
with col2:
    current_aht = st.slider("Current AHT (seconds)", 120, 600, 300)
    target_aht = st.slider("Target AHT (seconds)", 120, 600, 240)
    target_answer_time = st.slider("Target Answer Time (seconds)", 10, 180, 30)

# Erlang C calculation (more accurate version)
def erlang_c(agents, calls, aht):
    intensity = calls * (aht/3600)  # Convert AHT to hours
    agents = math.ceil(agents)
    
    # Calculate probability of wait
    sum_series = sum([(intensity**n)/math.factorial(n) for n in range(agents)])
    erlang_b = (intensity**agents)/math.factorial(agents)
    pw = erlang_b / (erlang_b + (1 - (intensity/agents)) * sum_series)
    
    # Calculate service level
    sl = 1 - (pw * math.exp(-(agents - intensity) * (target_answer_time/aht)))
    
    return sl * 100  # Return as percentage

# Find required agents to meet SLA
def find_required_agents(calls, aht, target_sla):
    agents = calls * (aht/3600)  # Start with minimum possible
    while True:
        sl = erlang_c(agents, calls, aht)
        if sl >= target_sla or agents > 100:  # Prevent infinite loop
            break
        agents += 0.1  # Small increments for precision
    return math.ceil(agents)

# Calculate with current and target AHT
required_agents_current = find_required_agents(calls_forecast, current_aht, service_level_target)
required_agents_target = find_required_agents(calls_forecast, target_aht, service_level_target)

# Calculate coverage
coverage_current = min(100, (required_agents_current / max_agents) * 100)
coverage_target = min(100, (required_agents_target / max_agents) * 100)

# Display results
st.header("Optimization Results")

st.subheader("With Current AHT")
col1, col2, col3 = st.columns(3)
col1.metric("Agents Required", required_agents_current)
col2.metric("Projected SLA", f"{erlang_c(required_agents_current, calls_forecast, current_aht):.1f}%")
col3.metric("Coverage", f"{coverage_current:.1f}%", 
            "Overstaffed" if coverage_current < 100 else "Fully utilized")

st.subheader("With Target AHT")
col1, col2, col3 = st.columns(3)
col1.metric("Agents Required", required_agents_target)
col2.metric("Projected SLA", f"{erlang_c(required_agents_target, calls_forecast, target_aht):.1f}%")
col3.metric("Coverage", f"{coverage_target:.1f}%", 
            "Overstaffed" if coverage_target < 100 else "Fully utilized")

# AHT Impact Analysis
st.header("AHT Impact Analysis")
st.write(f"Reducing AHT from {current_aht}s to {target_aht}s would allow you to:")
st.write(f"- Handle the same volume with {required_agents_current - required_agents_target} fewer agents")
st.write(f"- Improve your coverage from {coverage_current:.1f}% to {coverage_target:.1f}%")
st.write(f"- Potentially handle {math.floor(calls_forecast * (current_aht/target_aht))} calls/hour with the same staff")

# Explanation of Coverage
st.header("What Does Coverage Mean?")
with st.expander("Understanding Coverage Metrics"):
    st.write("""
    **Coverage** in call center staffing refers to the percentage of your required staffing that you actually have available.
    
    - **100% Coverage**: You have exactly the number of agents needed to meet your service level target
    - **Below 100%**: You're understaffed and likely to miss your service level targets
    - **Above 100%**: You have more staff than needed (which may be good for unexpected spikes)
    
    The formula is:
    ```
    Coverage = (Available Agents / Required Agents) × 100
    ```
    
    Higher coverage means better ability to handle calls promptly. Lower coverage means longer wait times and potentially lower service levels.
    """)
