#!/usr/bin/env python3
"""
Integrated Fermentation Process Builder
Main application combining profile builder with setpoint file analysis
"""

import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from datetime import datetime
import json

# Import our modules
from profile_builder import setup_profile_builder
from sidebar_file_selector import setup_file_selector
from sidebar_octopus import setup_octopus_sidebar
from component_builder import setup_component_builder

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Add drag and drop CSS and JavaScript
app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
      .component-block {
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        cursor: pointer;
        user-select: none;
      }
      .component-block:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      }
      .component-block.dragging {
        transform: scale(1.05);
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        z-index: 1000;
        background-color: #e3f2fd !important;
      }
      .drop-indicator {
        height: 3px;
        background-color: #2196f3;
        margin: 2px 0;
        border-radius: 2px;
        opacity: 0.8;
      }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
      <script>
        let isDragging = false;
        let draggedElement = null;
        let draggedIndex = null;
        let startY = 0;
        let blockHeight = 80;

        function initDragSystem() {
          const componentBlocks = document.querySelectorAll('.component-block');
          componentBlocks.forEach((block, index) => {
            if (!block.hasAttribute('data-drag-initialized')) {
              block.setAttribute('data-drag-initialized', 'true');
              block.addEventListener('mousedown', (e) => handleMouseDown(e, block, index));
            }
          });
        }

        function handleMouseDown(e, element, index) {
          if (e.button !== 0) return;
          isDragging = true;
          draggedElement = element;
          draggedIndex = index;
          startY = e.clientY;
          element.classList.add('dragging');
          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
          e.preventDefault();
        }

        function handleMouseMove(e) {
          if (!isDragging || !draggedElement) return;
          const componentBlocks = document.querySelectorAll('.component-block');
          const deltaY = e.clientY - startY;
          const blocksToMove = Math.round(deltaY / blockHeight);
          const targetIndex = Math.max(0, Math.min(componentBlocks.length - 1, draggedIndex + blocksToMove));
          
          document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
          if (targetIndex !== draggedIndex) {
            const indicator = document.createElement('div');
            indicator.className = 'drop-indicator';
            if (targetIndex < draggedIndex) {
              componentBlocks[targetIndex].parentNode.insertBefore(indicator, componentBlocks[targetIndex]);
            } else {
              componentBlocks[targetIndex].parentNode.insertBefore(indicator, componentBlocks[targetIndex].nextSibling);
            }
          }
        }

        function handleMouseUp(e) {
          if (!isDragging || !draggedElement) return;
          const deltaY = e.clientY - startY;
          const blocksToMove = Math.round(deltaY / blockHeight);
          const componentBlocks = document.querySelectorAll('.component-block');
          const toIndex = Math.max(0, Math.min(componentBlocks.length - 1, draggedIndex + blocksToMove));
          draggedElement.classList.remove('dragging');
          document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
          if (toIndex !== draggedIndex) {
            window.pendingDragData = {fromIndex: draggedIndex, toIndex: toIndex};
            const triggerBtn = document.getElementById('drag-trigger-btn');
            if (triggerBtn) {
              triggerBtn.click();
            }
          }
          isDragging = false;
          draggedElement = null;
          draggedIndex = null;
          document.removeEventListener('mousemove', handleMouseMove);
          document.removeEventListener('mouseup', handleMouseUp);
        }

        document.addEventListener('DOMContentLoaded', initDragSystem);
        new MutationObserver(initDragSystem).observe(document.body, {childList: true, subtree: true});
      </script>
    </footer>
  </body>
