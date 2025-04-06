import streamlit as st
import numpy as np
import math

# Configure page layout
st.set_page_config(layout="wide", page_title="Call Center Optimizer")

# Custom CSS for full-width and better styling
st.markdown("""
<style>
    /* Main container padding */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 5rem;
        padding-right: 5rem;
    }
    
    /* Metric boxes styling */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px 15px 15px 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    
    /* Understaffed warning */
    .understaffed {
        color: #d62728 !important;
        font-weight: bold !important;
    }
    
    /* Header styling */
    h1, h2, h3 {
        color: #2c3e50;
    }
    
    /* Slider labels */
    .stSlider label {
        font-weight: bold;
    }
    
    /* Columns spacing */
    .stColumn {
        padding: 0 15px;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("📊 Call Center Schedule Optimizer with AHT Analysis")
st.markdown("""
This tool helps you optimize your call center staffing by analyzing the impact of Average Handle Time (AHT) 
on service levels, required staffing, and call abandonment rates.
""")

# Input parameters section
st.header("🔧 Input Parameters")
input_col1, input_col2, input_col3 = st.columns(3)

with input_col1:
    st.subheader("Call Volume")
    calls_forecast = st.slider("Expected Calls per Hour", 50, 500, 200, 
                              help="The number of calls you expect to receive in one hour")
    
with input_col2:
    st.subheader("Service Targets")
    service_level_target = st.slider("Target Service Level (%)", 70, 100, 80,
                                   help="Percentage of calls to be answered within target time")
    target_answer_time = st.slider("Target Answer Time (seconds)", 10, 180, 30,
                                 help="Maximum acceptable wait time for service level calculation")
    
with input_col3:
    st.subheader("Staffing & AHT")
    max_agents = st.slider("Maximum Available Agents", 5, 50, 20,
                          help="Number of agents you can deploy")
    current_aht = st.slider("Current AHT (seconds)", 120, 600, 300,
                           help="Your current Average Handle Time per call")
    target_aht = st.slider("Target AHT (seconds)", 120, 600, 240,
                          help="Your desired Average Handle Time after improvements")

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
        return 0.0
    
    sl = 1 - (pw * math.exp(-(agents - intensity) * (target_answer_time/aht)))
    return max(0.0, sl * 100)

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

# Display results in a tabbed interface
st.header("📈 Optimization Results")
tab1, tab2 = st.tabs(["Current AHT Scenario", "Target AHT Scenario"])

with tab1:
    st.subheader(f"Current AHT: {current_aht} seconds")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Required Agents", 
               f"{required_agents_current}",
               f"{additional_agents_current} additional needed",
               help="Total agents needed to meet your service level target")
    
    col2.metric("Projected Service Level", 
               f"{erlang_c(max_agents, calls_forecast, current_aht):.1f}%",
               f"Target: {service_level_target}%",
               help="Expected service level with current staffing")
    
    coverage_delta = f"{coverage_current:.1f}% (Understaffed)" if coverage_current < 100 else f"{coverage_current:.1f}% (Optimal)"
    col3.metric("Staffing Coverage", 
               coverage_delta,
               help="Percentage of required staffing you currently have")
    
    col4.metric("Expected Call Loss", 
               f"{call_loss_current} calls/hour",
               f"{abandonment_rate_current*100:.1f}% abandonment rate",
               delta_color="inverse",
               help="Calls likely to be abandoned due to understaffing")

with tab2:
    st.subheader(f"Target AHT: {target_aht} seconds")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("Required Agents", 
               f"{required_agents_target}",
               f"{additional_agents_target} additional needed",
               help="Total agents needed to meet your service level target with improved AHT")
    
    col2.metric("Projected Service Level", 
               f"{erlang_c(max_agents, calls_forecast, target_aht):.1f}%",
               f"Target: {service_level_target}%",
               help="Expected service level with current staffing and improved AHT")
    
    coverage_delta = f"{coverage_target:.1f}% (Understaffed)" if coverage_target < 100 else f"{coverage_target:.1f}% (Optimal)"
    col3.metric("Staffing Coverage", 
               coverage_delta,
               help="Percentage of required staffing you currently have with improved AHT")
    
    col4.metric("Expected Call Loss", 
               f"{call_loss_target} calls/hour",
               f"{abandonment_rate_target*100:.1f}% abandonment rate",
               delta_color="inverse",
               help="Calls likely to be abandoned due to understaffing with improved AHT")

# AHT Impact Analysis
st.header("📊 AHT Impact Comparison")
impact_col1, impact_col2 = st.columns(2)

with impact_col1:
    st.subheader("Staffing Impact")
    st.metric("Total Agents Needed", 
             f"{required_agents_target} (vs {required_agents_current})",
             delta=f"{required_agents_current - required_agents_target} agents saved",
             delta_color="inverse")
    st.metric("Additional Agents Needed", 
             f"{additional_agents_target} (vs {additional_agents_current})",
             delta=f"{additional_agents_current - additional_agents_target} less needed",
             delta_color="inverse")
    
with impact_col2:
    st.subheader("Performance Impact")
    st.metric("Call Loss Reduction", 
             f"{call_loss_target} (vs {call_loss_current}) calls/hour",
             delta=f"{call_loss_current - call_loss_target} fewer lost calls",
             delta_color="inverse")
    st.metric("Capacity Increase", 
             f"{math.floor(calls_forecast * (current_aht/target_aht))} (vs {calls_forecast}) calls/hour",
             delta=f"{math.floor(calls_forecast * (current_aht/target_aht) - calls_forecast)} more calls possible",
             delta_color="normal")

# Key takeaways
st.header("🎯 Key Takeaways")
if target_aht < current_aht:
    st.success(f"""
    Reducing AHT from {current_aht}s to {target_aht}s would allow you to:
    - **Save {required_agents_current - required_agents_target} agents** while maintaining service levels
    - **Handle (math.floor(calls_forecast * (current_aht/target_aht) - calls_forecast) more calls per hour** with the same staff
    - **Reduce abandoned calls by {call_loss_current - call_loss_target} calls per hour**
    - **Improve staffing coverage by {coverage_target - coverage_current:.1f} percentage points**
    """)
else:
    st.warning("""
    Your target AHT is not lower than current AHT. To see benefits from AHT reduction, 
    set a target AHT that's lower than your current AHT.
    """)

# Methodology explanation
with st.expander("📖 Methodology & Formulas"):
    st.markdown("""
    ### Erlang C Formula
    The Erlang C formula calculates the probability that a call has to wait (Pw):
    
    ```
    Pw = ( (A^N / N!) * (N / (N - A)) ) / ( sum(i=0 to N-1) (A^i / i!) + (A^N / N!) * (N / (N - A)) )
    ```
    Where:
    - A = Traffic intensity (calls/hour × AHT in hours)
    - N = Number of agents
    
    Service Level is then calculated as:
    ```
    SL = 1 - (Pw × e^(-(N - A) × (TargetAnswerTime/AHT)))
    ```
    
    ### Abandonment Rate Estimation
    The abandonment rate is estimated based on understaffing:
    ```
    Abandonment Rate = min(35%, 5% + (30% × UnderstaffingRatio))
    Understaffing Ratio = (Required Agents - Available Agents) / Required Agents
    ```
    
    ### Coverage Calculation
    ```
    Coverage = (Available Agents / Required Agents) × 100%
    ```
    """)
    
    st.markdown("""
    ### Assumptions
    1. Calls arrive randomly following a Poisson process
    2. Call handling times follow an exponential distribution
    3. The call center operates in a steady state
    4. Abandonment occurs only due to excessive wait times
    5. All agents have identical performance characteristics
    """)

# Footer
st.markdown("---")
st.markdown("""
*Note: This tool provides estimates based on mathematical models. Actual call center performance may vary 
due to factors like call arrival patterns, agent skill variation, and unexpected events.*
""")
