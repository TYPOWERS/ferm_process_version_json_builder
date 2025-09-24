#!/usr/bin/env python3
"""
Test script for debugging ramp detection on specific pH file
"""

import pandas as pd
import numpy as np
import json
from process_setpoint_files import SetpointProcessor
from component_builder import ComponentBuilder

def test_ramp_detection():
    """Test ramp detection on the problematic pH file"""
    
    # File path
    test_file = "/home/tpowers/_Code/ferm_process_version_json_builder/04/04/pH_SP_Upper (pH) 8EA855121317829769C0A66647B370F781B602F0.all.csv"
    
    print("🔍 Testing ramp detection on pH file...")
    print(f"File: {test_file}")
    print("=" * 80)
    
    # Initialize processor and read file
    processor = SetpointProcessor()
    
    try:
        df = processor.read_setpoint_file(test_file)
        print(f"📊 Loaded {len(df)} data points")
        print(f"Value range: {df['value'].min():.3f} to {df['value'].max():.3f}")
        print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        # Convert timestamps and align timeline
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp', 'value']).reset_index(drop=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Simple timeline alignment (no inoculation time)
        start_time = df['timestamp'].min()
        df['process_time_hours'] = (df['timestamp'] - start_time).dt.total_seconds() / 3600
        
        print(f"📈 Process time range: {df['process_time_hours'].min():.2f} to {df['process_time_hours'].max():.2f} hours")
        print()
        
        # Show first few and last few data points
        print("📋 First 10 data points:")
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            print(f"  {i:2d}: t={row['process_time_hours']:6.2f}h, value={row['value']:6.3f}")
        
        print("\n📋 Last 10 data points:")
        for i in range(max(0, len(df)-10), len(df)):
            row = df.iloc[i]
            print(f"  {i:2d}: t={row['process_time_hours']:6.2f}h, value={row['value']:6.3f}")
        
        print("\n📋 Data around transitions (every 1000 points):")
        for i in range(0, len(df), 1000):
            if i < len(df):
                row = df.iloc[i]
                print(f"  {i:5d}: t={row['process_time_hours']:6.2f}h, value={row['value']:6.3f}")
        print()
        
        # Test the component detection manually
        print("🔍 Testing component detection...")
        
        # Create a mock ComponentBuilder instance without callbacks
        component_builder = ComponentBuilder.__new__(ComponentBuilder)
        component_builder.app = None  # Skip callback setup
        
        # Test ramp detection at different starting points including later indices where ramp should occur
        test_indices = [0, 5, 10, 50, 100, 150, 200]
        
        for start_idx in test_indices:
            if start_idx >= len(df) - 2:
                continue
                
            print(f"\n🎯 Testing detection starting at index {start_idx}:")
            print(f"   Start: t={df.iloc[start_idx]['process_time_hours']:.2f}h, value={df.iloc[start_idx]['value']:.3f}")
            
            # Test step ramp detection with detailed debugging
            print(f"   Values around start: {[df.iloc[i]['value'] for i in range(start_idx, min(start_idx+10, len(df)))]}")
            
            step_ramp_end, step_ramp_component = component_builder._detect_step_ramp_segment(df, start_idx, "pH")
            
            if step_ramp_component:
                print(f"   ✅ Found STEP RAMP: {step_ramp_component}")
                print(f"   End index: {step_ramp_end}, duration: {step_ramp_component['duration']}h")
                print(f"   Step count: {step_ramp_component['step_count']}")
            else:
                print(f"   ❌ No step ramp found, advanced to index {step_ramp_end}")
            
            # Test smooth ramp detection
            ramp_end, ramp_component = component_builder._detect_ramp_segment(df, start_idx, "pH")
            
            if ramp_component:
                print(f"   ✅ Found smooth ramp: {ramp_component}")
                print(f"   End index: {ramp_end}, duration: {ramp_component['duration']}h")
                print(f"   R²: {ramp_component['r_squared']:.3f}")
            else:
                print(f"   ❌ No smooth ramp found, advanced to index {ramp_end}")
                
            # Also test constant detection for comparison
            const_end, const_component = component_builder._detect_constant_segment(df, start_idx, "pH")
            
            if const_component:
                print(f"   📊 Constant alternative: duration={const_component['duration']:.2f}h, value={const_component['setpoint']:.3f}")
            else:
                print(f"   📊 No constant found")
        
        # Run full analysis
        print("\n" + "=" * 80)
        print("🚀 Running full component analysis...")
        
        components = component_builder._detect_components(df, "pH")
        
        print(f"\n📋 Found {len(components)} components:")
        for i, comp in enumerate(components):
            print(f"\n{i+1}. {comp['type'].upper()}:")
            if comp['type'] == 'ramp':
                print(f"   Start: {comp['start_temp']:.3f} → End: {comp['end_temp']:.3f}")
                print(f"   Duration: {comp['duration']}h")
                print(f"   R²: {comp['r_squared']:.3f}")
                print(f"   Data points: {comp['data_points']}")
            elif comp['type'] == 'constant':
                print(f"   Setpoint: {comp['setpoint']:.3f}")
                print(f"   Duration: {comp['duration']}h")
                print(f"   Data points: {comp['data_points']}")
        
        # Convert to final JSON format
        print("\n" + "=" * 80)
        print("📄 Final JSON components:")
        
        # Clean up components for JSON output
        clean_components = []
        for comp in components:
            clean_comp = comp.copy()
            # Remove debug metadata
            for key in ['confidence', 'data_points', 'start_time', 'end_time', 'r_squared']:
                clean_comp.pop(key, None)
            clean_components.append(clean_comp)
        
        print(json.dumps(clean_components, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ramp_detection()

# NOTE: Always use python3 command, not python