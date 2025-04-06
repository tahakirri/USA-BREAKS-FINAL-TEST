import streamlit as st
import math
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import PercentFormatter

# Page configuration
st.set_page_config(layout="wide")
st.title("📊 Call Center Staffing Optimizer")

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
.graph-box {
    padding: 15px;
    border-radius: 10px;
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# ========== INPUT SECTION ==========
with st.expander("⚙️ Configure Call Center Metrics", expanded=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📞 Call Volume")
        calls_per_hour = st.number_input("Calls per hour", min_value=1, value=200, step=1)
        
    with col2:
        st.subheader("👩‍💼 Staffing")
        current_agents = st.number_input("Current agents available", min_value=1, value=8, step=1)
        
    with col3:
        st.subheader("📊 Performance Metrics")
        current_aht = st.number_input("Current AHT (seconds)", min_value=30, value=300, step=10)
        current_abandon_rate = st.number_input("Current abandon rate (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)

    st.subheader("🎯 Target Performance Goals")
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
occupancy = min(100, (calls_per_hour * (current_aht/3600) / current_agents) * 100)

# ========== VISUALIZATIONS ==========
st.header("📊 Performance Visualizations")

# Visualization 1: Staffing Coverage
with st.container():
    st.subheader("Staffing Coverage Analysis")
    fig, ax = plt.subplots(figsize=(10, 4))
    
    # Data
    categories = ['Current', 'Required', 'With Target AHT']
    values = [current_agents, required_agents, required_agents_target_aht]
    colors = ['#ff6b6b', '#51cf66', '#339af0']
    
    # Plot
    bars = ax.bar(categories, values, color=colors)
    ax.axhline(current_agents, color='#ff6b6b', linestyle='--', alpha=0.5)
    ax.set_ylabel('Number of Agents')
    ax.set_title('Agent Requirements Comparison')
    
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom')
    
    st.pyplot(fig)

# Visualization 2: Performance Metrics Radar Chart
with st.container():
    st.subheader("Performance Metrics Overview")
    
    # Data for radar chart
    categories = ['SLA', 'AHT', 'Abandon Rate', 'Occupancy', 'Coverage']
    current_values = [
        current_sla,
        100 - (current_aht/600)*100,  # Convert AHT to inverse scale (lower is better)
        100 - current_abandon_rate,    # Convert abandon rate to inverse scale
        occupancy,
        current_coverage
    ]
    target_values = [
        target_sla,
        100 - (target_aht/600)*100,
        100 - target_abandon_rate,
        85,  # Ideal occupancy
        100  # Ideal coverage
    ]
    
    # Make radar chart
    angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]  # Close the loop
    current_values += current_values[:1]
    target_values += target_values[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.plot(angles, current_values, 'o-', linewidth=2, label='Current')
    ax.fill(angles, current_values, alpha=0.25)
    ax.plot(angles, target_values, 'o-', linewidth=2, label='Target')
    ax.fill(angles, target_values, alpha=0.1)
    
    ax.set_thetagrids(np.degrees(angles[:-1]), categories)
    ax.set_ylim(0, 100)
    ax.set_title('Performance Metrics Comparison', pad=20)
    ax.legend(loc='upper right')
    
    st.pyplot(fig)

# Visualization 3: Hourly Call Distribution
with st.container():
    st.subheader("Hourly Call Volume Simulation")
    
    # Simulate hourly call distribution (morning, afternoon, evening)
    hours = np.arange(1, 25)
    base_volume = calls_per_hour * 0.8
    call_distribution = base_volume * (1 + 0.5 * np.sin((hours - 9) * np.pi/12))
    call_distribution = np.maximum(base_volume * 0.5, call_distribution)
    
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(hours, call_distribution, marker='o', color='#4dabf7')
    ax.fill_between(hours, call_distribution, color='#4dabf7', alpha=0.2)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Call Volume')
    ax.set_title('Estimated Hourly Call Distribution')
    ax.set_xticks(hours[::2])
    ax.grid(True, linestyle='--', alpha=0.6)
    
    st.pyplot(fig)

# Visualization 4: AHT Impact Analysis
with st.container():
    st.subheader("AHT Impact on Required Staffing")
    
    aht_values = np.linspace(180, 600, 10)  # From 3 to 10 minutes
    required_agents_list = [find_required_agents(calls_per_hour, aht, target_sla, target_answer_time) 
                           for aht in aht_values]
    
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(aht_values, required_agents_list, marker='o', color='#f783ac')
    ax.axvline(current_aht, color='red', linestyle='--', label=f'Current AHT ({current_aht}s)')
    ax.axvline(target_aht, color='green', linestyle='--', label=f'Target AHT ({target_aht}s)')
    ax.set_xlabel('Average Handle Time (seconds)')
    ax.set_ylabel('Agents Required')
    ax.set_title('How AHT Affects Staffing Requirements')
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.6)
    
    st.pyplot(fig)

# ========== RECOMMENDATIONS ==========
st.header("📝 Recommendations")

if current_coverage < 100:
    st.markdown(f"""
    <div class="warning-box">
        <h3>👥 Staffing Recommendations</h3>
        <p>You're currently at <strong>{current_coverage:.1f}% coverage</strong> and need <strong>{required_agents - current_agents} additional agents</strong> to meet your SLA target.</p>
        <ul>
            <li>Consider overtime or shift extensions for current staff</li>
            <li>Implement call-back options to smooth call volume</li>
            <li>Cross-train agents from other departments</li>
            <li>Prioritize high-value calls during peak periods</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

if current_aht > target_aht:
    st.markdown(f"""
    <div class="metric-box">
        <h3>⏱️ AHT Reduction Opportunities</h3>
        <p>Reducing AHT from {current_aht}s to {target_aht}s would decrease required agents from {required_agents} to {required_agents_target_aht}.</p>
        <ul>
            <li>Create quick reference guides for common issues</li>
            <li>Implement better knowledge management system</li>
            <li>Train agents on call control techniques</li>
            <li>Streamline after-call work processes</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

if predicted_abandon > target_abandon_rate:
    st.markdown(f"""
    <div class="metric-box">
        <h3>📉 Abandon Rate Reduction Strategies</h3>
        <p>Predicted abandon rate is {predicted_abandon:.1f}% vs. target of {target_abandon_rate}%.</p>
        <ul>
            <li>Provide accurate wait time estimates to callers</li>
            <li>Implement virtual hold/call-back options</li>
            <li>Improve on-hold messaging and music</li>
            <li>Offer alternative contact methods (chat, email)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
