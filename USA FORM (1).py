import streamlit as st
import math
import matplotlib.pyplot as plt
import numpy as np

# Page configuration
st.set_page_config(layout="wide")
st.title("Call Center Staffing Optimizer")

# Custom CSS for better styling
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
.good-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #f0fff4;
    border-left: 5px solid #00d154;
}
</style>
""", unsafe_allow_html=True)

# ========== INPUT SECTION ==========
st.header("Current Call Center Metrics")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Call Volume")
    calls_per_hour = st.number_input("Calls per hour", min_value=1, value=200, step=1)
    
with col2:
    st.subheader("Staffing")
    current_agents = st.number_input("Current agents available", min_value=1, value=8, step=1)
    
with col3:
    st.subheader("Performance Metrics")
    current_aht = st.number_input("Current AHT (seconds)", min_value=30, value=300, step=10)
    current_abandon_rate = st.number_input("Current abandon rate (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)

st.header("Target Performance Goals")

col1, col2, col3 = st.columns(3)

with col1:
    target_sla = st.number_input("Target service level (%)", min_value=50, max_value=100, value=80, step=1)
    target_answer_time = st.number_input("Target answer time (seconds)", min_value=5, value=30, step=5)
    
with col2:
    target_aht = st.number_input("Target AHT (seconds)", min_value=30, value=240, step=10)
    
with col3:
    target_abandon_rate = st.number_input("Target abandon rate (%)", min_value=0.0, max_value=100.0, value=8.0, step=0.5)

# ========== CALCULATIONS ==========
def erlang_c(calls, aht, agents, target_answer_time):
    intensity = calls * (aht/3600)
    agents = math.ceil(agents)
    
    if agents <= intensity:
        return 0  # Service level will be 0% if agents <= intensity
    
    sum_series = sum([(intensity**n)/math.factorial(n) for n in range(agents)])
    erlang_b = (intensity**agents)/math.factorial(agents)
    pw = erlang_b / (erlang_b + (1 - (intensity/agents)) * sum_series)
    
    sl = 1 - (pw * math.exp(-(agents - intensity) * (target_answer_time/aht)))
    return sl * 100

def find_required_agents(calls, aht, target_sla, target_answer_time):
    intensity = calls * (aht/3600)
    agents = math.ceil(intensity)  # Start with minimum possible
    
    while True:
        sl = erlang_c(calls, aht, agents, target_answer_time)
        if sl >= target_sla or agents > 100:  # Prevent infinite loop
            break
        agents += 0.1
        
    return math.ceil(agents)

def predict_abandon_rate(calls, agents, aht, current_abandon_rate):
    intensity = calls * (aht/3600)
    occupancy = min(100, (intensity/agents)*100)
    
    # Simple model: abandon rate increases exponentially with occupancy over 80%
    if occupancy <= 80:
        predicted_abandon = current_abandon_rate * (occupancy/80)
    else:
        predicted_abandon = current_abandon_rate * (1 + (occupancy-80)/20)**2
    
    return min(100, predicted_abandon)

# Calculate metrics
required_agents = find_required_agents(calls_per_hour, current_aht, target_sla, target_answer_time)
required_agents_target_aht = find_required_agents(calls_per_hour, target_aht, target_sla, target_answer_time)
current_coverage = (current_agents / required_agents) * 100
predicted_abandon = predict_abandon_rate(calls_per_hour, current_agents, current_aht, current_abandon_rate)
current_sla = erlang_c(calls_per_hour, current_aht, current_agents, target_answer_time)

# ========== RESULTS SECTION ==========
st.header("Optimization Results")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="metric-box">
        <h3>Current Staffing Situation</h3>
        <p>Agents available: <strong>{current_agents}</strong></p>
        <p>Agents needed: <strong>{required_agents}</strong></p>
        <p>Coverage: <strong>{current_coverage:.1f}%</strong></p>
    </div>
    """, unsafe_allow_html=True)
    
    if current_coverage < 80:
        st.markdown(f"""
        <div class="warning-box">
            <h3>⚠️ Warning: Understaffed</h3>
            <p>You need {required_agents - current_agents} more agents to meet your SLA target</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="good-box">
            <h3>✓ Adequate Staffing</h3>
            <p>Your current staffing meets requirements</p>
        </div>
        """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-box">
        <h3>Performance Metrics</h3>
        <p>Current SLA: <strong>{current_sla:.1f}%</strong></p>
        <p>Predicted abandon rate: <strong>{predicted_abandon:.1f}%</strong></p>
        <p>Current AHT: <strong>{current_aht}s</strong></p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-box">
        <h3>Improvement Potential</h3>
        <p>If you achieve target AHT ({target_aht}s):</p>
        <p>Agents needed: <strong>{required_agents_target_aht}</strong></p>
        <p>Staffing gap: <strong>{max(0, required_agents_target_aht - current_agents)}</strong></p>
    </div>
    """, unsafe_allow_html=True)

# ========== VISUALIZATION ==========
st.header("Performance Visualization")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

# Coverage graph
ax1.barh(['Coverage'], [100], color='lightgray')
ax1.barh(['Coverage'], [current_coverage], color='salmon')
ax1.set_xlim(0, 120)
ax1.axvline(100, color='black', linestyle='--')
ax1.set_title('Staffing Coverage')
ax1.text(100+2, 0, '100% Target', va='center')
ax1.text(current_coverage/2, 0, f'{current_coverage:.1f}%', va='center', color='white')

# Abandon rate comparison
rates = [current_abandon_rate, predicted_abandon, target_abandon_rate]
labels = ['Current', 'Predicted', 'Target']
colors = ['lightblue', 'salmon', 'lightgreen']
ax2.bar(labels, rates, color=colors)
ax2.set_ylim(0, max(rates)*1.2)
ax2.set_title('Abandon Rate Comparison')
for i, v in enumerate(rates):
    ax2.text(i, v+0.5, f"{v:.1f}%", ha='center')

st.pyplot(fig)

# ========== RECOMMENDATIONS ==========
st.header("Recommendations")

if current_coverage < 100:
    st.markdown("""
    ### Staffing Recommendations:
    1. **Immediate Actions**:
       - Recruit {} additional agents
       - Offer overtime to current staff
       - Prioritize high-value calls
    
    2. **Process Improvements**:
       - Implement call-back option
       - Optimize IVR to reduce unnecessary calls
       - Cross-train agents from other departments
    """.format(required_agents - current_agents))

if current_aht > target_aht:
    st.markdown("""
    ### AHT Reduction Recommendations:
    1. **Training**:
       - Focus on average handle time in coaching
       - Create quick reference guides for common issues
    
    2. **Tools & Processes**:
       - Improve knowledge base accessibility
       - Streamline call wrap-up procedures
       - Automate repetitive tasks
    """)

if predicted_abandon > target_abandon_rate:
    st.markdown("""
    ### Abandon Rate Reduction:
    1. **Queue Management**:
       - Provide accurate wait time estimates
       - Offer position in queue information
    
    2. **Customer Communication**:
       - Implement virtual hold (call-back option)
       - Improve on-hold messaging and music
    """)
