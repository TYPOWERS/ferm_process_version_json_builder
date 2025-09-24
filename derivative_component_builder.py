#!/usr/bin/env python3
"""
Derivative-Based Component Builder
Advanced setpoint analysis using multi-scale derivative analysis for better pattern recognition
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dash import html, Input, Output, State, callback, ALL
import dash_bootstrap_components as dbc
import dash
from typing import List, Dict, Tuple, Optional
import uuid
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')


class DerivativeComponentBuilder:
    def __init__(self, app):
        self.app = app
        self.setup_callbacks()

    def _round_to_sig_figs(self, value, sig_figs=3):
        """Round value to specified number of significant figures"""
        if value == 0:
            return 0
        import math
        return round(value, -int(math.floor(math.log10(abs(value)))) + (sig_figs - 1))
    
    def analyze_setpoint_data_derivative(self, setpoint_data: Dict, inoculation_time: str = None, end_of_run_time: str = None) -> List[Dict]:
        """
        Analyze setpoint data using multi-scale derivative analysis
        
        Args:
            setpoint_data: Dict of processed setpoint files
            inoculation_time: Inoculation datetime string for time alignment
            end_of_run_time: End of run datetime string for limiting components
            
        Returns:
            List of component dictionaries
        """
        print("🔍 Starting derivative-based setpoint analysis...")
        
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
            
            # Align timeline with inoculation time and limit to end of run
            aligned_df = self._align_timeline(df, inoculation_time, end_of_run_time)
            
            if len(aligned_df) < 10:  # Need minimum points for derivative analysis
                print(f"  ⚠️ Not enough data points for derivative analysis ({len(aligned_df)} points)")
                continue
            
            # Perform derivative-based component detection
            components = self._detect_components_derivative(aligned_df, file_data['parameter'])
            
            # Add metadata
            for comp in components:
                comp['source_file'] = filename
                comp['id'] = str(uuid.uuid4())
                comp['approved'] = False  # Requires user approval
                comp['method'] = 'derivative_analysis'
            
            all_components.extend(components)
            print(f"  ✅ Generated {len(components)} components using derivative analysis")
        
        # Consolidate and refine components
        consolidated = self._consolidate_derivative_components(all_components)

        # Truncate components that extend past end of run time
        if end_of_run_time and inoculation_time:
            consolidated = self._truncate_components_to_end_time(consolidated, inoculation_time, end_of_run_time)

        # Clean up analysis-specific metadata
        for comp in consolidated:
            comp.pop('confidence', None)
            comp.pop('data_points', None)
            comp.pop('start_time', None)
            comp.pop('end_time', None)
            comp.pop('change_points', None)
            comp.pop('derivative_signature', None)
            comp.pop('pattern_score', None)
            comp.pop('source_file', None)
            comp.pop('approved', None)
            comp.pop('method', None)
        
        print(f"🎯 Derivative analysis complete: {len(consolidated)} components generated")
        return consolidated
    
    def _align_timeline(self, df: pd.DataFrame, inoculation_time: str = None, end_of_run_time: str = None) -> pd.DataFrame:
        """Align setpoint timeline with inoculation time and optionally limit to end of run"""
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
    
    def _detect_components_derivative(self, df: pd.DataFrame, parameter_name: str) -> List[Dict]:
        """Main derivative-based component detection"""
        
        # Step 1: Multi-scale derivative analysis
        derivative_data = self._calculate_multi_scale_derivatives(df)
        
        # Step 2: Change point detection
        change_points = self._detect_change_points(derivative_data)
        
        # Step 3: Segment classification
        segments = self._classify_segments(derivative_data, change_points)
        
        # Step 4: Convert segments to components
        components = self._segments_to_components(segments, parameter_name, df)
        
        return components
    
    def _calculate_multi_scale_derivatives(self, df: pd.DataFrame) -> Dict:
        """Calculate derivatives at multiple time scales"""
        
        # Convert to regular time grid for consistent analysis
        time_hours = df['process_time_hours'].values
        values = df['value'].values
        
        # Create regular time grid (30-minute intervals for fermentation time scales)
        t_min, t_max = time_hours.min(), time_hours.max()
        dt_regular = 0.5  # 30 minutes in hours (matches component rounding)
        t_regular = np.arange(t_min, t_max + dt_regular, dt_regular)
        
        # Interpolate to regular grid
        try:
            interp_func = interp1d(time_hours, values, kind='linear', 
                                 bounds_error=False, fill_value='extrapolate')
            y_regular = interp_func(t_regular)
        except Exception as e:
            print(f"  ⚠️ Interpolation failed: {e}")
            # Fallback to original data
            t_regular = time_hours
            y_regular = values
            dt_regular = np.mean(np.diff(time_hours))
        
        # Calculate derivatives at fermentation-appropriate time scales
        total_duration = t_max - t_min
        
        # Scale window sizes based on total fermentation duration
        if total_duration <= 48:  # Short fermentation (24-48h)
            scales = {
                'fine': 3,    # 1.5 hours window
                'medium': 7,  # 3.5 hours window
                'coarse': 13  # 6.5 hours window
            }
        elif total_duration <= 120:  # Medium fermentation (48-120h)
            scales = {
                'fine': 5,    # 2.5 hours window
                'medium': 11, # 5.5 hours window
                'coarse': 21  # 10.5 hours window
            }
        else:  # Long fermentation (120-170h)
            scales = {
                'fine': 7,    # 3.5 hours window
                'medium': 15, # 7.5 hours window
                'coarse': 29  # 14.5 hours window
            }
        
        # Ensure windows don't exceed data length and are odd
        for scale_name in scales:
            scales[scale_name] = min(scales[scale_name], len(y_regular) - 1)
            if scales[scale_name] % 2 == 0:  # Must be odd
                scales[scale_name] += 1
            if scales[scale_name] < 5:  # Minimum window size
                scales[scale_name] = 5
        
        derivatives = {
            'time': t_regular,
            'values': y_regular,
            'dt': dt_regular
        }
        
        for scale_name, window_size in scales.items():
            if window_size >= len(y_regular):
                window_size = max(5, len(y_regular) // 3)
            if window_size % 2 == 0:  # Must be odd
                window_size += 1
            
            try:
                polyorder = min(3, window_size - 1)
                
                # First derivative (rate of change)
                dy_dt = savgol_filter(y_regular, window_size, polyorder, deriv=1) / dt_regular
                
                # Second derivative (acceleration)
                d2y_dt2 = savgol_filter(y_regular, window_size, polyorder, deriv=2) / (dt_regular ** 2)
                
                derivatives[f'{scale_name}_d1'] = dy_dt
                derivatives[f'{scale_name}_d2'] = d2y_dt2
                
                # Derivative magnitude and direction
                derivatives[f'{scale_name}_magnitude'] = np.abs(dy_dt)
                derivatives[f'{scale_name}_direction'] = np.sign(dy_dt)
                
            except Exception as e:
                print(f"  ⚠️ Derivative calculation failed for {scale_name} scale: {e}")
                # Fallback to simple gradient
                dy_dt = np.gradient(y_regular, dt_regular)
                d2y_dt2 = np.gradient(dy_dt, dt_regular)
                derivatives[f'{scale_name}_d1'] = dy_dt
                derivatives[f'{scale_name}_d2'] = d2y_dt2
                derivatives[f'{scale_name}_magnitude'] = np.abs(dy_dt)
                derivatives[f'{scale_name}_direction'] = np.sign(dy_dt)
        
        return derivatives
    
    def _detect_change_points(self, derivative_data: Dict) -> List[int]:
        """Detect change points using derivative analysis - optimized for long ramps"""
        
        # Use coarse-scale derivatives for change point detection to avoid over-segmentation
        d1_coarse = derivative_data.get('coarse_d1', np.array([]))
        d2_coarse = derivative_data.get('coarse_d2', np.array([]))
        d1_medium = derivative_data.get('medium_d1', np.array([]))
        magnitude_medium = derivative_data.get('medium_magnitude', np.array([]))
        
        if len(d1_coarse) == 0:
            return []
        
        change_points = set()
        
        # Method 1: Large changes in derivative magnitude (more conservative threshold)
        if len(magnitude_medium) > 0:
            magnitude_threshold = np.std(magnitude_medium) * 3  # Increased from 2 to 3 std devs
            magnitude_changes = np.where(np.abs(np.diff(magnitude_medium)) > magnitude_threshold)[0]
            change_points.update(magnitude_changes)
        
        # Method 2: Significant zero crossings in second derivative (coarse scale only)
        # Only consider crossings with sufficient magnitude change
        if len(d2_coarse) > 10:
            d2_smoothed = savgol_filter(d2_coarse, min(11, len(d2_coarse)//2*2+1), 2)
            zero_crossings = np.where(np.diff(np.sign(d2_smoothed)))[0]
            
            # Filter zero crossings - only keep if significant change in d2 magnitude
            d2_threshold = np.std(d2_smoothed) * 2
            significant_crossings = []
            for zc in zero_crossings:
                if zc > 5 and zc < len(d2_smoothed) - 5:  # Not too close to boundaries
                    before = np.abs(d2_smoothed[zc-3:zc]).mean()
                    after = np.abs(d2_smoothed[zc+1:zc+4]).mean()
                    if abs(before - after) > d2_threshold:
                        significant_crossings.append(zc)
            
            change_points.update(significant_crossings)
        
        # Method 3: Major direction changes in first derivative (coarse scale)
        # Only consider sustained direction changes, not brief oscillations
        if len(d1_coarse) > 20:
            # Smooth the derivative to avoid noise
            d1_smoothed = savgol_filter(d1_coarse, min(7, len(d1_coarse)//3*2+1), 2)
            direction = np.sign(d1_smoothed)
            
            # Find runs of consistent direction
            direction_changes = np.where(np.diff(direction) != 0)[0]
            
            # Filter for sustained changes (at least 2 hours = 4 points at 0.5h intervals)
            min_run_length = 4
            filtered_changes = []
            
            for i, change_idx in enumerate(direction_changes):
                # Check if this direction change is sustained
                if change_idx + min_run_length < len(direction):
                    new_direction = direction[change_idx + 1]
                    # Verify the new direction persists
                    if np.sum(direction[change_idx+1:change_idx+1+min_run_length] == new_direction) >= min_run_length * 0.8:
                        filtered_changes.append(change_idx)
            
            change_points.update(filtered_changes)
        
        # Convert to sorted list and filter with larger minimum distance
        change_points = sorted(list(change_points))
        
        # Remove points too close to boundaries and each other (increased minimum distance)
        min_distance = max(8, len(d1_coarse) // 50)  # Increased from //100 to //50, min 8 points (4 hours)
        filtered_points = []
        
        for cp in change_points:
            if min_distance <= cp <= len(d1_coarse) - min_distance:
                # Check if too close to existing change point
                if not filtered_points or min(abs(cp - existing) for existing in filtered_points) >= min_distance:
                    filtered_points.append(cp)
        
        # Always include start and end points
        final_points = [0] + filtered_points + [len(d1_coarse) - 1]
        return sorted(list(set(final_points)))
    
    def _classify_segments(self, derivative_data: Dict, change_points: List[int]) -> List[Dict]:
        """Classify segments between change points"""
        
        segments = []
        d1 = derivative_data.get('medium_d1', np.array([]))
        d2 = derivative_data.get('medium_d2', np.array([]))
        values = derivative_data['values']
        time = derivative_data['time']
        
        if len(change_points) < 2:
            return segments
        
        for i in range(len(change_points) - 1):
            start_idx = change_points[i]
            end_idx = change_points[i + 1]
            
            if end_idx <= start_idx:
                continue
            
            # Extract segment data
            seg_d1 = d1[start_idx:end_idx]
            seg_d2 = d2[start_idx:end_idx]
            seg_values = values[start_idx:end_idx]
            seg_time = time[start_idx:end_idx]
            
            if len(seg_d1) < 3:  # Too short to analyze
                continue
            
            # Classify segment type
            segment_type, confidence, metadata = self._classify_single_segment(
                seg_d1, seg_d2, seg_values, seg_time
            )
            
            segments.append({
                'start_idx': start_idx,
                'end_idx': end_idx,
                'start_time': seg_time[0],
                'end_time': seg_time[-1],
                'start_value': seg_values[0],
                'end_value': seg_values[-1],
                'type': segment_type,
                'confidence': confidence,
                'metadata': metadata,
                'duration': seg_time[-1] - seg_time[0]
            })
        
        return segments
    
    def _classify_single_segment(self, d1: np.ndarray, d2: np.ndarray, 
                                values: np.ndarray, time: np.ndarray) -> Tuple[str, float, Dict]:
        """Classify a single segment based on derivative patterns"""
        
        # Calculate statistics
        d1_mean = np.mean(d1)
        d1_std = np.std(d1)
        d1_abs_mean = np.mean(np.abs(d1))
        d2_abs_mean = np.mean(np.abs(d2))
        
        value_range = np.max(values) - np.min(values)
        duration = time[-1] - time[0] if len(time) > 1 else 0
        
        metadata = {
            'd1_mean': d1_mean,
            'd1_std': d1_std,
            'd1_abs_mean': d1_abs_mean,
            'd2_abs_mean': d2_abs_mean,
            'value_range': value_range,
            'duration': duration
        }
        
        # Classification thresholds (adaptive based on data)
        noise_threshold = np.percentile(np.abs(d1), 75) * 0.1  # 10% of 75th percentile
        small_change_threshold = 0.05  # 0.05 units
        min_duration_threshold = 0.5  # 30 minutes minimum (matches rounding)
        
        # Rule-based classification
        if duration < min_duration_threshold:
            return 'noise', 0.3, metadata
        
        elif d1_abs_mean < noise_threshold and value_range < small_change_threshold:
            # Constant region: low derivative, small value range
            confidence = 0.9 if d1_std < noise_threshold * 0.5 else 0.7
            return 'constant', confidence, metadata
        
        elif d1_abs_mean > noise_threshold:
            # Potential ramp: significant first derivative
            
            # Check consistency of slope (more lenient for long ramps)
            slope_consistency = 1 - (d1_std / (d1_abs_mean + 1e-6))  # Avoid division by zero
            
            # For long durations, be more lenient on slope consistency
            duration_factor = min(1.0, duration / 12.0)  # Scale factor for durations > 12h
            consistency_threshold = 0.6 - (duration_factor * 0.2)  # Lower threshold for longer ramps
            
            # Also check if second derivative is reasonable for a ramp
            d2_ratio = d2_abs_mean / (d1_abs_mean + 1e-6)
            
            if slope_consistency > consistency_threshold and d2_ratio < 2.0:  # More lenient thresholds
                confidence = min(0.95, 0.4 + slope_consistency * 0.4 + duration_factor * 0.2)
                return 'ramp', confidence, metadata
            elif d2_abs_mean > noise_threshold * 3:
                # High second derivative suggests PID or complex control
                return 'pid', 0.7, metadata
            else:
                # Inconsistent slope might be complex pattern
                return 'complex', 0.5, metadata
        
        elif d1_abs_mean > noise_threshold and d2_abs_mean > noise_threshold:
            # High variability in both derivatives suggests PID or complex control
            
            # Look for oscillatory behavior (sign changes in d1)
            sign_changes = np.sum(np.diff(np.sign(d1)) != 0)
            oscillation_ratio = sign_changes / len(d1)
            
            if oscillation_ratio > 0.1:  # More than 10% sign changes
                return 'pid', 0.8, metadata
            else:
                return 'complex', 0.6, metadata
        
        else:
            # Default case
            return 'complex', 0.4, metadata
    
    def _segments_to_components(self, segments: List[Dict], parameter_name: str, 
                              original_df: pd.DataFrame) -> List[Dict]:
        """Convert classified segments to profile components"""
        
        components = []
        
        for seg in segments:
            if seg['confidence'] < 0.5 or seg['type'] == 'noise':
                continue  # Skip low-confidence or noise segments
            
            duration = seg['duration']
            if duration < 0.5:  # Less than 30 minutes, skip
                continue
            
            # Round duration to nearest 0.5 hours
            rounded_duration = round(duration * 2) / 2
            
            component = {
                'parameter': parameter_name,
                'start_time': round(seg['start_time'], 2),
                'end_time': round(seg['end_time'], 2),
                'duration': rounded_duration,
                'confidence': seg['confidence'],
                'data_points': seg['end_idx'] - seg['start_idx']
            }
            
            if seg['type'] == 'constant':
                component.update({
                    'type': 'constant',
                    'setpoint': self._round_to_sig_figs(seg['start_value'])
                })
            
            elif seg['type'] == 'ramp':
                component.update({
                    'type': 'ramp',
                    'start_temp': self._round_to_sig_figs(seg['start_value']),
                    'end_temp': self._round_to_sig_figs(seg['end_value'])
                })
            
            elif seg['type'] == 'pid':
                # For PID, use average value as setpoint and estimate bounds
                avg_value = (seg['start_value'] + seg['end_value']) / 2
                value_range = abs(seg['end_value'] - seg['start_value'])
                
                component.update({
                    'type': 'pid',
                    'controller': f"Auto-detected PID Controller ({parameter_name})",
                    'setpoint': self._round_to_sig_figs(avg_value),
                    'min_allowed': self._round_to_sig_figs(avg_value - value_range),
                    'max_allowed': self._round_to_sig_figs(avg_value + value_range)
                })
            
            elif seg['type'] == 'complex':
                # For complex patterns, create a ramp as best approximation
                component.update({
                    'type': 'ramp',
                    'start_temp': self._round_to_sig_figs(seg['start_value']),
                    'end_temp': self._round_to_sig_figs(seg['end_value'])
                })
                component['confidence'] = min(component['confidence'], 0.6)
            
            components.append(component)
        
        return components
    
    def _consolidate_derivative_components(self, components: List[Dict]) -> List[Dict]:
        """Consolidate and refine components from derivative analysis"""
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
                merged = self._try_merge_derivative_components(current, next_comp)
                if merged:
                    current = merged
                    j += 1
                else:
                    break
            
            # Only keep components with minimum duration and confidence
            if current['duration'] >= 0.5 and current['confidence'] >= 0.5:  # 30 minutes minimum
                consolidated.append(current)
            
            i = j if j > i + 1 else i + 1
        
        return consolidated
    
    def _try_merge_derivative_components(self, comp1: Dict, comp2: Dict) -> Optional[Dict]:
        """Try to merge two adjacent components from derivative analysis"""
        
        # Must be same type and parameter
        if comp1['type'] != comp2['type'] or comp1['parameter'] != comp2['parameter']:
            return None
        
        # Check if they're adjacent (small time gap allowed)
        time_gap = comp2['start_time'] - comp1['end_time']
        if time_gap > 0.5:  # More than 30 minutes gap
            return None
        
        # Merge based on type
        if comp1['type'] == 'constant':
            # Merge constants with similar setpoints
            if abs(comp1['setpoint'] - comp2['setpoint']) < 0.2:  # Within 0.2 units
                return {
                    'type': 'constant',
                    'setpoint': round((comp1['setpoint'] + comp2['setpoint']) / 2, 1),
                    'duration': comp1['duration'] + comp2['duration'],
                    'parameter': comp1['parameter'],
                    'start_time': comp1['start_time'],
                    'end_time': comp2['end_time'],
                    'confidence': min(comp1['confidence'], comp2['confidence']),
                    'data_points': comp1['data_points'] + comp2['data_points']
                }
        
        elif comp1['type'] == 'ramp':
            # Merge ramps with similar slopes (more aggressive merging)
            slope1 = (comp1['end_temp'] - comp1['start_temp']) / comp1['duration']
            slope2 = (comp2['end_temp'] - comp2['start_temp']) / comp2['duration']
            
            # Calculate overall slope if components were merged
            total_change = comp2['end_temp'] - comp1['start_temp']
            total_duration = comp1['duration'] + comp2['duration']
            overall_slope = total_change / total_duration if total_duration > 0 else 0
            
            # Check if individual slopes are consistent with overall slope
            slope_tolerance = 0.5  # Increased from 0.3 to 0.5 for more aggressive merging
            
            avg_slope = (abs(slope1) + abs(slope2)) / 2
            if avg_slope == 0:
                slope_consistency = True
            else:
                slope1_diff = abs(slope1 - overall_slope) / (abs(overall_slope) + 1e-6)
                slope2_diff = abs(slope2 - overall_slope) / (abs(overall_slope) + 1e-6)
                slope_consistency = max(slope1_diff, slope2_diff) < slope_tolerance
            
            # Also allow merging if slopes have same direction and reasonable magnitude
            same_direction = (slope1 * slope2 >= 0)  # Same sign or one is zero
            reasonable_diff = avg_slope == 0 or abs(slope1 - slope2) / avg_slope < 0.6
            
            if slope_consistency or (same_direction and reasonable_diff):
                return {
                    'type': 'ramp',
                    'start_temp': comp1['start_temp'],
                    'end_temp': comp2['end_temp'],
                    'duration': total_duration,
                    'parameter': comp1['parameter'],
                    'start_time': comp1['start_time'],
                    'end_time': comp2['end_time'],
                    'confidence': min(comp1['confidence'], comp2['confidence']),
                    'data_points': comp1['data_points'] + comp2['data_points']
                }
        
        elif comp1['type'] == 'pid':
            # Merge PID components with overlapping ranges
            if (comp1['min_allowed'] <= comp2['max_allowed'] and 
                comp2['min_allowed'] <= comp1['max_allowed']):
                
                new_min = min(comp1['min_allowed'], comp2['min_allowed'])
                new_max = max(comp1['max_allowed'], comp2['max_allowed'])
                new_setpoint = (comp1['setpoint'] + comp2['setpoint']) / 2
                
                return {
                    'type': 'pid',
                    'controller': comp1['controller'],
                    'setpoint': round(new_setpoint, 1),
                    'min_allowed': round(new_min, 1),
                    'max_allowed': round(new_max, 1),
                    'duration': comp1['duration'] + comp2['duration'],
                    'parameter': comp1['parameter'],
                    'start_time': comp1['start_time'],
                    'end_time': comp2['end_time'],
                    'confidence': min(comp1['confidence'], comp2['confidence']),
                    'data_points': comp1['data_points'] + comp2['data_points']
                }
        
        return None

    def _truncate_components_to_end_time(self, components: List[Dict], inoculation_time: str, end_of_run_time: str) -> List[Dict]:
        """Truncate components that extend past end of run time, with interpolation for ramps"""
        try:
            inoculation_dt = pd.to_datetime(inoculation_time, errors='coerce')
            end_run_dt = pd.to_datetime(end_of_run_time, errors='coerce')
            if pd.isna(inoculation_dt) or pd.isna(end_run_dt):
                print("  → Warning: Could not parse time values for truncation")
                return components

            # Calculate total run time (end of run - inoculation)
            total_run_time = (end_run_dt - inoculation_dt).total_seconds() / 3600
            print(f"  → Total run time: {total_run_time:.1f}h (from inoculation to end of run)")

            if not components:
                return components

            # Calculate cumulative time for each component to find which extends past end
            truncated_components = []
            cumulative_time = 0

            for i, comp in enumerate(components):
                comp_duration = comp.get('duration', 0)
                comp_end_time = cumulative_time + comp_duration

                print(f"  → Component {i+1} ({comp['type']}): {cumulative_time:.1f}h - {comp_end_time:.1f}h (duration: {comp_duration:.1f}h)")

                if cumulative_time >= total_run_time:
                    # This component starts after end of run - skip it
                    print(f"    → Skipping (starts after end of run at {total_run_time:.1f}h)")
                    break

                elif comp_end_time > total_run_time:
                    # This component extends past end of run - truncate it
                    # New duration = total_run_time - sum of all previous components
                    remaining_time = total_run_time - cumulative_time

                    print(f"    → Extends past end of run - truncating:")
                    print(f"    → Total run time: {total_run_time:.1f}h")
                    print(f"    → Time used by previous components: {cumulative_time:.1f}h")
                    print(f"    → Remaining time for this component: {remaining_time:.1f}h")

                    truncated_comp = comp.copy()
                    truncated_comp['duration'] = remaining_time  # Don't round yet, keep exact

                    # Handle ramp interpolation
                    if comp['type'] == 'ramp':
                        start_temp = comp['start_temp']
                        end_temp = comp['end_temp']
                        # Calculate interpolated end temperature based on progress
                        progress = remaining_time / comp_duration if comp_duration > 0 else 0
                        interpolated_end_temp = start_temp + (end_temp - start_temp) * progress
                        truncated_comp['end_temp'] = self._round_to_sig_figs(interpolated_end_temp)
                        print(f"    → Ramp interpolation: {start_temp} → {interpolated_end_temp:.3f} (progress: {progress:.2%})")

                    # Round to 5-minute precision for final duration
                    truncated_comp['duration'] = round(remaining_time / (5/60)) * (5/60)  # 5 minutes = 5/60 hours
                    print(f"    → Final duration (rounded to 5min): {truncated_comp['duration']:.3f}h")

                    truncated_components.append(truncated_comp)
                    break  # This was the last component

                else:
                    # Component ends before end of run - keep as is
                    print(f"    → Keeping as-is (ends before run end)")
                    truncated_components.append(comp)

                cumulative_time = comp_end_time

            print(f"  → Result: {len(components)} → {len(truncated_components)} components after truncation")
            return truncated_components

        except Exception as e:
            print(f"  → Error during truncation: {e}")
            return components

    def setup_callbacks(self):
        """Setup callbacks for derivative component builder integration"""
        
        @self.app.callback(
            Output("profile-components", "data", allow_duplicate=True),
            [Input("setpoint-data", "data")],
            [State("inoculation-time", "data"),
             State("end-of-run-time", "data"),
             State("profile-components", "data")],
            prevent_initial_call=True
        )
        def analyze_with_derivatives_auto(setpoint_data, inoculation_time, end_of_run_time, existing_components):
            print(f"🔍 Derivative callback triggered! setpoint_data: {bool(setpoint_data)}, existing_components: {len(existing_components or [])}")
            
            if not setpoint_data:
                print("⚠️ No setpoint data provided to derivative analysis")
                return existing_components or []
            
            try:
                print(f"🚀 Starting derivative analysis on {len(setpoint_data)} files...")
                # Run the derivative analysis engine automatically
                generated_components = self.analyze_setpoint_data_derivative(setpoint_data, inoculation_time, end_of_run_time)
                print(f"🎯 Generated {len(generated_components)} components using derivative analysis")
                
                # Replace existing auto-generated components with new derivative-based ones
                manual_components = [c for c in (existing_components or []) 
                                   if not c.get('source_file')]  # Keep manually added components
                
                all_components = manual_components + generated_components
                print(f"📊 Final component count: {len(all_components)} (manual: {len(manual_components)}, generated: {len(generated_components)})")
                return all_components
            except Exception as e:
                print(f"❌ Error in derivative analysis: {e}")
                import traceback
                traceback.print_exc()
                return existing_components or []


# Function to integrate with main app
def setup_derivative_component_builder(app):
    """Setup derivative component builder functionality in the main app"""
    derivative_builder = DerivativeComponentBuilder(app)
    return derivative_builder