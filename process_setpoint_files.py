#!/usr/bin/env python3
"""
Process Setpoint Files Visualizer
Dash web application for analyzing and visualizing fermentation setpoint time series data from CSV files.
"""

import os
import glob
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
import re
from typing import Dict, List, Tuple

import dash
from dash import dcc, html, Input, Output, State, callback, MATCH, ALL
import dash_bootstrap_components as dbc
import base64

class SetpointProcessor:
    def __init__(self, data_folder=None):
        self.data_folder = data_folder
        self.setpoint_files = []
        self.parameter_groups = {}
        self.all_files = []  # Store all files for the Dash app
        
    def is_uuid_like(self, filename):
        """Check if filename starts with a UUID-like pattern (8-4-4-4-12 hex characters)"""
        import re
        # Remove file extension and _SP suffix to get the base name
        base_name = filename.replace('.csv', '').replace('_SP', '').split('_SP')[0]
        # UUID pattern: 8-4-4-4-12 hexadecimal characters
        uuid_pattern = r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'
        return bool(re.match(uuid_pattern, base_name))
    
    def add_step_function_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add intermediate points to create step-function visualization for setpoints.
        
        For gaps > 69 seconds, insert a point at (next_timestamp - 1_second, previous_value)
        to show that the setpoint remained constant until the change.
        
        Uses vectorized operations for much better performance.
        """
        if len(df) < 2:
            return df
        
        try:
            import numpy as np
            
            # Vectorized approach - much faster than row-by-row
            timestamps = df['timestamp'].values
            values = df['value'].values
            
            # Calculate time differences between consecutive points (vectorized)
            time_diffs = np.diff(timestamps).astype('timedelta64[s]').astype(float)
            
            # Find indices where gaps > 69 seconds (vectorized boolean mask)
            gap_mask = time_diffs > 69
            gap_indices = np.where(gap_mask)[0]  # Get indices of gaps
            
            if len(gap_indices) == 0:
                return df  # No gaps, return original
            
            print(f"  - Found {len(gap_indices)} gaps > 69 seconds, adding step points...")
            
            # Create lists to hold all data (original + new points)
            all_timestamps = []
            all_values = []
            all_parameters = []
            all_filepaths = []
            
            # Process in chunks for better memory efficiency
            current_idx = 0
            
            for gap_idx in gap_indices:
                # Add all points up to the gap
                end_idx = gap_idx + 1
                all_timestamps.extend(timestamps[current_idx:end_idx])
                all_values.extend(values[current_idx:end_idx])
                all_parameters.extend(df['parameter'].iloc[current_idx:end_idx].values)
                all_filepaths.extend(df['file_path'].iloc[current_idx:end_idx].values)
                
                # Add step point (1 second before next point, floored)
                next_timestamp = timestamps[gap_idx + 1]
                step_timestamp = pd.Timestamp(next_timestamp) - pd.Timedelta(seconds=1)
                step_timestamp = step_timestamp.floor('s')
                
                all_timestamps.append(step_timestamp)
                all_values.append(values[gap_idx])  # Use previous value
                all_parameters.append(df['parameter'].iloc[gap_idx])
                all_filepaths.append(df['file_path'].iloc[gap_idx])
                
                current_idx = end_idx
            
            # Add remaining points after the last gap
            if current_idx < len(timestamps):
                all_timestamps.extend(timestamps[current_idx:])
                all_values.extend(values[current_idx:])
                all_parameters.extend(df['parameter'].iloc[current_idx:].values)
                all_filepaths.extend(df['file_path'].iloc[current_idx:].values)
            
            # Create new dataframe (single operation, much faster)
            result_df = pd.DataFrame({
                'timestamp': all_timestamps,
                'value': all_values,
                'parameter': all_parameters,
                'file_path': all_filepaths
            })
            
            # Sort by timestamp (vectorized)
            return result_df.sort_values('timestamp').reset_index(drop=True)
                
        except Exception as e:
            print(f"Warning: Error in step-function processing: {e}")
            import traceback
            traceback.print_exc()
            return df  # Return original data if processing fails
    
    def extract_inoculation_time(self):
        """Extract inoculation timestamp from Reference times file."""
        if not self.data_folder:
            return None
            
        # Look for Reference times file
        pattern = os.path.join(self.data_folder, "*Reference*times*.csv")
        reference_files = glob.glob(pattern)
        
        if not reference_files:
            print("No Reference times file found")
            return None
            
        try:
            reference_file = reference_files[0]  # Use first match
            print(f"Found Reference times file: {os.path.basename(reference_file)}")
            
            # Read the file and look for Inoculation timestamp
            with open(reference_file, 'r') as f:
                for line in f:
                    if 'Inoculation' in line:
                        # Extract timestamp from the line
                        # Format: 2025-07-24T23:06:15.1012886,,Inoculation
                        timestamp = line.split(',')[0]
                        print(f"Found inoculation time: {timestamp}")
                        return timestamp
                        
        except Exception as e:
            print(f"Error reading Reference times file: {e}")
            
        return None

    def extract_end_of_run_time(self):
        """Extract end of run timestamp from State file where state is 'Unloading'."""
        if not self.data_folder:
            return None

        # Look for State file (pattern: State [UUID].all.csv)
        pattern = os.path.join(self.data_folder, "State*.csv")
        state_files = glob.glob(pattern)

        if not state_files:
            print("No State file found")
            return None

        try:
            state_file = state_files[0]  # Use first match
            print(f"Found State file: {os.path.basename(state_file)}")

            # Read the file and look for Unloading timestamp
            with open(state_file, 'r') as f:
                for line in f:
                    if 'Unloading' in line:
                        # Extract timestamp from the line
                        # Format: 2025-07-31T19:49:07.8355362,,Unloading
                        timestamp = line.split(',')[0]
                        print(f"Found end of run time: {timestamp}")
                        return timestamp

        except Exception as e:
            print(f"Error reading State file: {e}")

        return None

    def discover_files(self):
        """Find all _SP files and categorize them by parameter type."""
        if not self.data_folder:
            return {'variable_sp': [], 'named_sp': [], 'inoculation_time': None, 'end_of_run_time': None}
            
        pattern = os.path.join(self.data_folder, "*_SP*.csv")
        self.setpoint_files = glob.glob(pattern)
        
        # Extract inoculation time from Reference times file
        inoculation_time = self.extract_inoculation_time()

        # Extract end of run time from State file
        end_of_run_time = self.extract_end_of_run_time()
        
        # Separate files into Variable SP (UUID-like) and Named SP groups
        variable_sp_files = []
        named_sp_files = []
        
        for file_path in self.setpoint_files:
            filename = os.path.basename(file_path)
            file_info = {
                'path': file_path,
                'name': filename,
                'selected': False
            }
            
            if self.is_uuid_like(filename):
                variable_sp_files.append(file_info)
            else:
                named_sp_files.append(file_info)
        
        # Sort both groups alphabetically
        variable_sp_files.sort(key=lambda x: x['name'].lower())
        named_sp_files.sort(key=lambda x: x['name'].lower())
        
        # Store grouped files
        self.grouped_files = {
            'variable_sp': variable_sp_files,
            'named_sp': named_sp_files
        }
        
        # Also maintain the flat list for backward compatibility
        self.all_files = named_sp_files + variable_sp_files
        
        # Group files by parameter type (keep existing functionality)
        self.parameter_groups = {}
        for file_path in self.setpoint_files:
            filename = os.path.basename(file_path)
            
            # Extract parameter name (everything before _SP)
            if "_SP" in filename:
                param_name = filename.split("_SP")[0]
                # Clean up parameter name
                param_name = param_name.replace("_", " ").title()
                
                if param_name not in self.parameter_groups:
                    self.parameter_groups[param_name] = []
                self.parameter_groups[param_name].append(file_path)
        
        # Add inoculation time and end of run time to the return data
        result = self.grouped_files.copy()
        result['inoculation_time'] = inoculation_time
        result['end_of_run_time'] = end_of_run_time
        return result
    
    def read_setpoint_file(self, file_path: str) -> pd.DataFrame:
        """Read and parse a single setpoint CSV file."""
        try:
            file_name = os.path.basename(file_path)
            print(f"Processing file: {file_name}")
            # Read the file, skipping the header lines
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            
            # Find the data start (after VariableKey line)
            data_start = 0
            variable_key = ""
            
            for i, line in enumerate(lines):
                if line.startswith("VariableKey,"):
                    variable_key = line.split(",", 1)[1].strip()
                    data_start = i + 1
                    break
            
            if data_start == 0:
                print(f"Warning: Could not find VariableKey in {file_path}")
                return pd.DataFrame()
            
            # Read the time series data
            data_lines = lines[data_start:]
            timestamps = []
            values = []
            
            for line in data_lines:
                line = line.strip()
                if line and ',' in line:
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        timestamp_str = parts[0]
                        value_str = parts[1]
                        
                        # Skip NaN values
                        if value_str.lower() in ['nan', '']:
                            continue
                            
                        try:
                            timestamp = pd.to_datetime(timestamp_str)
                            value = float(value_str)
                            timestamps.append(timestamp)
                            values.append(value)
                        except (ValueError, pd.errors.ParserError):
                            continue
            
            if not timestamps:
                return pd.DataFrame()
            
            if not timestamps:
                return pd.DataFrame()
            
            # Create initial dataframe
            df = pd.DataFrame({
                'timestamp': timestamps,
                'value': values,
                'parameter': variable_key,
                'file_path': file_path
            })
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Add step-function points for setpoint visualization
            original_count = len(df)
            print(f"  - Original points: {original_count}")
            
            if original_count > 10000:
                print(f"  - Large file detected, this may take a moment...")
            
            df = self.add_step_function_points(df)
            print(f"  - After step processing: {len(df)} (+{len(df) - original_count} step points)")
            
            return df
            
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def list_parameters(self):
        """List all available parameter groups."""
        if not self.parameter_groups:
            self.discover_files()
        
        print("\nAvailable Parameter Groups:")
        print("=" * 50)
        for i, (param_group, files) in enumerate(self.parameter_groups.items(), 1):
            print(f"{i:2d}. {param_group} ({len(files)} files)")
        
        return list(self.parameter_groups.keys())
    
    def select_parameters_interactive(self) -> List[str]:
        """Interactive parameter selection."""
        param_names = self.list_parameters()
        
        print(f"\nEnter parameter numbers to plot (comma-separated, or 'all' for all):")
        print("Example: 1,3,5 or all")
        
        selection = input("Selection: ").strip()
        
        if selection.lower() == 'all':
            return param_names
        
        selected_params = []
        try:
            numbers = [int(x.strip()) for x in selection.split(',')]
            for num in numbers:
                if 1 <= num <= len(param_names):
                    selected_params.append(param_names[num - 1])
                else:
                    print(f"Warning: Number {num} is out of range")
        except ValueError:
            print("Invalid input. Please use numbers or 'all'.")
            return []
        
        return selected_params
    
    def load_selected_data(self, selected_params: List[str]) -> pd.DataFrame:
        """Load data for selected parameters."""
        all_data = []
        
        print(f"\nLoading data for {len(selected_params)} parameter groups...")
        
        for param_group in selected_params:
            if param_group not in self.parameter_groups:
                print(f"Warning: Parameter group '{param_group}' not found")
                continue
            
            files = self.parameter_groups[param_group]
            print(f"Loading {param_group}: {len(files)} files")
            
            for file_path in files:
                df = self.read_setpoint_file(file_path)
                if not df.empty:
                    all_data.append(df)
        
        if not all_data:
            return pd.DataFrame()
        
        combined_df = pd.concat(all_data, ignore_index=True)
        combined_df = combined_df.sort_values(['parameter', 'timestamp'])
        
        print(f"Loaded {len(combined_df)} data points from {len(set(combined_df['parameter']))} parameters")
        return combined_df
    
    def calculate_derivatives(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate 1st and 2nd derivatives using Savitzky-Golay filtering for smoother results."""
        import numpy as np
        from scipy.interpolate import interp1d
        from scipy.signal import savgol_filter
        
        result_data = []
        
        for param in data['parameter'].unique():
            param_data = data[data['parameter'] == param].copy()
            param_data = param_data.sort_values('timestamp').reset_index(drop=True)
            
            if len(param_data) < 10:  # Need minimum points for filtering
                # Fall back to simple gradient for very small datasets
                time_seconds = (param_data['timestamp'] - param_data['timestamp'].iloc[0]).dt.total_seconds().values
                values = param_data['value'].values
                param_data['first_derivative'] = np.gradient(values, time_seconds)
                param_data['second_derivative'] = np.gradient(param_data['first_derivative'], time_seconds)
                result_data.append(param_data)
                continue
                
            # Convert timestamps to numeric (seconds from first timestamp)
            time_irregular = (param_data['timestamp'] - param_data['timestamp'].iloc[0]).dt.total_seconds().values
            values_irregular = param_data['value'].values
            
            # 1. Resample onto a regular grid
            t_min, t_max = np.min(time_irregular), np.max(time_irregular)
            dt_regular = 1.0  # 1 second intervals
            t_regular = np.arange(t_min, t_max + dt_regular, dt_regular)
            
            # Skip if too few points after resampling
            if len(t_regular) < 10:
                time_seconds = time_irregular
                values = values_irregular
                param_data['first_derivative'] = np.gradient(values, time_seconds)
                param_data['second_derivative'] = np.gradient(param_data['first_derivative'], time_seconds)
                result_data.append(param_data)
                continue
            
            # 2. Interpolate onto regular grid
            try:
                interp_function = interp1d(time_irregular, values_irregular, kind='linear', 
                                         bounds_error=False, fill_value='extrapolate')
                y_regular = interp_function(t_regular)
                
                # 3. Apply Savitzky-Golay Filter for derivatives
                window_size = min(21, len(y_regular) // 3)  # Adaptive window size
                if window_size % 2 == 0:  # Must be odd
                    window_size += 1
                if window_size < 5:  # Minimum window size
                    window_size = 5
                    
                polyorder = min(3, window_size - 1)  # Polynomial order must be < window size
                
                # Calculate derivatives on regular grid
                dy_dt_regular = savgol_filter(y_regular, window_size, polyorder, deriv=1) / dt_regular
                d2y_dt2_regular = savgol_filter(y_regular, window_size, polyorder, deriv=2) / (dt_regular ** 2)
                
                # 4. Interpolate derivatives back to original irregular timestamps
                interp_dy = interp1d(t_regular, dy_dt_regular, kind='linear', 
                                   bounds_error=False, fill_value='extrapolate')
                interp_d2y = interp1d(t_regular, d2y_dt2_regular, kind='linear', 
                                    bounds_error=False, fill_value='extrapolate')
                
                first_derivative = interp_dy(time_irregular)
                second_derivative = interp_d2y(time_irregular)
                
            except Exception as e:
                print(f"Warning: Savgol filtering failed for {param}, falling back to gradient: {e}")
                # Fall back to simple gradient
                first_derivative = np.gradient(values_irregular, time_irregular)
                second_derivative = np.gradient(first_derivative, time_irregular)
            
            # Add derivatives to the dataframe
            param_data = param_data.copy()
            param_data['first_derivative'] = first_derivative
            param_data['second_derivative'] = second_derivative
            
            result_data.append(param_data)
        
        if result_data:
            return pd.concat(result_data, ignore_index=True)
        else:
            return data

    def create_plot(self, data: pd.DataFrame, title: str = "Setpoint Time Series", use_process_time: bool = False) -> go.Figure:
        """Create Plotly visualization of the setpoint data with derivatives."""
        if data.empty:
            return go.Figure().add_annotation(text="No data to display", x=0.5, y=0.5)
        
        # Calculate derivatives
        data_with_derivatives = self.calculate_derivatives(data)
        
        # Create subplots: 3 rows (Original, 1st Derivative, 2nd Derivative)
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=('Setpoint Values', '1st Derivative (Rate of Change)', '2nd Derivative (Acceleration)'),
            vertical_spacing=0.08,
            shared_xaxes=True
        )
        
        # Get unique parameters
        parameters = data_with_derivatives['parameter'].unique()
        
        # Create a color palette
        colors = px.colors.qualitative.Set3
        if len(parameters) > len(colors):
            colors = px.colors.qualitative.Plotly * (len(parameters) // len(px.colors.qualitative.Plotly) + 1)
        
        for i, param in enumerate(parameters):
            param_data = data_with_derivatives[data_with_derivatives['parameter'] == param]
            color = colors[i % len(colors)]
            
            # Extract units from parameter name for hover text
            units = ""
            if "(" in param and ")" in param:
                units = param[param.find("(")+1:param.find(")")]
            
            # Choose x-axis data based on use_process_time
            x_data = param_data['process_time_hours'] if use_process_time and 'process_time_hours' in param_data.columns else param_data['timestamp']
            x_label = "Process Time (h)" if use_process_time and 'process_time_hours' in param_data.columns else "Time"
            
            # Original setpoint values (row 1)
            fig.add_trace(go.Scatter(
                x=x_data,
                y=param_data['value'],
                name=param,
                mode='lines+markers',
                line=dict(color=color, width=2),
                marker=dict(size=4),
                hovertemplate=(
                    f"<b>{param}</b><br>" +
                    f"{x_label}: %{{x}}<br>" +
                    f"Value: %{{y}}" + (f" {units}" if units else "") +
                    "<extra></extra>"
                ),
                showlegend=True
            ), row=1, col=1)
            
            # 1st derivative (row 2)
            if 'first_derivative' in param_data.columns:
                fig.add_trace(go.Scatter(
                    x=x_data,
                    y=param_data['first_derivative'],
                    name=f"{param} (1st)",
                    mode='lines',
                    line=dict(color=color, width=1, dash='dash'),
                    hovertemplate=(
                        f"<b>{param} - 1st Derivative</b><br>" +
                        f"{x_label}: %{{x}}<br>" +
                        f"Rate: %{{y}}" + (f" {units}/s" if units else " /s") +
                        "<extra></extra>"
                    ),
                    showlegend=False
                ), row=2, col=1)
            
            # 2nd derivative (row 3)
            if 'second_derivative' in param_data.columns:
                fig.add_trace(go.Scatter(
                    x=x_data,
                    y=param_data['second_derivative'],
                    name=f"{param} (2nd)",
                    mode='lines',
                    line=dict(color=color, width=1, dash='dot'),
                    hovertemplate=(
                        f"<b>{param} - 2nd Derivative</b><br>" +
                        f"{x_label}: %{{x}}<br>" +
                        f"Acceleration: %{{y}}" + (f" {units}/s²" if units else " /s²") +
                        "<extra></extra>"
                    ),
                    showlegend=False
                ), row=3, col=1)
        
        # Update layout
        fig.update_layout(
            title=dict(text=title, x=0.5, font=dict(size=16)),
            hovermode='closest',
            height=1200,  # Taller to accommodate 3 subplots
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            ),
            margin=dict(r=200)  # Make room for legend
        )
        
        # Update axes
        x_axis_title = "Process Time (hours)" if use_process_time else "Time"
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='lightgray',
            row=3, col=1,
            title=x_axis_title
        )
        
        # Update y-axes with appropriate titles
        fig.update_yaxes(title="Setpoint Value", row=1, col=1, showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(title="Rate of Change", row=2, col=1, showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(title="Acceleration", row=3, col=1, showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        return fig
    
    def run_interactive(self):
        """Run the interactive workflow."""
        print("Setpoint File Processor")
        print("=" * 30)
        
        # Discover files
        self.discover_files()
        
        if not self.parameter_groups:
            print("No setpoint files found!")
            return
        
        # Select parameters
        selected_params = self.select_parameters_interactive()
        
        if not selected_params:
            print("No parameters selected.")
            return
        
        # Load data
        data = self.load_selected_data(selected_params)
        
        if data.empty:
            print("No valid data found for selected parameters.")
            return
        
        # Create and show plot
        title = f"Setpoint Data: {', '.join(selected_params[:3])}"
        if len(selected_params) > 3:
            title += f" (+{len(selected_params)-3} more)"
        
        fig = self.create_plot(data, title)
        fig.show()
        
        # Print summary
        print(f"\nSummary:")
        print(f"- Parameters plotted: {len(selected_params)}")
        print(f"- Total data points: {len(data)}")
        print(f"- Time range: {data['timestamp'].min()} to {data['timestamp'].max()}")
        print(f"- Unique parameters: {len(data['parameter'].unique())}")

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Global processor instance
processor = SetpointProcessor()

# Define the app layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Process Setpoint Files Visualizer", className="text-center mb-4"),
        ])
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("1. Select Folder", className="card-title"),
                    html.P("Enter the folder path containing your setpoint files:", className="text-muted"),
                    dbc.InputGroup([
                        dbc.Input(
                            id="folder-path-input",
                            placeholder="Enter folder path (e.g., /path/to/your/data)",
                            type="text",
                            value="\\\\wsl.localhost\\Ubuntu\\home\\tpowers\\_Code\\ferm_process_version_json_builder\\04\\04"
                        ),
                        dbc.Button(
                            "Load Files",
                            id="load-folder-btn",
                            color="primary",
                            n_clicks=0
                        )
                    ], className="mb-3"),
                    html.P("Or drag and drop files directly:", className="text-muted mt-3"),
                    dcc.Upload(
                        id="upload-folder",
                        children=html.Div([
                            html.I(className="fas fa-file-csv fa-2x mb-2"),
                            html.Br(),
                            html.P("Drag & Drop CSV Files Here")
                        ], style={
                            'textAlign': 'center',
                            'padding': '20px',
                            'border': '2px dashed #ccc',
                            'borderRadius': '10px',
                            'cursor': 'pointer',
                            'backgroundColor': '#f8f9fa'
                        }),
                        style={
                            'width': '100%',
                            'minHeight': '120px'
                        },
                        multiple=True,
                        accept='.csv'
                    ),
                    html.Div(id="folder-display", className="mb-3")
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H4("2. Select Files", className="card-title"),
                    dbc.Row([
                        dbc.Col([
                            dbc.Input(
                                id="search-input",
                                placeholder="Search files...",
                                type="text",
                                className="mb-3"
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Button("Select All", id="select-all-btn", color="secondary", size="sm", className="me-2"),
                            dbc.Button("Clear All", id="clear-all-btn", color="secondary", size="sm")
                        ], width=6, className="text-end")
                    ]),
                    html.Div(id="file-list", className="mb-3"),
                    dbc.Button("Create Graph", id="graph-btn", color="success", size="lg", disabled=True)
                ])
            ], className="mb-4")
        ], width=12)
    ]),
    
    dbc.Row([
        dbc.Col([
            html.Div(id="graph-container")
        ], width=12)
    ]),
    
    # Store components for state management
    dcc.Store(id="folder-data"),
    dcc.Store(id="file-data"),
    dcc.Store(id="selected-files"),
    dcc.Store(id="variable-sp-collapsed", data=True),  # Start with Variable SP collapsed
    dcc.Store(id="named-sp-collapsed", data=False),   # Start with Named SP expanded
    
    # Add FontAwesome for icons
    html.Link(
        rel="stylesheet",
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
    )
], fluid=True)


