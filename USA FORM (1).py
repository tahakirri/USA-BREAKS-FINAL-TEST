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
.graph-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
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
    if agents <= intensity:
        return 0
    sum_series = sum((intensity**n)/math.factorial(n) for n in range(int(agents)))
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
        agents += 0.1
    return math.ceil(agents)

required_agents = find_required_agents(calls_per_hour, current_aht, target_sla, target_answer_time)
required_agents_target = find_required_agents(calls_per_hour, target_aht, target_sla, target_answer_time)
current_coverage = (current_agents / required_agents) * 100
current_sla = erlang_c(calls_per_hour, current_aht, current_agents, target_answer_time)
occupancy = min(100, (calls_per_hour * (current_aht/3600) / current_agents) * 100)

# Visualization 1: Staffing Comparison (using native Streamlit)
st.subheader("👥 Staffing Requirements")
st.write(f"""
- **Current agents**: {current_agents}
- **Required agents (current AHT)**: {required_agents}
- **Required agents (target AHT)**: {required_agents_target}
""")

# Visualization 2: Performance Metrics
st.subheader("📊 Performance Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Current SLA", f"{current_sla:.1f}%", f"Target: {target_sla}%")
col2.metric("Current AHT", f"{current_aht}s", f"Target: {target_aht}s")
col3.metric("Abandon Rate", f"{current_abandon_rate}%", f"Target: {target_abandon_rate}%")
col4.metric("Occupancy", f"{occupancy:.1f}%", "Ideal: 85%")

# Visualization 3: AHT Impact
st.subheader("⏱️ AHT Impact Analysis")
st.write(f"""
- **Current AHT**: {current_aht}s requires {required_agents} agents
- **Target AHT**: {target_aht}s requires {required_agents_target} agents
- **Potential savings**: {required_agents - required_agents_target} agents
""")

# Recommendations
st.header("📝 Recommendations")
if current_coverage < 100:
    st.markdown(f"""
    <div class="warning-box">
        <h3>Staffing Shortage</h3>
        <p>You need {required_agents - current_agents} more agents to meet your SLA target.</p>
        <ul>
            <li>Implement overtime for current staff</li>
            <li>Offer call-back options</li>
            <li>Cross-train agents from other departments</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

if current_aht > target_aht:
    st.markdown(f"""
    <div class="metric-box">
        <h3>AHT Reduction Potential</h3>
        <p>Reducing AHT to {target_aht}s would save {required_agents - required_agents_target} agents.</p>
        <ul>
            <li>Create quick reference guides</li>
            <li>Improve knowledge base</li>
            <li>Streamline call processes</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

if current_abandon_rate > target_abandon_rate:
    st.markdown(f"""
    <div class="metric-box">
        <h3>Abandon Rate Reduction</h3>
        <p>Current abandon rate is {current_abandon_rate}% vs. target of {target_abandon_rate}%.</p>
        <ul>
            <li>Provide accurate wait time estimates</li>
            <li>Implement virtual hold options</li>
            <li>Improve on-hold messaging</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
