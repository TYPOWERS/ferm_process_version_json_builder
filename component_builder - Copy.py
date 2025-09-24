#!/usr/bin/env python3
"""
Component Builder & Analysis Engine
Converts setpoint data into profile components using intelligent pattern recognition
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dash import html, Input, Output, State, callback, ALL
import dash_bootstrap_components as dbc
import dash
from typing import List, Dict, Tuple
import uuid


class ComponentBuilder:
    def __init__(self, app):
        self.app = app
        self.setup_callbacks()
    
    def analyze_setpoint_data(self, setpoint_data: Dict, inoculation_time: str = None) -> List[Dict]:
        """
        Analyze setpoint data and generate profile components
        
        Args:
            setpoint_data: Dict of processed setpoint files
            inoculation_time: Inoculation datetime string for time alignment
            
        Returns:
            List of component dictionaries
        """
        print("🔍 Starting setpoint analysis...")
        
        all_components = []
        
        for filename, file_data in setpoint_data.items():
            print(f"📊 Analyzing file: {filename}")
            
            # Convert back to DataFrame for analysis
            df = pd.DataFrame(file_data['data'])
            if df.empty:
                continue
                
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            
            # Drop rows with NaN timestamps or values
            df = df.dropna(subset=['timestamp', 'value']).reset_index(drop=True)
            
            if df.empty:
                print(f"  ⚠️ No valid data after removing NaN values")
                continue
                
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Align timeline with inoculation time
            aligned_df = self._align_timeline(df, inoculation_time)
            
            # Detect segments and create components
            components = self._detect_components(aligned_df, file_data['parameter'])
            
            # Add metadata
            for comp in components:
                comp['source_file'] = filename
                comp['id'] = str(uuid.uuid4())
                comp['approved'] = False  # Requires user approval
            
            all_components.extend(components)
            print(f"  ✅ Generated {len(components)} components")
        
        # Consolidate similar components
        consolidated = self._consolidate_components(all_components)
        
        # Clean up analysis-specific metadata that shouldn't be in the main profile
        for comp in consolidated:
            comp.pop('confidence', None)
            comp.pop('data_points', None)
            comp.pop('start_time', None)
            comp.pop('end_time', None)
            comp.pop('r_squared', None)
            comp.pop('step_count', None)
            comp.pop('step_pattern', None)
            comp.pop('mean_slope', None)
            comp.pop('slope_consistency', None)
            comp.pop('original_components', None)
            comp.pop('source_file', None)
            comp.pop('approved', None)
        
        print(f"🎯 Analysis complete: {len(consolidated)} components generated")
        return consolidated
    
    def _align_timeline(self, df: pd.DataFrame, inoculation_time: str = None) -> pd.DataFrame:
        """Align setpoint timeline with inoculation time"""
        if not inoculation_time:
            # If no inoculation time, start from 0
            start_time = df['timestamp'].min()
            df['process_time_hours'] = (df['timestamp'] - start_time).dt.total_seconds() / 3600
        else:
            # Align with inoculation time
            inoculation_dt = pd.to_datetime(inoculation_time, errors='coerce')
            df['process_time_hours'] = (df['timestamp'] - inoculation_dt).dt.total_seconds() / 3600
            
            # Filter to only include post-inoculation data
            df = df[df['process_time_hours'] >= 0].reset_index(drop=True)
        
        return df
    
    def _detect_components(self, df: pd.DataFrame, parameter_name: str) -> List[Dict]:
        """Detect components from aligned setpoint data"""
        if len(df) < 2:
            return []
        
        components = []
        i = 0
        
        while i < len(df) - 1:
            # Find the next segment
            segment_end, component = self._find_next_segment(df, i, parameter_name)
            
            if component:
                components.append(component)
            
            i = segment_end
        
        return components
    
    def _find_next_segment(self, df: pd.DataFrame, start_idx: int, parameter_name: str) -> Tuple[int, Dict]:
        """Find the next component segment starting from start_idx"""
        
        # Look for step-wise ramps first (new priority for pH-style data)
        #step_ramp_end, step_ramp_component = self._detect_step_ramp_segment(df, start_idx, parameter_name)
        
        # Look for smooth ramp segments
        ramp_end, ramp_component = self._detect_ramp_segment(df, start_idx, parameter_name)
        
        # Look for constant segments
        constant_end, constant_component = self._detect_constant_segment(df, start_idx, parameter_name)
        
        # Prioritize step ramps > smooth ramps > constants
        #if step_ramp_component:
        #    return step_ramp_end, step_ramp_component
        #elif ramp_component and constant_component:
        if ramp_component and constant_component:
            # If ramp covers significant portion of constant or more, prefer ramp
            ramp_length = ramp_end - start_idx
            constant_length = constant_end - start_idx
            
            if ramp_length >= constant_length * 0.7:  # Ramp covers at least 70% of constant length
                return ramp_end, ramp_component
            else:
                return constant_end, constant_component
        elif ramp_component:
            return ramp_end, ramp_component
        elif constant_component:
            return constant_end, constant_component
        else:
            # No clear pattern, advance by 1
            return start_idx + 1, None
    
    def _detect_constant_segment(self, df: pd.DataFrame, start_idx: int, parameter_name: str) -> Tuple[int, Dict]:
        """Detect constant segments (variance threshold = 0)"""
        if start_idx >= len(df) - 1:
            return start_idx + 1, None
        
        start_value = df.iloc[start_idx]['value']
        start_time = df.iloc[start_idx]['process_time_hours']
        
        # Find how far the constant segment extends
        end_idx = start_idx + 1
        max_value=max(df['value'])
        min_value=min(df['value'])
        range_value=max_value-min_value
        while end_idx < len(df):
            current_value = df.iloc[end_idx]['value']
            
            # Check if still constant (variance threshold = 0)
            if abs(current_value - start_value) > range_value * 0.1:  # Small epsilon for floating point
                break
                
            end_idx += 1
        
        # Check minimum duration (0.167 hours = 10 minutes)
        end_time = df.iloc[end_idx - 1]['process_time_hours']
        duration = end_time - start_time
        
        # Handle NaN values in duration calculation
        if pd.isna(duration) or duration < 0.167:  # 10 minutes minimum in hours
            return start_idx + 1, None
        
        # Keep precise values for better detection
        rounded_value = round(start_value, 1)  # 1 decimal place
        rounded_duration = duration  # Don't round duration
        
        component = {
            'type': 'constant',
            'setpoint': rounded_value,
            'duration': rounded_duration,
            'parameter': parameter_name,
            'start_time': round(start_time, 2),
            'end_time': round(end_time, 2),
            'confidence': 'high',
            'data_points': end_idx - start_idx
        }
        
        return end_idx, component
    
    def _detect_step_ramp_segment(self, df: pd.DataFrame, start_idx: int, parameter_name: str) -> Tuple[int, Dict]:
        """Detect ramp segments using gradient analysis (based on user's pandas/numpy approach)"""
        if start_idx >= len(df) - 10:  # Need enough points for gradient analysis
            return start_idx + 1, None
        
        # Take a reasonable segment for analysis
        #max_scan = min(1000, len(df) - start_idx)  # Analyze up to 1000 points
        #segment_df = df.iloc[start_idx:start_idx + max_scan].copy().reset_index(drop=True)
        segment_df =df.copy().reset_index(drop=True)
        if len(segment_df) < 10:
            return start_idx + 1, None
        
        # Convert time to seconds for gradient calculation
        time_hours = segment_df['process_time_hours'].values
        time_seconds = time_hours * 3600  # Convert to seconds
        values = segment_df['value'].values
        
        # Compute slope using numpy gradient
        slopes = np.gradient(values, time_seconds)
        
        # Define threshold for flat vs ramp (pH units per second)
        epsilon = 0.001  # Even smaller threshold - most pH changes should be considered ramps
        
        # Label segments as flat or ramp
        segment_types = np.where(np.abs(slopes) < epsilon, "flat", "ramp")
        
        # Group consecutive segments
        type_changes = np.concatenate([[True], segment_types[1:] != segment_types[:-1]])
        segment_ids = np.cumsum(type_changes)
        
        # Analyze each segment to find meaningful ramps
        for seg_id in np.unique(segment_ids):
            mask = segment_ids == seg_id
            seg_indices = np.where(mask)[0]
            
            if len(seg_indices) < 5:  # Skip very short segments
                continue
                
            seg_type = segment_types[seg_indices[0]]
            
            if seg_type == "ramp":
                # Check if this is a meaningful ramp
                start_seg_idx = seg_indices[0]
                end_seg_idx = seg_indices[-1]
                
                start_value = values[start_seg_idx]
                end_value = values[end_seg_idx]
                start_time_h = time_hours[start_seg_idx]
                end_time_h = time_hours[end_seg_idx]
                
                duration = end_time_h - start_time_h
                total_change = abs(end_value - start_value)
                
                # Check if this ramp meets our criteria
                if duration >= 0.5 and total_change >= 0.1:  # 30 min minimum, 0.1 pH minimum change
                    
                    # Calculate mean slope for this segment
                    seg_slopes = slopes[mask]
                    mean_slope = np.mean(seg_slopes)
                    std_slope = np.std(seg_slopes)
                    
                    # Check consistency of slope (low std deviation indicates consistent ramp)
                    if std_slope < abs(mean_slope) * 2:  # Slope is reasonably consistent
                        
                        # Create ramp component
                        rounded_start = round(start_value, 1)
                        rounded_end = round(end_value, 1)
                        
                        component = {
                            'type': 'ramp',
                            'start_temp': rounded_start,
                            'end_temp': rounded_end,
                            'duration': duration,
                            'parameter': parameter_name,
                            'start_time': round(start_time_h, 2),
                            'end_time': round(end_time_h, 2),
                            'confidence': 'high',
                            'mean_slope': round(mean_slope * 3600, 6),  # Convert to pH/hour
                            'slope_consistency': round(std_slope / abs(mean_slope) if mean_slope != 0 else 0, 3),
                            'data_points': len(seg_indices)
                        }
                        
                        # Return the end index in the original dataframe
                        end_df_idx = start_idx + end_seg_idx
                        return end_df_idx + 1, component
        
        # No meaningful ramp found
        return start_idx + 1, None

    def _detect_ramp_segment(self, df: pd.DataFrame, start_idx: int, parameter_name: str) -> Tuple[int, Dict]:
        """
        Detect ramp segments using adaptive thresholds based on data statistics.
        Uses relative thresholds instead of fixed epsilon values.
        """

        if start_idx >= len(df) - 2:  # need at least 3 points
            return start_idx + 1, None

        # Extract the relevant slice
        sub_df = df.iloc[start_idx:].copy()

        # Compute slope (change in value / change in time)
        sub_df["slope"] = np.gradient(
            sub_df["value"].values,
            sub_df["process_time_hours"].values
        )

        # Start from current position and extend ramp as long as slope is consistent
        ramp_start_idx = start_idx
        current_idx = start_idx
        
        # Need at least 3 points to start
        if len(sub_df) < 3:
            return start_idx + 1, None
        
        # Start with first 3 slopes
        ramp_slopes = sub_df["slope"].iloc[0:3].tolist()
        current_idx = start_idx + 2  # We've used first 3 points
        
        # Continue ramp as long as slope stays within 2x of average of last 3 slopes
        for i in range(3, len(sub_df)):
            current_slope = sub_df["slope"].iloc[i]
            
            # Get average of last 3 slopes
            last_3_avg = np.mean(ramp_slopes[-3:])
            
            # Check if current slope is within 2x of the last 3 average
            if abs(current_slope) > abs(last_3_avg) :
                # End the ramp here
                break
            
            # Slope is consistent, continue ramp
            ramp_slopes.append(current_slope)
            current_idx = start_idx + i
        
        ramp_end_idx = current_idx
        
        # Check if we have a meaningful ramp
        if ramp_end_idx <= ramp_start_idx + 1:  # Need at least 2 points
            return start_idx + 1, None
            
        start_time = df.iloc[ramp_start_idx]["process_time_hours"]
        end_time = df.iloc[ramp_end_idx]["process_time_hours"]
        duration = end_time - start_time

        # Require a minimum duration (10 minutes = 0.167 hr)
        if pd.isna(duration) or duration < 0.167:
            return start_idx + 1, None

        start_value = df.iloc[ramp_start_idx]["value"]
        end_value = df.iloc[ramp_end_idx]["value"]

        # Calculate statistics for the detected ramp
        mean_slope = np.mean(ramp_slopes)
        slope_std = np.std(ramp_slopes)

        # Confidence based on slope consistency
        slope_consistency = 1 - (slope_std / (abs(mean_slope) + 1e-6))
        if slope_consistency > 0.8:
            confidence = "high"
        elif slope_consistency > 0.6:
            confidence = "medium"
        else:
            confidence = "low"

        component = {
            "type": "ramp",
            "start_temp": round(start_value, 1),
            "end_temp": round(end_value, 1),
            "duration": duration,
            "parameter": parameter_name,
            "start_time": round(start_time, 2),
            "end_time": round(end_time, 2),
            "confidence": confidence,
            "mean_slope": round(mean_slope, 6),
            "slope_std": round(slope_std, 6),
            "data_points": ramp_end_idx - ramp_start_idx + 1,
        }

        return ramp_end_idx + 1, component
    def _consolidate_components(self, components: List[Dict]) -> List[Dict]:
        """Consolidate similar adjacent components to minimize count"""
        if not components:
            return []
        
        # Sort by start time
        sorted_components = sorted(components, key=lambda x: x['start_time'])
        consolidated = []
        
        i = 0
        while i < len(sorted_components):
            current = sorted_components[i].copy()
            
            # Look for components to merge
            j = i + 1
            while j < len(sorted_components):
                next_comp = sorted_components[j]
                
                # Try to merge with next component
                merged = self._try_merge_components(current, next_comp)
                if merged:
                    current = merged
                    j += 1
                else:
                    break
            
            consolidated.append(current)
            i = j if j > i + 1 else i + 1
        
        # Detect PID patterns (3+ small constants in sequence)
        consolidated = self._detect_pid_patterns(consolidated)
        
        return consolidated
    
    def _try_merge_components(self, comp1: Dict, comp2: Dict) -> Dict:
        """Try to merge two adjacent components if they're similar"""
        
        # Must be same type and parameter
        if comp1['type'] != comp2['type'] or comp1['parameter'] != comp2['parameter']:
            return None
        
        # Check if they're actually adjacent (small time gap allowed for constants only)
        time_gap = comp2['start_time'] - comp1['end_time']
        if comp1['type'] == 'constant' and time_gap > 0.5:  # Only restrict constants
            return None
        
        if comp1['type'] == 'constant':
            # Merge constants with same setpoint (0 threshold)
            if abs(comp1['setpoint'] - comp2['setpoint']) < 0.001:
                return {
                    'type': 'constant',
                    'setpoint': comp1['setpoint'],
                    'duration': comp1['duration'] + comp2['duration'],
                    'parameter': comp1['parameter'],
                    'start_time': comp1['start_time'],
                    'end_time': comp2['end_time'],
                    'confidence': 'high',
                    'data_points': comp1['data_points'] + comp2['data_points'],
                    'source_file': ', '.join(set([f for f in [comp1.get('source_file', ''), comp2.get('source_file', '')] if f]))
                }
        
        elif comp1['type'] == 'ramp':
            # Use angle difference between ramp directions (much better approach)
            slope1 = (comp1['end_temp'] - comp1['start_temp']) / comp1['duration']  # per hour
            slope2 = (comp2['end_temp'] - comp2['start_temp']) / comp2['duration']  # per hour
            
            # Calculate angles of the slopes (in radians)
            angle1 = np.arctan(slope1)
            angle2 = np.arctan(slope2)
            
            # Calculate the absolute difference between angles
            angle_diff = abs(angle1 - angle2)
            
            # Handle the case where angles wrap around (e.g., near ±π/2)
            if angle_diff > np.pi:
                angle_diff = 2 * np.pi - angle_diff
            
            # Convert 10% to radians - 10% of π/2 (90 degrees) = π/20 ≈ 0.157 radians ≈ 9 degrees
            max_angle_diff = np.pi / 20  # 10% of 90 degrees
            
            angle_tolerance_met = angle_diff <= max_angle_diff
            
            if angle_tolerance_met:
                return {
                    'type': 'ramp',
                    'start_temp': comp1['start_temp'],
                    'end_temp': comp2['end_temp'],
                    'duration': comp1['duration'] + comp2['duration'],
                    'parameter': comp1['parameter'],
                    'start_time': comp1['start_time'],
                    'end_time': comp2['end_time'],
                    'confidence': 'high',
                    'data_points': comp1['data_points'] + comp2['data_points'],
                    'source_file': ', '.join(set([f for f in [comp1.get('source_file', ''), comp2.get('source_file', '')] if f]))
                }
        
        return None
    
    def _detect_pid_patterns(self, components: List[Dict]) -> List[Dict]:
        """Convert 3+ small constants in sequence to PID components"""
        if len(components) < 3:
            return components
        
        result = []
        i = 0
        
        while i < len(components):
            # Look for sequence of small constant components
            if (components[i]['type'] == 'constant' and 
                components[i]['duration'] <= 1):  # 1 hour or less = "small"
                
                # Count consecutive small constants
                j = i
                total_duration = 0
                values = []
                
                while (j < len(components) and 
                       components[j]['type'] == 'constant' and
                       components[j]['duration'] <= 1 and
                       components[j]['parameter'] == components[i]['parameter']):
                    
                    total_duration += components[j]['duration']
                    values.append(components[j]['setpoint'])
                    j += 1
                
                # If 3+ components, convert to PID
                if j - i >= 3:
                    avg_setpoint = round(np.mean(values), 1)
                    min_val = round(min(values), 1)
                    max_val = round(max(values), 1)
                    
                    pid_component = {
                        'type': 'pid',
                        'controller': f"Auto-detected PID Controller",
                        'setpoint': avg_setpoint,
                        'min_allowed': min_val,
                        'max_allowed': max_val,
                        'duration': round(total_duration, 1),  # Round to 0.1 hour precision
                        'parameter': components[i]['parameter'],
                        'start_time': components[i]['start_time'],
                        'end_time': components[j-1]['end_time'],
                        'confidence': 'medium',
                        'original_components': j - i,
                        'source_file': ', '.join(set([c.get('source_file', '') for c in components[i:j]]))
                    }
                    
                    result.append(pid_component)
                    i = j
                else:
                    result.append(components[i])
                    i += 1
            else:
                result.append(components[i])
                i += 1
        
        return result
    
    def setup_callbacks(self):
        """Setup callbacks for component builder integration"""
        
        @self.app.callback(
            Output("profile-components", "data", allow_duplicate=True),
            [Input("setpoint-data", "data")],
            [State("inoculation-time", "data"),
             State("profile-components", "data")],
            prevent_initial_call=True
        )
        def analyze_and_generate_components(setpoint_data, inoculation_time, existing_components):
            print(f"🔍 Gradient callback triggered! setpoint_data: {bool(setpoint_data)}, existing_components: {len(existing_components or [])}")
            
            if not setpoint_data:
                print("⚠️ No setpoint data provided to gradient analysis")
                return existing_components or []
            
            try:
                print(f"🚀 Starting gradient analysis on {len(setpoint_data)} files...")
                # Run the analysis engine
                generated_components = self.analyze_setpoint_data(setpoint_data, inoculation_time)
                print(f"🎯 Generated {len(generated_components)} components using gradient analysis")
                
                # Add generated components to existing profile components
                all_components = (existing_components or []) + generated_components
                print(f"📊 Final component count: {len(all_components)} (existing: {len(existing_components or [])}, generated: {len(generated_components)})")
                return all_components
            except Exception as e:
                print(f"❌ Error analyzing setpoint data: {e}")
                import traceback
                traceback.print_exc()
                return existing_components or []


# Function to integrate with main app
def setup_component_builder(app):
    """Setup component builder functionality in the main app"""
    component_builder = ComponentBuilder(app)
    return component_builder