@app.callback(
    [Output("folder-data", "data"),
     Output("folder-display", "children"),
     Output("file-data", "data")],
    [Input("load-folder-btn", "n_clicks"),
     Input("upload-folder", "contents")],
    [State("folder-path-input", "value"),
     State("upload-folder", "filename")],
    prevent_initial_call=True
)
def handle_folder_input(n_clicks, contents, folder_path, filenames):
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Handle folder path input
    if trigger_id == "load-folder-btn" and folder_path:
        if not os.path.exists(folder_path):
            folder_display = dbc.Alert(
                f"Folder '{folder_path}' does not exist. Please check the path.",
                color="danger"
            )
            return dash.no_update, folder_display, []
        
        processor.data_folder = folder_path
        files = processor.discover_files()
        
        if files:
            folder_display = dbc.Alert(
                f"Found {len(files)} setpoint files in '{folder_path}'",
                color="success"
            )
            return folder_path, folder_display, files
        else:
            folder_display = dbc.Alert(
                f"No CSV files with '_SP' in the name found in '{folder_path}'",
                color="warning"
            )
            return dash.no_update, folder_display, []
    
    # Handle drag & drop upload
    elif trigger_id == "upload-folder" and contents:
        files_data = []
        csv_files = []
        
        for content, filename in zip(contents, filenames):
            # Only process CSV files that contain "_SP"
            if filename.endswith('.csv') and '_SP' in filename:
                # Decode the file content
                content_type, content_string = content.split(',')
                decoded = base64.b64decode(content_string)
                
                # Create a temporary file path for processing
                temp_path = f"/tmp/{filename}"
                with open(temp_path, 'wb') as f:
                    f.write(decoded)
                
                files_data.append({
                    'path': temp_path,
                    'name': filename,
                    'selected': False
                })
                csv_files.append(temp_path)
        
        # Sort files alphabetically
        files_data.sort(key=lambda x: x['name'].lower())
        
        if files_data:
            folder_display = dbc.Alert(
                f"Uploaded {len(files_data)} setpoint files",
                color="success"
            )
            
            # Update processor with uploaded files
            processor.setpoint_files = csv_files
            processor.all_files = files_data
            
            return "uploaded_files", folder_display, files_data
        else:
            folder_display = dbc.Alert(
                "No CSV files with '_SP' in the name were found. Please upload setpoint CSV files.",
                color="warning"
            )
            return dash.no_update, folder_display, []
    
    return dash.no_update, dash.no_update, dash.no_update


