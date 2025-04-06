import streamlit as st
import math

# Page configuration
st.set_page_config(layout="wide")
st.title("📊 Call Center Staffing Optimizer")

# Dark mode CSS
st.markdown("""
<style>
body {
    color: #ffffff;
    background-color: #1a1a1a;
}
.metric-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #2d3436;
    margin-bottom: 10px;
    border-left: 5px solid #3498db;
}
.warning-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #2d3436;
    border-left: 5px solid #e74c3c;
    margin-bottom: 10px;
}
.stNumberInput, .stSelectbox, .stSlider {
    background-color: #2d3436 !important;
    color: white !important;
}
.graph-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #2d3436;
    border: 1px solid #3498db;
    margin-bottom: 20px;
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

# Calculations
def erlang_c(calls, aht, agents, target_answer_time):
    intensity = calls * (aht/3600)
    agents = math.ceil(agents)
    
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
        agents += 1
        
    return agents

def predict_abandon_rate(calls, agents, aht, current_abandon_rate):
    intensity = calls * (aht/3600)
    occupancy = min(100, (intensity/agents)*100)
    
    # Abandon rate model
    if occupancy <= 80:
        predicted_abandon = current_abandon_rate * (occupancy/80)
    else:
        predicted_abandon = current_abandon_rate * (1 + (occupancy-80)/20)**2
    
    return min(100, predicted_abandon)

# Perform calculations
required_agents = find_required_agents(calls_per_hour, current_aht, target_sla, target_answer_time)
required_agents_target = find_required_agents(calls_per_hour, target_aht, target_sla, target_answer_time)
current_coverage = (current_agents / required_agents) * 100
current_sla = erlang_c(calls_per_hour, current_aht, current_agents, target_answer_time)
predicted_abandon = predict_abandon_rate(calls_per_hour, current_agents, current_aht, current_abandon_rate)
shift_abandon = (predicted_abandon/100) * calls_per_hour * 9  # 9-hour shift projection

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
        <p>Hourly Abandon Rate: {predicted_abandon:.1f}%</p>
        <p>9h Shift Abandon Projection: {int(shift_abandon)} calls</p>
        <p>Occupancy: {min(100, (calls_per_hour * (current_aht/3600) / current_agents * 100):.1f}%</p>
    </div>
    """, unsafe_allow_html=True)

# Recommendations
st.header("📝 Action Plan")
if current_coverage < 100:
    st.markdown(f"""
    <div class="warning-box">
        <h3>Staffing Shortage Solutions</h3>
        <p>Gap: {required_agents - current_agents} agents needed</p>
        <ul>
            <li>Team leaders to actively coach high-AHT agents</li>
            <li>Implement dynamic queue prioritization for high-wait calls</li>
            <li>Activate surge capacity protocols during peak hours</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

if current_aht > target_aht:
    st.markdown(f"""
    <div class="metric-box">
        <h3>AHT Reduction Strategy</h3>
        <p>Potential savings: {required_agents - required_agents_target} agents</p>
        <ul>
            <li>Redesign call processes to eliminate redundant steps</li>
            <li>Implement real-time AHT monitoring dashboard</li>
            <li>Create quick resolution playbooks for common issues</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown(f"""
<div class="metric-box">
    <h3>Queue Management Protocol</h3>
    <ul>
        <li>Automatically escalate calls waiting > {target_answer_time * 1.5} seconds</li>
        <li>Implement callback option for calls predicted to wait > {target_answer_time} seconds</li>
        <li>Prioritize repeat callers and high-value customers in queue</li>
    </ul>
</div>
""", unsafe_allow_html=True)