</html>
"""

# Define the main layout
app.layout = html.Div([
    # Sidebar toggle icons (fixed position)
    html.Div([
        dbc.Button(
            html.I(className="fas fa-file", style={"fontSize": "20px"}),
            id="file-sidebar-toggle",
            color="primary",
            size="lg",
            className="me-2",
            style={
                "position": "fixed",
                "top": "20px",
                "left": "20px",
                "zIndex": "1050",
                "borderRadius": "50%",
                "width": "50px",
                "height": "50px"
            }
        ),
        dbc.Button([
            html.Div([
                html.I(className="fas fa-circle", style={"color": "#007bff", "fontSize": "30px"}),
                html.Span("B", style={
                    "position": "absolute",
                    "top": "50%", 
                    "left": "50%",
                    "transform": "translate(-50%, -50%)",
                    "color": "white",
                    "fontWeight": "bold",
                    "fontSize": "16px"
                })
            ], style={"position": "relative", "display": "inline-block"})
        ],
            id="octopus-sidebar-toggle",
            color="info",
            size="lg",
            style={
                "position": "fixed",
                "top": "80px",
                "left": "20px",
                "zIndex": "1050",
                "borderRadius": "50%",
                "width": "50px",
                "height": "50px",
                "border": "none",
                "backgroundColor": "transparent"
            }
        )
    ]),
    
    # File Selector Sidebar (overlay, 1/2 screen width)
    html.Div([
        html.Div([
            # Close button
            dbc.Button(
                html.I(className="fas fa-times"),
                id="file-sidebar-close",
                color="light",
                size="sm",
                style={"position": "absolute", "top": "10px", "right": "10px"}
            ),
            
            # Sidebar content will be populated by sidebar_file_selector module
            html.Div(id="file-sidebar-content", children=[
                html.H4("File Selector", className="mb-4"),
                html.P("Loading file selector...", className="text-muted")
            ])
        ], style={
            "padding": "20px",
            "height": "100vh",
            "overflowY": "auto",
            "backgroundColor": "#f8f9fa"
        })
    ], 
        id="file-sidebar",
        style={
            "position": "fixed",
            "top": "0",
            "left": "-50vw",  # Hidden by default
            "width": "50vw",
            "height": "100vh",
            "backgroundColor": "#f8f9fa",
            "boxShadow": "2px 0 5px rgba(0,0,0,0.1)",
            "zIndex": "1040",
            "transition": "left 0.3s ease-in-out"
        }
    ),
    
    # Octopus Sidebar (overlay, smaller width)
    html.Div([
        html.Div([
            # Close button
            dbc.Button(
                html.I(className="fas fa-times"),
                id="octopus-sidebar-close",
                color="light",
                size="sm",
                style={"position": "absolute", "top": "10px", "right": "10px"}
            ),
            
            # Sidebar content (placeholder for now)
            html.Div(id="octopus-sidebar-content", children=[
                html.H4("Octopus Sidebar", className="mb-4"),
                html.P("Future functionality will go here...", className="text-muted")
            ])
        ], style={
            "padding": "20px",
            "height": "100vh",
            "overflowY": "auto",
            "backgroundColor": "#e3f2fd"
        })
    ], 
        id="octopus-sidebar",
        style={
            "position": "fixed",
            "top": "0",
            "left": "-30vw",  # Hidden by default
            "width": "30vw",
            "height": "100vh",
            "backgroundColor": "#e3f2fd",
            "boxShadow": "2px 0 5px rgba(0,0,0,0.1)",
            "zIndex": "1040",
            "transition": "left 0.3s ease-in-out"
        }
    ),
    
    # Main content area (profile builder)
    html.Div([
        dbc.Container([
            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("Fermentation Profile Builder", className="text-center mb-4"),
                ], width=12)
            ]),
            
            # Inoculation time picker (global for setpoint alignment)
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("Inoculation Time", className="card-title"),
                            html.P("Set the inoculation time to align setpoint data with profile timeline:", 
                                   className="text-muted mb-3"),
                            dbc.InputGroup([
                                dbc.Input(
                                    id="inoculation-datetime",
                                    type="datetime-local",
                                    value=datetime.now().strftime("%Y-%m-%dT%H:%M")
                                ),
                                dbc.Button("Update Alignment", id="update-alignment-btn", color="primary")
                            ])
                        ])
                    ], className="mb-4")
                ], width=12)
            ]),
            
            # Profile builder content
            dbc.Row([
                dbc.Col([
                    html.Div(id="profile-builder-content")
                ], width=12)
            ]),
            
            # Graph area (will show profile + setpoint overlay)
            dbc.Row([
                dbc.Col([
                    # Toggle controls above graph
                    dbc.Card([
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.H5("Profile & Setpoint Visualization", className="card-title mb-0")
                                ], width=8),
                                dbc.Col([
                                    dbc.Checkbox(
                                        id="show-negative-time",
                                        label="Show data before inoculation",
                                        value=False,
                                        className="text-end"
                                    )
                                ], width=4, className="d-flex align-items-center justify-content-end")
                            ], className="mb-3"),
                            dcc.Graph(
                                id="integrated-graph",
                                style={'height': '600px'},
                                figure=go.Figure().add_annotation(
                                    text="Graph will show profile + setpoint overlay",
                                    x=0.5, y=0.5, showarrow=False
                                )
                            )
                        ])
                    ])
                ], width=12)
            ])
        ], fluid=True)
    ], 
        id="main-content",
        style={
            "marginLeft": "0px",
            "transition": "margin-left 0.3s ease-in-out",
            "minHeight": "100vh"
        }
    ),
    
    # Data stores for cross-module communication
    dcc.Store(id="file-sidebar-open", data=False),
    dcc.Store(id="octopus-sidebar-open", data=False),
    dcc.Store(id="selected-setpoint-files", data=[]),
    dcc.Store(id="setpoint-data", data={}),
    dcc.Store(id="profile-components", data=[]),
    dcc.Store(id="inoculation-time", data=None),
    dcc.Store(id="generated-components", data=[]),
    dcc.Store(id="selected-component", data=None),
    dcc.Store(id="show-negative-time", data=False),
    
    # Additional stores for file selector
    dcc.Store(id="file-data-store", data={}),
    dcc.Store(id="named-sp-collapsed", data=False),
    dcc.Store(id="variable-sp-collapsed", data=True),
    
    # Add FontAwesome for icons
    html.Link(
        rel="stylesheet",
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
    )
], style={"position": "relative"})


# Sidebar toggle callbacks
@app.callback(
    [Output("file-sidebar", "style"),
     Output("file-sidebar-open", "data")],
    [Input("file-sidebar-toggle", "n_clicks"),
     Input("file-sidebar-close", "n_clicks")],
    [State("file-sidebar-open", "data")],
    prevent_initial_call=True
)
def toggle_file_sidebar(toggle_clicks, close_clicks, is_open):
    ctx = dash.callback_context
    
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Close octopus sidebar if file sidebar is opening
        if trigger_id == "file-sidebar-toggle" and not is_open:
            new_open = True
        else:
            new_open = not is_open if trigger_id == "file-sidebar-toggle" else False
        
        sidebar_style = {
            "position": "fixed",
            "top": "0",
            "left": "0" if new_open else "-50vw",
            "width": "50vw",
            "height": "100vh",
            "backgroundColor": "#f8f9fa",
            "boxShadow": "2px 0 5px rgba(0,0,0,0.1)",
            "zIndex": "1040",
            "transition": "left 0.3s ease-in-out"
        }
        
        return sidebar_style, new_open
    
    return dash.no_update, dash.no_update


@app.callback(
    [Output("octopus-sidebar", "style"),
     Output("octopus-sidebar-open", "data")],
    [Input("octopus-sidebar-toggle", "n_clicks"),
     Input("octopus-sidebar-close", "n_clicks")],
    [State("octopus-sidebar-open", "data"),
     State("file-sidebar-open", "data")],
    prevent_initial_call=True
)
def toggle_octopus_sidebar(toggle_clicks, close_clicks, is_open, file_sidebar_open):
    ctx = dash.callback_context
    
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if trigger_id == "octopus-sidebar-toggle" and not is_open:
            new_open = True
        else:
            new_open = not is_open if trigger_id == "octopus-sidebar-toggle" else False
        
        sidebar_style = {
            "position": "fixed",
            "top": "0",
            "left": "0" if new_open else "-30vw",
            "width": "30vw",
            "height": "100vh",
            "backgroundColor": "#e3f2fd",
            "boxShadow": "2px 0 5px rgba(0,0,0,0.1)",
            "zIndex": "1040",
            "transition": "left 0.3s ease-in-out"
        }
        
        return sidebar_style, new_open
    
    return dash.no_update, dash.no_update


# Close sidebar when clicking the other toggle
@app.callback(
    Output("file-sidebar-open", "data", allow_duplicate=True),
    [Input("octopus-sidebar-toggle", "n_clicks")],
    [State("octopus-sidebar-open", "data")],
    prevent_initial_call=True
)
def close_file_sidebar_on_octopus_open(octopus_clicks, octopus_open):
    if octopus_clicks and not octopus_open:
        return False
    return dash.no_update


@app.callback(
    Output("octopus-sidebar-open", "data", allow_duplicate=True),
    [Input("file-sidebar-toggle", "n_clicks")],
    [State("file-sidebar-open", "data")],
    prevent_initial_call=True
)
def close_octopus_sidebar_on_file_open(file_clicks, file_open):
    if file_clicks and not file_open:
        return False
    return dash.no_update


# Inoculation time callback - from manual input
@app.callback(
    Output("inoculation-time", "data"),
    [Input("update-alignment-btn", "n_clicks"),
     Input("file-data-store", "data")],
    [State("inoculation-datetime", "value")],
    prevent_initial_call=True
)
def update_inoculation_time(n_clicks, file_data, datetime_value):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # If manual update button was clicked
    if trigger_id == "update-alignment-btn" and n_clicks and datetime_value:
        return datetime_value
    
    # If file data was loaded, try to extract inoculation time
    elif trigger_id == "file-data-store" and file_data:
        inoculation_time = file_data.get('inoculation_time')
        if inoculation_time:
            print(f"Auto-setting inoculation time from files: {inoculation_time}")
            return inoculation_time
    
    return dash.no_update


# Profile builder content callback
@app.callback(
    Output("profile-builder-content", "children"),
    [Input("file-sidebar-open", "data")]  # Trigger on any state change
)
def update_profile_builder_content(trigger):
    """Load the profile builder layout"""
    return profile_builder.get_layout()

# Integrated graph callback - overlays profile + setpoint data
@app.callback(
    Output("integrated-graph", "figure"),
    [Input("profile-components", "data"),
     Input("setpoint-data", "data"),
     Input("inoculation-time", "data")],
    prevent_initial_call=True
)
def update_integrated_graph(profile_components, setpoint_data, inoculation_time):
    """
    Main graph that overlays:
    - Profile components (blue, solid lines)
    - Setpoint data (red, dashed lines)
    """
    fig = go.Figure()
    
    # Plot profile components (blue, solid)
    if profile_components:
        profile_times, profile_values = generate_profile_timeline(profile_components)
        if profile_times and profile_values:
            fig.add_trace(go.Scatter(
                x=profile_times,
                y=profile_values,
                mode='lines',
                name='Profile',
                line=dict(color='blue', width=3),
                hovertemplate='Profile<br>Time: %{x:.1f}h<br>Value: %{y}<extra></extra>'
            ))
    
    # Plot setpoint data (red, dashed) 
    if setpoint_data:
        for filename, file_info in setpoint_data.items():
            # Convert setpoint data for plotting
            setpoint_times, setpoint_values = convert_setpoint_for_plotting(
                file_info['data'], inoculation_time
            )
            
            if setpoint_times and setpoint_values:
                fig.add_trace(go.Scatter(
                    x=setpoint_times,
                    y=setpoint_values,
                    mode='lines',
                    name=f'Setpoint: {file_info["parameter"]}',
                    line=dict(color='red', width=2, dash='dash'),
                    hovertemplate=f'{file_info["parameter"]}<br>Time: %{{x:.1f}}h<br>Value: %{{y}}<extra></extra>'
                ))
    
    # Determine x-axis range based on data
    x_max = 0
    
    # Get max time from profile components
    if profile_components and profile_times:
        x_max = max(x_max, max(profile_times))
    
    # Get max time from setpoint data
    if setpoint_data:
        for filename, file_info in setpoint_data.items():
            setpoint_times, _ = convert_setpoint_for_plotting(file_info['data'], inoculation_time)
            if setpoint_times:
                x_max = max(x_max, max(setpoint_times))
    
    # Update layout with dynamic x-axis range
    layout_kwargs = {
        'title': "Profile & Setpoint Visualization",
        'xaxis_title': "Time (hours)",
        'yaxis_title': "Value", 
        'height': 600,
        'hovermode': 'closest',
        'legend': dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02)
    }
    
    # Set x-axis range if we have data
    if x_max > 0:
        # Add 5% padding to the right
        x_range_max = x_max * 1.05
        layout_kwargs['xaxis'] = dict(range=[0, x_range_max])
    
    fig.update_layout(**layout_kwargs)
    
    # Add annotation if no data
    if not profile_components and not setpoint_data:
        fig.add_annotation(
            text="Add profile components or load setpoint files to see visualization",
            x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="gray")
        )
    
    return fig

def generate_profile_timeline(components):
    """Generate timeline from profile components - matches original app.py exactly"""
    if not components:
        return [], []
    
    t_points, y_points = [], []
    current_time = 0
    
    for comp in components:
        dur = comp["duration"]
        if comp["type"] == "constant":
            t_points += [current_time, current_time + dur]
            y_points += [comp["setpoint"], comp["setpoint"]]
        elif comp["type"] == "ramp":
            t_points += [current_time, current_time + dur]
            y_points += [comp["start_temp"], comp["end_temp"]]
        elif comp["type"] == "pwm":
            cycles = max(10, dur // 5)
            cycle_time = dur / cycles
            high_time = cycle_time * (comp["pulse_percent"] / 100)
            for _ in range(cycles):
                t_points += [current_time, current_time, current_time + high_time, current_time + high_time, current_time + cycle_time]
                y_points += [comp["low_temp"], comp["high_temp"], comp["high_temp"], comp["low_temp"], comp["low_temp"]]
                current_time += cycle_time
            continue  # Skip the current_time += dur at the end since we already advanced it
        elif comp["type"] == "pid":
            # For PID, just show the setpoint line (shapes will be added separately)
            setpoint = comp.get("setpoint", 0)
            t_points += [current_time, current_time + dur]
            y_points += [setpoint, setpoint]
        
        current_time += dur
    
    return t_points, y_points

def convert_setpoint_for_plotting(setpoint_data, inoculation_time):
    """Convert setpoint data to plotting format with time alignment"""
    if not setpoint_data or not inoculation_time:
        return [], []
    
    import pandas as pd
    
    # Convert to DataFrame
    df = pd.DataFrame(setpoint_data)
    if df.empty:
        return [], []
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    # Handle inoculation time with proper error handling
    if inoculation_time:
        try:
            inoculation_dt = pd.to_datetime(inoculation_time, errors='coerce')
            if pd.isna(inoculation_dt):
                # Invalid datetime, use first timestamp as reference
                inoculation_dt = df['timestamp'].min()
        except:
            # Fallback to first timestamp
            inoculation_dt = df['timestamp'].min()
    else:
        # No inoculation time provided, use first timestamp
        inoculation_dt = df['timestamp'].min()
    
    # Calculate hours from inoculation
    df['hours_from_inoculation'] = (df['timestamp'] - inoculation_dt).dt.total_seconds() / 3600
    
    # Filter to post-inoculation data only (only if we have a valid inoculation time)
    if inoculation_time:
        df = df[df['hours_from_inoculation'] >= 0]
    
    if df.empty:
        return [], []
    
    return df['hours_from_inoculation'].tolist(), df['value'].tolist()


# Checkbox callback for negative time toggle
@app.callback(
    Output("show-negative-time", "data"),
    [Input("show-negative-time", "value")],
    prevent_initial_call=True
)
def update_negative_time_toggle(checkbox_value):
    # Just update the toggle state - graph display will handle the rest
    return checkbox_value


# Initialize all modules
profile_builder = setup_profile_builder(app)
file_selector = setup_file_selector(app)
octopus_sidebar = setup_octopus_sidebar(app)
component_builder = setup_component_builder(app)

def main():
    """Main entry point for the integrated application"""
    print("🚀 Starting Integrated Fermentation Profile Builder...")
    print("📊 Features enabled:")
    print("  ✅ Profile Builder with drag & drop")
    print("  ✅ Setpoint File Selector with analysis")
    print("  ✅ Intelligent Component Generation")
    print("  ✅ Graph Overlay (Profile + Setpoints)")
    print("  ✅ Modular Architecture")
    print("\n🌐 Access the application at: http://127.0.0.1:8052")
    
    app.run(debug=True, host='127.0.0.1', port=8052)


if __name__ == "__main__":
    main()