# Server-side callbacks for toggle functionality
@app.callback(
    Output("variable-sp-collapsed", "data"),
    [Input("variable-sp-toggle", "n_clicks")],
    [State("variable-sp-collapsed", "data")],
    prevent_initial_call=True
)
def toggle_variable_sp(n_clicks, is_collapsed):
    return not is_collapsed if is_collapsed is not None else False

@app.callback(
    Output("named-sp-collapsed", "data"),
    [Input("named-sp-toggle", "n_clicks")],
    [State("named-sp-collapsed", "data")],
    prevent_initial_call=True
)
def toggle_named_sp(n_clicks, is_collapsed):
    return not is_collapsed if is_collapsed is not None else True

# Separate callback for handling just checkbox selections
@app.callback(
    Output("selected-files", "data"),
    [Input("select-all-btn", "n_clicks"),
     Input("clear-all-btn", "n_clicks"),
     Input({"type": "file-checkbox", "index": ALL}, "value")],
    [State("selected-files", "data"),
     State({"type": "file-checkbox", "index": ALL}, "id"),
     State("file-data", "data"),
     State("search-input", "value"),
     State("variable-sp-collapsed", "data"),
     State("named-sp-collapsed", "data")],
    prevent_initial_call=True
)
def update_selected_files(select_all_clicks, clear_all_clicks, checkbox_values, current_selected, checkbox_ids, file_data, search_value, var_collapsed, named_collapsed):
    print(f"Selection callback triggered. Context: {dash.callback_context.triggered}")
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return current_selected or []
    
    # Handle both old format (flat list) and new format (grouped dict)
    if not file_data:
        return []
    
    # Convert old format to new format if needed
    if isinstance(file_data, list):
        grouped_data = {'variable_sp': [], 'named_sp': file_data}
    else:
        grouped_data = file_data
    
    # Get all files for processing
    all_files = grouped_data.get('named_sp', []) + grouped_data.get('variable_sp', [])
    
    trigger_id = ctx.triggered[0]['prop_id']
    
    if "select-all-btn" in trigger_id:
        # Select all visible files (considering search and collapsed state)
        visible_files = []
        if search_value:
            visible_files = [f for f in all_files if search_value.lower() in f['name'].lower()]
        else:
            if not named_collapsed:
                visible_files.extend(grouped_data.get('named_sp', []))
            if not var_collapsed:
                visible_files.extend(grouped_data.get('variable_sp', []))
        return [f['path'] for f in visible_files]
        
    elif "clear-all-btn" in trigger_id:
        return []
    else:
        # Handle individual checkbox changes
        selected = []
        if checkbox_values and checkbox_ids:
            for i, (checkbox_id, value) in enumerate(zip(checkbox_ids, checkbox_values)):
                if value:  # If checkbox is checked
                    file_path = checkbox_id['index']
                    selected.append(file_path)
        return selected

