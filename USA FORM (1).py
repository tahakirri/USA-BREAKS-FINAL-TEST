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
    intensity = calls * (aht/3600)
    agents = math.ceil(agents)
    
    # Prevent division by zero/negative agents
    if agents <= 0 or intensity <= 0:
        return 0.0
    
    sum_series = sum([(intensity**n)/math.factorial(n) for n in range(agents)])
    erlang_b = (intensity**agents)/math.factorial(agents)
    pw = erlang_b / (erlang_b + (1 - (intensity/agents)) * sum_series)
    
    # Handle extreme understaffing
    if (agents - intensity) < 0:
        return 0.0  # Or "Overloaded" as a string
    
    sl = 1 - (pw * math.exp(-(agents - intensity) * (target_answer_time/aht)))
    return max(0.0, sl * 100)  # Cap at 0%

# Find required agents to meet SLA
def find_required_agents(calls, aht, target_sla):
    agents = calls * (aht/3600)  # Start with minimum possible
    while True:
        sl = erlang_c(agents, calls, aht)
        if sl >= target_sla or agents > 100:  # Prevent infinite loop
            break
        agents += 0.1  # Small increments for precision
    return math.ceil(agents)

# Calculate call abandonment rate (simplified model)
def estimate_abandonment_rate(agents_available, calls, aht, target_sla):
    required_agents = find_required_agents(calls, aht, target_sla)
    if agents_available >= required_agents:
        return 0
    
    # Simplified model: abandonment increases with understaffing
    understaffing_ratio = (required_agents - agents_available) / required_agents
    base_abandonment = 0.05  # 5% base abandonment rate
    max_abandonment = 0.35   # 35% maximum abandonment rate
    
    return min(max_abandonment, base_abandonment + (understaffing_ratio * 0.3))

# Calculate with current and target AHT
required_agents_current = find_required_agents(calls_forecast, current_aht, service_level_target)
required_agents_target = find_required_agents(calls_forecast, target_aht, service_level_target)

# Calculate additional agents needed
additional_agents_current = max(0, required_agents_current - max_agents)
additional_agents_target = max(0, required_agents_target - max_agents)

# Calculate coverage
coverage_current = min(100, (max_agents / required_agents_current) * 100)
coverage_target = min(100, (max_agents / required_agents_target) * 100)

# Calculate call loss
abandonment_rate_current = estimate_abandonment_rate(max_agents, calls_forecast, current_aht, service_level_target)
call_loss_current = int(calls_forecast * abandonment_rate_current)

abandonment_rate_target = estimate_abandonment_rate(max_agents, calls_forecast, target_aht, service_level_target)
call_loss_target = int(calls_forecast * abandonment_rate_target)

# Display results
st.header("Optimization Results")

st.subheader("With Current AHT")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Additional Agents Needed", additional_agents_current, 
            f"Total: {required_agents_current} agents")
col2.metric("Projected SLA", f"{erlang_c(max_agents, calls_forecast, current_aht):.1f}%")
col3.metric("Coverage", f"{coverage_current:.1f}%", 
            "Understaffed" if coverage_current < 100 else "Fully utilized")
col4.metric("Expected Call Loss", f"{call_loss_current} calls/hour", 
            delta=f"{abandonment_rate_current*100:.1f}% abandonment")

st.subheader("With Target AHT")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Additional Agents Needed", additional_agents_target, 
            f"Total: {required_agents_target} agents")
col2.metric("Projected SLA", f"{erlang_c(max_agents, calls_forecast, target_aht):.1f}%")
col3.metric("Coverage", f"{coverage_target:.1f}%", 
            "Understaffed" if coverage_target < 100 else "Fully utilized")
col4.metric("Expected Call Loss", f"{call_loss_target} calls/hour", 
            delta=f"{abandonment_rate_target*100:.1f}% abandonment")

# AHT Impact Analysis
st.header("AHT Impact Analysis")
st.write(f"Reducing AHT from {current_aht}s to {target_aht}s would allow you to:")
st.write(f"- Reduce additional agents needed from {additional_agents_current} to {additional_agents_target}")
st.write(f"- Lower total staffing requirement from {required_agents_current} to {required_agents_target} agents")
st.write(f"- Improve your coverage from {coverage_current:.1f}% to {coverage_target:.1f}%")
st.write(f"- Reduce call abandonment from {abandonment_rate_current*100:.1f}% to {abandonment_rate_target*100:.1f}%")
st.write(f"- Save approximately {call_loss_current - call_loss_target} calls/hour from being lost")
st.write(f"- Potentially handle {math.floor(calls_forecast * (current_aht/target_aht))} calls/hour with the same staff")

# Explanation of Coverage and Call Loss
st.header("Understanding the Metrics")
with st.expander("Detailed Explanation"):
    st.write("""
    **Coverage** in call center staffing refers to the percentage of your required staffing that you actually have available.
    
    - **100% Coverage**: You have exactly the number of agents needed to meet your service level target
    - **Below 100%**: You're understaffed and likely to miss your service level targets
    - **Above 100%**: You have more staff than needed (which may be good for unexpected spikes)
    
    **Call Loss/Abandonment** occurs when callers hang up before reaching an agent. Key factors:
    
    - Higher understaffing leads to longer wait times and more abandonments
    - Typical call centers see 5-15% abandonment rates when understaffed
    - Our model estimates abandonment based on your understaffing level
    
    The formula for coverage is:
    ```
    Coverage = (Available Agents / Required Agents) × 100
    ```
    
    The abandonment estimation is based on:
    ```
    Base Abandonment (5%) + (Understaffing Ratio × 30%)
    ```
    (capped at 35% maximum abandonment)
    """)
