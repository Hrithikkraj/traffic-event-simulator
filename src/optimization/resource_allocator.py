import pandas as pd
import pulp
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define operational blueprints: How many resources does each tier actually need?
TIER_REQUIREMENTS = {
    'Critical': {'officers': 12, 'barricades': 20, 'benefit_multiplier': 1.5},
    'High':     {'officers': 6,  'barricades': 10, 'benefit_multiplier': 1.2},
    'Medium':   {'officers': 3,  'barricades': 5,  'benefit_multiplier': 1.0},
    'Low':      {'officers': 1,  'barricades': 0,  'benefit_multiplier': 0.8}
}

def optimize_deployment(active_events_df: pd.DataFrame, total_officers: int = 50, total_barricades: int = 80) -> pd.DataFrame:
    """
    Uses Integer Linear Programming (ILP) to allocate finite officers to active events.
    Objective: Maximize total mitigated Event Impact Score.
    """
    logging.info(f"Running optimization for {len(active_events_df)} events with {total_officers} officers available.")
    
    # 1. Initialize the Optimization Problem (Maximization)
    prob = pulp.LpProblem("Police_Resource_Allocation", pulp.LpMaximize)
    
    # 2. Decision Variables: A binary flag for each event (1 = Deploy Resources, 0 = Do Not Deploy)
    # In a real system, you could do partial deployments, but binary is perfect for a hackathon MVP.
    event_ids = active_events_df.index.tolist()
    deploy_vars = pulp.LpVariable.dicts("Deploy", event_ids, cat='Binary')
    
    # 3. Objective Function: Maximize the EIS mitigated. 
    # We weight higher tiers slightly more to ensure Critical events are prioritized.
    prob += pulp.lpSum([
        deploy_vars[i] * active_events_df.loc[i, 'eis_normalized'] * TIER_REQUIREMENTS[active_events_df.loc[i, 'eis_tier']]['benefit_multiplier']
        for i in event_ids
    ])
    
    # 4. Constraints: We cannot exceed total available officers or barricades
    prob += pulp.lpSum([
        deploy_vars[i] * TIER_REQUIREMENTS[active_events_df.loc[i, 'eis_tier']]['officers']
        for i in event_ids
    ]) <= total_officers, "Max_Officers"
    
    prob += pulp.lpSum([
        deploy_vars[i] * TIER_REQUIREMENTS[active_events_df.loc[i, 'eis_tier']]['barricades']
        for i in event_ids
    ]) <= total_barricades, "Max_Barricades"
    
    # 5. Solve the Knapsack/ILP problem
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    
    # 6. Map results back to the DataFrame
    active_events_df = active_events_df.copy()
    active_events_df['is_resources_deployed'] = [deploy_vars[i].varValue for i in event_ids]
    
    # Assign actual numbers based on the solver's binary decision
    active_events_df['assigned_officers'] = active_events_df.apply(
        lambda x: TIER_REQUIREMENTS[x['eis_tier']]['officers'] if x['is_resources_deployed'] == 1 else 0, axis=1
    )
    active_events_df['assigned_barricades'] = active_events_df.apply(
        lambda x: TIER_REQUIREMENTS[x['eis_tier']]['barricades'] if x['is_resources_deployed'] == 1 else 0, axis=1
    )
    
    logging.info(f"Optimization complete. Total officers deployed: {active_events_df['assigned_officers'].sum()}")
    return active_events_df

# Quick test if run directly
if __name__ == "__main__":
    # Mock data to test the solver
    data = {
        'event_cause': ['VIP Rally', 'Truck Breakdown', 'Pothole', 'Protest'],
        'eis_normalized': [95.0, 60.0, 15.0, 85.0],
        'eis_tier': ['Critical', 'Medium', 'Low', 'High']
    }
    df = pd.DataFrame(data)
    optimized_df = optimize_deployment(df, total_officers=15, total_barricades=25)
    print(optimized_df[['event_cause', 'eis_tier', 'assigned_officers', 'assigned_barricades']])