# Separate callback for updating the file list display
@app.callback(
    Output("file-list", "children"),
    [Input("file-data", "data"),
     Input("search-input", "value"),
     Input("variable-sp-collapsed", "data"),
     Input("named-sp-collapsed", "data")],
    [State("selected-files", "data")],
    prevent_initial_call=True
)
def update_file_list_display(file_data, search_value, var_collapsed, named_collapsed, selected):
    # Default values for toggle states - ensure they're set properly
    if var_collapsed is None:
        var_collapsed = True  # Variable SP starts collapsed
    if named_collapsed is None:
        named_collapsed = False  # Named SP starts expanded
    
    selected = selected or []
    
    # Handle both old format (flat list) and new format (grouped dict)
    if not file_data:
        return html.P("No folder selected", className="text-muted")
    
    # Convert old format to new format if needed
    if isinstance(file_data, list):
        # Old format - convert to grouped format
        grouped_data = {'variable_sp': [], 'named_sp': file_data}
    else:
        # New format
        grouped_data = file_data
    
    selected = selected or []
    
    # Create grouped file list with collapsible sections
    file_list = []
    
    def create_file_checkboxes(files, group_name):
        """Create checkbox list for a group of files"""
        if not files:
            return []
        
        checkboxes = []
        for file_info in files:
            # Apply search filter
            if search_value and search_value.lower() not in file_info['name'].lower() and file_info['path'] not in selected:
                continue
                
            is_selected = file_info['path'] in selected
            
            checkbox = dbc.Checkbox(
                id={"type": "file-checkbox", "index": file_info['path']},
                value=is_selected,
                className="me-2"
            )
            
            file_item = dbc.Row([
                dbc.Col([
                    checkbox,
                    html.Label(file_info['name'], className="form-check-label", style={'fontSize': '0.9rem'})
                ], className="d-flex align-items-center")
            ], className="mb-1 ms-3")
            
            checkboxes.append(file_item)
        
        return checkboxes
    
    # Named SP section
    named_files = grouped_data.get('named_sp', [])
    if named_files:
        named_count = len([f for f in named_files if f['path'] in selected])
        total_named = len(named_files)
        
        named_header = dbc.Button(
            [
                html.I(className=f"fas fa-chevron-{'down' if not named_collapsed else 'right'} me-2"),
                f"Named SP ({named_count}/{total_named} selected)"
            ],
            id="named-sp-toggle",
            color="light",
            className="w-100 text-start mb-2",
            style={'border': '1px solid #dee2e6'},
            n_clicks=0  # Reset n_clicks to avoid stale state
        )
        file_list.append(named_header)
        
        if not named_collapsed:
            named_checkboxes = create_file_checkboxes(named_files, 'named_sp')
            if named_checkboxes:
                file_list.extend(named_checkboxes)
            else:
                file_list.append(html.P("No files match search", className="text-muted ms-3"))
    
    # Variable SP section
    var_files = grouped_data.get('variable_sp', [])
    if var_files:
        var_count = len([f for f in var_files if f['path'] in selected])
        total_var = len(var_files)
        
        var_header = dbc.Button(
            [
                html.I(className=f"fas fa-chevron-{'down' if not var_collapsed else 'right'} me-2"),
                f"Variable SP ({var_count}/{total_var} selected)"
            ],
            id="variable-sp-toggle",
            color="light",
            className="w-100 text-start mb-2",
            style={'border': '1px solid #dee2e6'},
            n_clicks=0  # Reset n_clicks to avoid stale state
        )
        file_list.append(var_header)
        
        if not var_collapsed:
            var_checkboxes = create_file_checkboxes(var_files, 'variable_sp')
            if var_checkboxes:
                file_list.extend(var_checkboxes)
            else:
                file_list.append(html.P("No files match search", className="text-muted ms-3"))
    
    if not file_list:
        content = html.P("No files found", className="text-muted")
    else:
        content = html.Div(file_list)
    
    return content


