import streamlit as st
import math

# Page configuration
st.set_page_config(layout="wide")
st.title("📊 Call Center Staffing Optimizer")

# Custom CSS
st.markdown("""
<style>
.metric-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #f0f2f6;
    margin-bottom: 10px;
}
.warning-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #fff4f4;
    border-left: 5px solid #ff4b4b;
}
</style>
""", unsafe_allow_html=True)

# Input Section
with st.expander("⚙️ Configure Metrics", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        calls_per_hour = st.number_input("Calls per hour", min_value=1, value=200, step=1)
        current_agents = st.number_input("Current agents", min_value=1, value=8, step=1)
    with col2:
        current_aht = st.number_input("Current AHT (seconds)", min_value=30, value=300, step=10)
        current_abandon_rate = st.number_input("Current abandon rate (%)", min_value=0.0, value=15.0, step=0.5)

    col1, col2 = st.columns(2)
    with col1:
        target_sla = st.number_input("Target SLA (%)", min_value=50, value=80, step=1)
        target_answer_time = st.number_input("Target answer time (seconds)", min_value=5, value=30, step=5)
    with col2:
        target_aht = st.number_input("Target AHT (seconds)", min_value=30, value=240, step=10)
        target_abandon_rate = st.number_input("Target abandon rate (%)", min_value=0.0, value=8.0, step=0.5)

# Calculations (Fixed integer handling)
def erlang_c(calls, aht, agents, target_answer_time):
    intensity = calls * (aht/3600)
    agents = math.ceil(agents)  # Ensure integer
    
    if agents <= intensity:
        return 0
    
    sum_series = sum((intensity**n)/math.factorial(n) for n in range(agents))
    erlang_b = (intensity**agents)/math.factorial(agents)
    pw = erlang_b / (erlang_b + (1 - (intensity/agents)) * sum_series)
    return (1 - (pw * math.exp(-(agents - intensity) * (target_answer_time/aht)))) * 100

def find_required_agents(calls, aht, target_sla, target_answer_time):
    intensity = calls * (aht/3600)
    agents = math.ceil(intensity)
    
    while True:
        sl = erlang_c(calls, aht, agents, target_answer_time)
        if sl >= target_sla or agents > 100:
            break
        agents += 1  # Increment by whole numbers only
        
    return agents

# Perform calculations
required_agents = find_required_agents(calls_per_hour, current_aht, target_sla, target_answer_time)
required_agents_target = find_required_agents(calls_per_hour, target_aht, target_sla, target_answer_time)
current_coverage = (current_agents / required_agents) * 100
current_sla = erlang_c(calls_per_hour, current_aht, current_agents, target_answer_time)

# Results Display
st.header("📊 Results")

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="metric-box">
        <h3>Staffing Requirements</h3>
        <p>Current Agents: {current_agents}</p>
        <p>Required Agents (Current AHT): {required_agents}</p>
        <p>Required Agents (Target AHT): {required_agents_target}</p>
        <p>Coverage: {current_coverage:.1f}%</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-box">
        <h3>Performance Metrics</h3>
        <p>Current SLA: {current_sla:.1f}%</p>
        <p>Target SLA: {target_sla}%</p>
        <p>Abandon Rate: {current_abandon_rate}% → Target: {target_abandon_rate}%</p>
    </div>
    """, unsafe_allow_html=True)

# Recommendations
st.header("📝 Recommendations")
if current_coverage < 100:
    st.markdown(f"""
    <div class="warning-box">
        <h3>Staffing Shortage</h3>
        <p>You need {required_agents - current_agents} more agents to meet your SLA target.</p>
        <ul>
            <li>Implement overtime shifts</li>
            <li>Activate call-back system</li>
            <li>Prioritize urgent calls</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

if current_aht > target_aht:
    st.markdown(f"""
    <div class="metric-box">
        <h3>AHT Reduction Opportunity</h3>
        <p>Reducing AHT to {target_aht}s would save {required_agents - required_agents_target} agents.</p>
        <ul>
            <li>Create quick reference guides</li>
            <li>Optimize call scripts</li>
            <li>Automate repetitive tasks</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