@app.callback(
    Output("graph-btn", "disabled"),
    [Input("selected-files", "data")]
)
def update_graph_button(selected_files):
    return not selected_files or len(selected_files) == 0


@app.callback(
    Output("graph-container", "children"),
    [Input("graph-btn", "n_clicks")],
    [State("selected-files", "data"),
     State("inoculation-time", "data"),
     State("show-negative-time", "data")],
    prevent_initial_call=True
)
def create_graph(n_clicks, selected_files, inoculation_time, show_negative_time):
    if not n_clicks or not selected_files:
        return html.Div()
    
    print(f"Creating graph for {len(selected_files)} files")
    
    if len(selected_files) > 5:
        print(f"Processing {len(selected_files)} files - this may take a moment...")
    
    # Load data for selected files
    all_data = []
    for i, file_path in enumerate(selected_files):
        print(f"Processing file {i+1}/{len(selected_files)}: {os.path.basename(file_path)}")
        df = processor.read_setpoint_file(file_path)
        if not df.empty:
            all_data.append(df)
        else:
            print(f"Warning: Empty data from {file_path}")
    
    if not all_data:
        return dbc.Alert("No valid data found in selected files", color="warning")
    
    print(f"Combining data from {len(all_data)} files")
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sort_values(['parameter', 'timestamp'])
    
    # Apply time offset based on toggle and inoculation time
    if inoculation_time:
        try:
            from datetime import datetime
            inoculation_dt = datetime.fromisoformat(inoculation_time.replace('Z', '+00:00'))
            
            # Convert timestamps to process time hours
            combined_df['process_time_hours'] = (combined_df['timestamp'] - inoculation_dt).dt.total_seconds() / 3600
            
            # Filter data based on toggle setting
            if not show_negative_time:
                # Only show data from inoculation time onwards (>= 0)
                combined_df = combined_df[combined_df['process_time_hours'] >= 0].copy()
            
            print(f"Applied time offset: {len(combined_df)} data points after filtering (show_negative: {show_negative_time})")
        except Exception as e:
            print(f"Error applying time offset: {e}")
            # Fall back to original timestamps
            combined_df['process_time_hours'] = None
    else:
        combined_df['process_time_hours'] = None
    
    print(f"Creating plot with {len(combined_df)} data points")
    # Create plot with time offset consideration
    title = f"Setpoint Data ({len(selected_files)} files selected)"
    fig = processor.create_plot(combined_df, title, use_process_time=bool(inoculation_time))
    
    print("Graph creation complete")
    return dbc.Card([
        dbc.CardBody([
            html.H4(f"Graph - {len(selected_files)} files, {len(combined_df)} data points"),
            dcc.Graph(figure=fig, style={'height': '800px'})
        ])
    ])


def main():
    # Create temporary directory if it doesn't exist
    import tempfile
    os.makedirs('/tmp', exist_ok=True)
    
    app.run_server(debug=True, host='127.0.0.1', port=8051)


if __name__ == "__main__":
    main()