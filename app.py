import dash
from dash import dcc, html, Input, Output, State, ALL, ctx
import plotly.graph_objects as go
import json
import uuid
import dash_bootstrap_components as dbc

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# ===== JS for drag-and-drop =====
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
        let blockHeight = 0;
        let componentBlocks = [];

        function getBlocks() {
          return Array.from(document.querySelectorAll('.component-block'));
        }

        function initDragSystem() {
          componentBlocks = getBlocks();
          componentBlocks.forEach((block) => {
            block.removeEventListener('mousedown', handleMouseDown);
            block.addEventListener('mousedown', handleMouseDown);
            block.style.position = 'relative';
          });
          document.removeEventListener('mousemove', handleMouseMove);
          document.removeEventListener('mouseup', handleMouseUp);
          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
        }

        function handleMouseDown(e) {
          if (e.target.closest('[data-no-drag]')) return;
          e.preventDefault();
          isDragging = true;
          draggedElement = this;
          componentBlocks = getBlocks();
          draggedIndex = componentBlocks.indexOf(this);
          startY = e.clientY;
          blockHeight = this.offsetHeight + 10;
          this.classList.add('dragging');
        }

        function handleMouseMove(e) {
          if (!isDragging || !draggedElement) return;
          const deltaY = e.clientY - startY;
          const blocksToMove = Math.round(deltaY / blockHeight);
          document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
          if (Math.abs(blocksToMove) > 0) {
            const targetIndex = Math.max(0, Math.min(componentBlocks.length - 1, draggedIndex + blocksToMove));
            if (targetIndex !== draggedIndex) {
              const indicator = document.createElement('div');
              indicator.className = 'drop-indicator';
              if (targetIndex > draggedIndex) {
                componentBlocks[targetIndex].parentNode.insertBefore(indicator, componentBlocks[targetIndex].nextSibling);
              } else {
                componentBlocks[targetIndex].parentNode.insertBefore(indicator, componentBlocks[targetIndex]);
              }
            }
          }
        }

        function handleMouseUp(e) {
          if (!isDragging || !draggedElement) return;
          const deltaY = e.clientY - startY;
          const blocksToMove = Math.round(deltaY / blockHeight);
          const toIndex = Math.max(0, Math.min(componentBlocks.length - 1, draggedIndex + blocksToMove));
          draggedElement.classList.remove('dragging');
          document.querySelectorAll('.drop-indicator').forEach(el => el.remove());
          if (toIndex !== draggedIndex) {
            // Store drag data globally
            window.pendingDragData = {fromIndex: draggedIndex, toIndex: toIndex};
            console.log('Drag completed:', window.pendingDragData);
            
            // Click the hidden button to trigger the callback
            const triggerBtn = document.getElementById('drag-trigger-btn');
            if (triggerBtn) {
              triggerBtn.click();
            }
          }
          isDragging = false;
          draggedElement = null;
          draggedIndex = null;
        }

        document.addEventListener('DOMContentLoaded', initDragSystem);
        new MutationObserver(initDragSystem).observe(document.body, {childList: true, subtree: true});
      </script>
    </footer>
  </body>
</html>
"""

# ===== Layout =====
app.layout = html.Div([
    html.H1(id="main-title", children="Fermentation Profile Builder", className="text-center mb-4"),
    
    # Process Configuration at the top
    html.Div([
        html.Div([
            html.Label("Process Type:"),
            dcc.Dropdown(
                id="process-type",
                options=[
                    {"label": "Agitation", "value": "Agitation"},
                    {"label": "pH", "value": "pH"},
                    {"label": "Acid", "value": "Acid"},
                    {"label": "Base", "value": "Base"},
                    {"label": "Media A", "value": "Media A"},
                    {"label": "Temperature", "value": "Temperature"}
                ],
                placeholder="Select process type"
            )
        ], className="col-md-6"),
        html.Div([
            html.Label("Organism:"),
            dcc.Dropdown(
                id="organism",
                options=[
                    {"label": "Bl", "value": "Bl"},
                    {"label": "Bs", "value": "Bs"},
                    {"label": "Ao", "value": "Ao"},
                    {"label": "An", "value": "An"},
                    {"label": "Ec", "value": "Ec"}
                ],
                placeholder="Select organism"
            )
        ], className="col-md-6")
    ], className="row mb-4"),

    html.Div([
        html.Div([
            html.H3("Component Builder"),
            html.Label("Component Type:"),
            dcc.Dropdown(
                id="component-type",
                options=[
                    {"label": "Constant", "value": "constant"},
                    {"label": "Ramp", "value": "ramp"},
                    {"label": "PWM", "value": "pwm"},
                    {"label": "PID", "value": "pid"}
                ],
                placeholder="Select component type"
            ),
            html.Div(id="dynamic-fields", className="mb-3"),
            html.Button("Add Component", id="add-btn", className="btn btn-primary", disabled=True)
        ], className="col-md-6"),

        html.Div([
            html.H3(id="components-title", children="Profile Components"),
            html.Div(id="component-list", style={
                "minHeight": "200px",
                "border": "2px dashed #ccc",
                "borderRadius": "5px",
                "padding": "10px"
            }),
            html.Div([
                html.Button("Move Up", id="move-up-btn", className="btn btn-secondary me-2"),
                html.Button("Move Down", id="move-down-btn", className="btn btn-secondary me-2"),
                html.Button("Remove", id="remove-btn", className="btn btn-danger me-2"),
                html.Button("Export JSON", id="export-btn", className="btn btn-success")
            ], className="mt-3"),
            html.Div(id="json-output", className="mt-3")
        ], className="col-md-6")
    ], className="row mb-4"),

    html.Div([
        html.Div([
            html.Div([
                html.H3(id="graph-title", children="Profile Graph", style={"display": "inline-block", "marginRight": "20px"}),
                html.Div([
                    dcc.Checklist(
                        id="x-axis-toggle",
                        options=[{"label": " Fix X-axis to organism runtime", "value": "fixed"}],
                        value=[],
                        style={"display": "inline-block"}
                    )
                ], style={"display": "inline-block", "verticalAlign": "top", "marginTop": "10px"})
            ]),
            dcc.Graph(id="temp-graph")
        ], className="col-12")
    ], className="row"),

    dcc.Store(id="components-store", data=[]),
    dcc.Store(id="selected-component", data=None),
    dcc.Store(id="pid-controller-count", data=1),
    dcc.Store(id="total-runtime", data=0),  # Total runtime in hours
    dcc.Store(id="used-runtime", data=0),   # Used runtime in hours
    dcc.Store(id="drag-data", data={"fromIndex": None, "toIndex": None}),
    html.Button(id="drag-trigger-btn", style={"display": "none"}),
    html.Div(id="drag-output", style={"display": "none"})
])

# ===== Helpers =====
def move_item(lst, from_idx, to_idx):
    if from_idx is None or to_idx is None or from_idx == to_idx:
        return lst
    to_idx = max(0, min(len(lst) - 1, to_idx))
    new_list = lst.copy()
    item = new_list.pop(from_idx)
    new_list.insert(to_idx, item)
    return new_list

# ===== Callbacks =====

# Update dynamic titles based on process type
@app.callback(
    [Output("main-title", "children"),
     Output("components-title", "children"),
     Output("graph-title", "children")],
    Input("process-type", "value")
)
def update_titles(process_type):
    if not process_type:
        return "Fermentation Profile Builder", "Profile Components", "Profile Graph"
    
    return (
        f"Fermentation {process_type} Profile Builder",
        f"{process_type} Profile Components", 
        f"{process_type} Profile Graph"
    )

# Set total runtime based on organism selection
@app.callback(
    Output("total-runtime", "data"),
    Input("organism", "value")
)
def set_total_runtime(organism):
    if not organism:
        return 0
    
    # Set runtime based on organism (in hours)
    runtime_map = {
        "Bl": 5 * 24,  # 5 days = 120 hours
        "Bs": 5 * 24,  # 5 days = 120 hours
        "Ao": 7 * 24,  # 7 days = 168 hours
        "An": 7 * 24,  # 7 days = 168 hours
        "Ec": 3 * 24   # 3 days = 72 hours
    }
    
    return runtime_map.get(organism, 0)
@app.callback(
    [Output("dynamic-fields", "children"),
     Output("add-btn", "disabled"),
     Output("pid-controller-count", "data")],
    [Input("component-type", "value"),
     Input("pid-controller-count", "data"),
     Input("process-type", "value")],
    [State({"type": "dynamic-input", "id": ALL}, "value"),
     State({"type": "dynamic-input", "id": ALL}, "id"),
     State({"type": "pid-input", "controller": ALL, "field": ALL}, "value"),
     State({"type": "pid-input", "controller": ALL, "field": ALL}, "id")]
)
def update_fields(component_type, controller_count, process_type, dynamic_values, dynamic_ids, pid_values, pid_ids):
    if not component_type:
        return [], True, 1
    
    # Helper function to get preserved dynamic input value
    def get_preserved_value(field_id):
        if dynamic_values and dynamic_ids:
            for val, input_id in zip(dynamic_values, dynamic_ids):
                if input_id.get("id") == field_id and val is not None:
                    return val
        return ""
    
    # Helper function to get units and labels based on process type
    def get_units_and_labels(process_type):
        if process_type == "Temperature":
            return "°C", "Temperature"
        elif process_type == "Agitation":
            return "RPM", "Agitation Rate"
        elif process_type == "pH":
            return "", "pH"
        elif process_type == "Acid":
            return "mL/h", "Acid Flow Rate"
        elif process_type == "Base":
            return "mL/h", "Base Flow Rate"
        elif process_type == "Media A":
            return "mL/h", "Media A Flow Rate"
        else:
            return "°C", "Temperature"  # Default to temperature when no process type selected
    
    # Helper function to get units for individual controller types
    def get_controller_units(controller_name):
        if controller_name == "Temperature":
            return "°C"
        elif controller_name == "Agitation":
            return "RPM"
        elif controller_name == "pH":
            return ""
        elif controller_name == "Acid":
            return "mL/h"
        elif controller_name == "Base":
            return "mL/h"
        elif controller_name == "Media A":
            return "mL/h"
        else:
            return "°C"  # Default to temperature units
    
    if component_type != "pid":
        # Reset PID controller count when switching away from PID
        controller_count = 1
        
    fields = []
    unit, value_label = get_units_and_labels(process_type)
    
    if component_type == "constant":
        fields = [
            html.Div([html.Label("Duration (hours):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", min=0, step=0.0001, value="")], className="mb-2"),
            html.Div([html.Label(f"{value_label} Setpoint ({unit}):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "setpoint"}, type="number", step=0.0001, value="")], className="mb-2")
        ]
    elif component_type == "ramp":
        fields = [
            html.Div([html.Label("Duration (hours):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", min=0, step=0.0001, value="")], className="mb-2"),
            html.Div([html.Label(f"Start {value_label} ({unit}):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "start_temp"}, type="number", step=0.0001, value="")], className="mb-2"),
            html.Div([html.Label(f"End {value_label} ({unit}):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "end_temp"}, type="number", step=0.0001, value="")], className="mb-2")
        ]
    elif component_type == "pwm":
        fields = [
            html.Div([html.Label("Duration (hours):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", min=0, step=0.0001, value="")], className="mb-2"),
            html.Div([html.Label(f"High {value_label} ({unit}):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "high_temp"}, type="number", step=0.0001, value="")], className="mb-2"),
            html.Div([html.Label(f"Low {value_label} ({unit}):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "low_temp"}, type="number", step=0.0001, value="")], className="mb-2"),
            html.Div([html.Label("Pulse Percentage (%):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "pulse_percent"}, type="number", min=0, max=100, step=0.01, value="")], className="mb-2")
        ]
    elif component_type == "pid":
        # Check if we need to add another controller set
        if pid_values and pid_ids:
            # Organize values by controller
            controller_data = {}
            for val, input_id in zip(pid_values, pid_ids):
                if isinstance(input_id, dict) and "controller" in input_id and "field" in input_id:
                    controller_idx = input_id["controller"]
                    field = input_id["field"]
                    if controller_idx not in controller_data:
                        controller_data[controller_idx] = {}
                    controller_data[controller_idx][field] = val
            
            # Check if the last controller has controller name filled (trigger for new controller)
            if controller_count - 1 in controller_data:
                last_controller = controller_data[controller_count - 1]
                if (last_controller.get("controller") and 
                    last_controller.get("controller").strip() and 
                    controller_count < 5):  # Limit to 5 controllers max
                    controller_count += 1
        
        # Add shared PID parameters (duration and setpoint)
        fields.append(html.Div([
            html.H5("PID Configuration", className="mt-3 mb-2"),
            html.Div([html.Label("Duration (hours):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", min=0, step=0.0001, value=get_preserved_value("duration"))], className="mb-2"),
            html.Div([html.Label(f"Setpoint ({unit}):"),
                      dcc.Input(id={"type": "dynamic-input", "id": "setpoint"}, type="number", step=0.0001, value=get_preserved_value("setpoint"))], className="mb-2")
        ], style={"border": "1px solid #ddd", "padding": "10px", "borderRadius": "5px", "marginBottom": "10px"}))
        
        # Add individual controller configurations
        fields.append(html.H5("Controllers", className="mt-3 mb-2"))
        for i in range(controller_count):
            # Preserve existing values if available
            controller_name = None
            controller_min = ""
            controller_max = ""
            
            if pid_values and pid_ids:
                for val, input_id in zip(pid_values, pid_ids):
                    if isinstance(input_id, dict) and input_id.get("controller") == i:
                        field = input_id.get("field")
                        if field == "controller" and val:
                            controller_name = val
                        elif field == "min_allowed" and val is not None:
                            controller_min = val
                        elif field == "max_allowed" and val is not None:
                            controller_max = val
            
            # Controller selection and configuration
            controller_fields = [
                html.Div([
                    html.Label(f"Controller {i+1} Name:"),
                    dcc.Dropdown(
                        id={"type": "pid-input", "controller": i, "field": "controller"},
                        options=[
                            {"label": "Agitation", "value": "Agitation"},
                            {"label": "pH", "value": "pH"},
                            {"label": "Acid", "value": "Acid"},
                            {"label": "Base", "value": "Base"},
                            {"label": "Media A", "value": "Media A"},
                            {"label": "Temperature", "value": "Temperature"}
                        ],
                        placeholder=f"Select Controller {i+1}",
                        value=controller_name
                    )
                ], className="mb-2")
            ]
            
            # Show configuration fields if a controller is selected
            if controller_name:
                controller_fields.extend([
                    html.Div([html.Label(f"Minimum Allowed ({unit}):"),
                              dcc.Input(id={"type": "pid-input", "controller": i, "field": "min_allowed"}, 
                                       type="number", step=0.0001, value=controller_min)], className="mb-2"),
                    html.Div([html.Label(f"Maximum Allowed ({unit}):"),
                              dcc.Input(id={"type": "pid-input", "controller": i, "field": "max_allowed"}, 
                                       type="number", step=0.0001, value=controller_max)], className="mb-2")
                ])
            
            fields.append(html.Div(controller_fields, 
                          style={"border": "1px solid #ddd", "padding": "10px", "borderRadius": "5px", "marginBottom": "10px"}))
    
    return fields, False, controller_count

# Separate callback to handle PID controller auto-addition
@app.callback(
    Output("pid-controller-count", "data", allow_duplicate=True),
    Input({"type": "pid-input", "controller": ALL, "field": ALL}, "value"),
    State("pid-controller-count", "data"),
    State("component-type", "value"),
    prevent_initial_call=True
)
def auto_add_pid_controller(pid_values, controller_count, component_type):
    if component_type != "pid" or not pid_values:
        return controller_count
    
    # Check if we need to add another controller field
    if len(pid_values) > 0:
        # Get the last controller name value (dropdown selection)
        last_value = pid_values[-1] if pid_values else None
        if last_value and controller_count < 5:
            return controller_count + 1
    
    return controller_count

@app.callback(
    [Output("components-store", "data", allow_duplicate=True),
     Output("used-runtime", "data")],
    Input("add-btn", "n_clicks"),
    [State("component-type", "value"),
     State({"type": "dynamic-input", "id": ALL}, "value"),
     State({"type": "dynamic-input", "id": ALL}, "id"),
     State({"type": "pid-input", "controller": ALL, "field": ALL}, "value"),
     State({"type": "pid-input", "controller": ALL, "field": ALL}, "id"),
     State("components-store", "data"),
     State("total-runtime", "data"),
     State("used-runtime", "data")],
    prevent_initial_call=True
)
def add_component(_, comp_type, input_values, input_ids, pid_values, pid_ids, comps, total_runtime, used_runtime):
    if not comp_type:
        return comps, used_runtime
    
    # Helper function to auto-fill duration if 0 or None
    def auto_fill_duration(duration, total_runtime, used_runtime):
        if duration == 0 or duration is None:
            remaining = total_runtime - used_runtime
            return max(0, remaining)  # Ensure non-negative
        return duration
    
    if comp_type == "pid":
        # Get shared PID parameters from dynamic inputs
        vals = {i["id"]: v for v, i in zip(input_values, input_ids)}
        
        # Check if required shared fields are filled
        if vals.get("duration") is None or vals.get("setpoint") is None:
            return comps, used_runtime
        
        # Organize PID values by controller
        controller_data = {}
        if pid_values and pid_ids:
            for val, input_id in zip(pid_values, pid_ids):
                if isinstance(input_id, dict):
                    controller_idx = input_id.get("controller")
                    field = input_id.get("field")
                    if controller_idx not in controller_data:
                        controller_data[controller_idx] = {}
                    controller_data[controller_idx][field] = val
        
        # Collect valid controllers (those with all required fields filled)
        valid_controllers = {}
        for controller_idx, data in controller_data.items():
            controller_name = data.get("controller")
            if (controller_name and controller_name.strip() and
                data.get("min_allowed") is not None and 
                data.get("max_allowed") is not None):
                valid_controllers[controller_name.strip()] = {
                    "min_allowed": data["min_allowed"],
                    "max_allowed": data["max_allowed"]
                }
        
        if not valid_controllers:
            return comps, used_runtime
        
        # Auto-fill duration if 0
        duration = auto_fill_duration(vals["duration"], total_runtime, used_runtime)
        
        # Create new PID component with shared setpoint and individual controller structure
        new_comp = {
            "id": str(uuid.uuid4()), 
            "type": "pid",
            "controllers": valid_controllers,
            "setpoint": vals["setpoint"],
            "duration": duration
        }
        new_used_runtime = used_runtime + duration
        return comps + [new_comp], new_used_runtime
    
    else:
        # Handle non-PID components
        vals = {i["id"]: v for v, i in zip(input_values, input_ids)}
        if "duration" not in vals or vals["duration"] is None:
            return comps, used_runtime
        
        # Auto-fill duration if 0
        duration = auto_fill_duration(vals["duration"], total_runtime, used_runtime)
        
        new_comp = {"id": str(uuid.uuid4()), "type": comp_type, "duration": duration}
        if comp_type == "constant" and vals.get("setpoint") is not None:
            new_comp["setpoint"] = vals["setpoint"]
        elif comp_type == "ramp" and None not in (vals.get("start_temp"), vals.get("end_temp")):
            new_comp.update(start_temp=vals["start_temp"], end_temp=vals["end_temp"])
        elif comp_type == "pwm" and None not in (vals.get("high_temp"), vals.get("low_temp"), vals.get("pulse_percent")):
            new_comp.update(high_temp=vals["high_temp"], low_temp=vals["low_temp"], pulse_percent=vals["pulse_percent"])
        else:
            return comps, used_runtime
        
        new_used_runtime = used_runtime + duration
        return comps + [new_comp], new_used_runtime

@app.callback(
    Output("selected-component", "data"),
    Input({"type": "component-select", "index": ALL}, "value"),
    prevent_initial_call=True
)
def update_selected(selected_values):
    for vals in selected_values:
        if vals:
            return vals[0]
    return None

@app.callback(
    Output("component-list", "children"),
    [Input("components-store", "data"),
     State("selected-component", "data")]
)
def render_list(comps, selected_id):
    if not comps:
        return [html.P("No components added yet", style={"textAlign": "center", "color": "#666"})]
    print(f"Rendering list with {len(comps)} components")  # Debug
    existing_ids = {c["id"] for c in comps}
    blocks = []
    for i, comp in enumerate(comps):
        if comp["type"] == "constant":
            txt, icon = f"{comp['setpoint']} for {comp['duration']} hrs", "🟦"
        elif comp["type"] == "ramp":
            txt, icon = f"{comp['start_temp']} → {comp['end_temp']} over {comp['duration']} hrs", "📈"
        elif comp["type"] == "pwm":
            txt, icon = f"{comp['low_temp']}-{comp['high_temp']}, {comp['pulse_percent']}% for {comp['duration']} hrs", "⚡"
        else:  # pid
            controllers = comp.get('controllers', {})
            controller_count = len(controllers)
            controller_names = list(controllers.keys())
            setpoint = comp.get('setpoint', 'N/A')
            if controller_count == 1:
                controller_name = controller_names[0]
                controller_config = controllers[controller_name]
                txt = f"PID {setpoint} ({controller_config['min_allowed']}-{controller_config['max_allowed']}) by {controller_name} for {comp['duration']} hrs"
            else:
                txt = f"PID {setpoint} with {controller_count} controllers: {', '.join(controller_names)} for {comp['duration']} hrs"
            icon = "🎛️"
        blocks.append(html.Div([
            html.Div([dcc.Checklist(
                id={"type": "component-select", "index": i},
                options=[{"label": "", "value": comp["id"]}],
                value=[comp["id"]] if selected_id in existing_ids and comp["id"] == selected_id else []
            )], **{"data-no-drag": "true"}, style={"marginRight": "10px"}),
            html.Span(icon, style={"fontSize": "20px", "marginRight": "10px"}),
            html.Span(f"{i+1}. {txt}")
        ], className="component-block", style={
            "padding": "12px", "margin": "5px 0", "backgroundColor": "#f8f9fa",
            "border": "1px solid #dee2e6", "borderRadius": "5px", "display": "flex", "alignItems": "center"
        }))
    return blocks

@app.callback(
    Output("components-store", "data", allow_duplicate=True),
    [Input("move-up-btn", "n_clicks"),
     Input("move-down-btn", "n_clicks"),
     Input("remove-btn", "n_clicks")],
    [State("selected-component", "data"),
     State("components-store", "data")],
    prevent_initial_call=True
)
def move_buttons(_, __, ___, selected_id, comps):
    if not comps or not selected_id:
        return comps
    idx = next((i for i, c in enumerate(comps) if c["id"] == selected_id), None)
    if idx is None:
        return comps
    if ctx.triggered_id == "move-up-btn":
        return move_item(comps, idx, idx - 1)
    elif ctx.triggered_id == "move-down-btn":
        return move_item(comps, idx, idx + 1)
    elif ctx.triggered_id == "remove-btn":
        new_list = comps.copy()
        new_list.pop(idx)
        return new_list
    return comps

# Clientside callback to capture drag data
app.clientside_callback(
    """
    function(n_clicks) {
        if (window.pendingDragData) {
            const data = window.pendingDragData;
            window.pendingDragData = null;
            console.log('Clientside callback triggered with:', data);
            return data;
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output("drag-data", "data"),
    Input("drag-trigger-btn", "n_clicks"),
    prevent_initial_call=True
)

@app.callback(
    Output("components-store", "data", allow_duplicate=True),
    Input("drag-data", "data"),
    State("components-store", "data"),
    prevent_initial_call=True
)
def handle_drag_reorder(drag_data, comps):
    if not comps or not drag_data:
        return comps
    
    from_idx = drag_data.get("fromIndex")
    to_idx = drag_data.get("toIndex")
    
    if from_idx is not None and to_idx is not None and from_idx != to_idx:
        print(f"Server callback: moving item from {from_idx} to {to_idx}")  # Debug
        reordered_comps = move_item(comps, from_idx, to_idx)
        print(f"Successfully reordered, new length: {len(reordered_comps)}")  # Debug
        return reordered_comps
    
    return comps

@app.callback(
    Output("temp-graph", "figure"),
    [Input("components-store", "data"),
     Input("process-type", "value"),
     Input("x-axis-toggle", "value")],
    State("total-runtime", "data")
)
def update_graph(comps, process_type, x_axis_toggle, total_runtime):
    fig = go.Figure()
    
    # Get units based on process type
    if process_type == "Temperature":
        unit, value_label = "°C", "Temperature"
    elif process_type == "Agitation":
        unit, value_label = "RPM", "Agitation Rate"
    elif process_type == "pH":
        unit, value_label = "", "pH"
    elif process_type == "Acid":
        unit, value_label = "mL/h", "Acid Flow Rate"
    elif process_type == "Base":
        unit, value_label = "mL/h", "Base Flow Rate"
    elif process_type == "Media A":
        unit, value_label = "mL/h", "Media A Flow Rate"
    else:
        unit, value_label = "units", "Value"
    
    if not comps:
        if "fixed" in x_axis_toggle and total_runtime > 0:
            fig.update_layout(
                title=f"{value_label} Profile", 
                xaxis_title="Time (hours)", 
                yaxis_title=f"{value_label} ({unit})",
                height=1000,
                xaxis=dict(range=[0, total_runtime])
            )
        else:
            fig.update_layout(title=f"{value_label} Profile", xaxis_title="Time (hours)", yaxis_title=f"{value_label} ({unit})", height=1000)
        return fig
    t_points, y_points = [], []
    current_time = 0
    for comp in comps:
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
            continue
        elif comp["type"] == "pid":
            # Create PID control loop visualization for multiple controllers
            controllers = comp.get("controllers", {})
            setpoint = comp.get("setpoint")
            duration = comp["duration"]
            
            if controllers and setpoint is not None:
                # Calculate the full y-range of the graph data to determine consistent PID sizing
                if t_points and y_points:
                    # Use existing data to determine graph range
                    data_min = min(y_points)
                    data_max = max(y_points)
                    graph_range = data_max - data_min
                    if graph_range == 0:
                        graph_range = max(100, abs(setpoint) * 0.4)  # Fallback for flat lines
                else:
                    # First component, estimate reasonable range
                    graph_range = max(100, abs(setpoint) * 0.4)
                
                # PID box always takes up 1/5 of the graph's y-range for consistent appearance
                pid_height = graph_range / 5
                
                # Draw the control box boundaries (centered in duration and around setpoint)
                box_left = current_time + duration * 0.3
                box_right = current_time + duration * 0.7
                box_bottom = setpoint - pid_height / 2
                box_top = setpoint + pid_height / 2
                
                # Add main box outline
                fig.add_shape(
                    type="rect",
                    x0=box_left, x1=box_right,
                    y0=box_bottom, y1=box_top,
                    line=dict(color="blue", width=2),
                    fillcolor="lightblue",
                    opacity=0.3
                )
                
                # Add setpoint line split around the PID box (not going through it)
                # Left part: from start to left edge of box
                t_points += [current_time, box_left]
                y_points += [setpoint, setpoint]
                # Right part: from right edge of box to end
                t_points += [box_right, current_time + duration]
                y_points += [setpoint, setpoint]
                
                # Add individual controller ranges positioned from center outward
                colors = ["blue", "green", "orange", "purple", "brown"]
                controller_count = len(controllers)
                
                for idx, (controller_name, controller_config) in enumerate(controllers.items()):
                    color = colors[idx % len(colors)]
                    
                    # Controller height based on percentage of PID box: 10% for 1st, 20% for 2nd, etc.
                    height_percentage = (idx + 1) * 0.1  # 10%, 20%, 30%, etc.
                    controller_height = pid_height * height_percentage
                    
                    # Position controllers from center outward
                    if idx == 0:
                        # First controller in center
                        ctrl_bottom = setpoint - controller_height / 2
                        ctrl_top = setpoint + controller_height / 2
                    else:
                        # Subsequent controllers move outward alternating up/down
                        spacing = pid_height * 0.05  # 5% of PID height spacing between controllers
                        if idx % 2 == 1:  # Odd indices go up
                            offset = ((idx + 1) // 2) * spacing
                            ctrl_bottom = setpoint + offset
                            ctrl_top = ctrl_bottom + controller_height
                        else:  # Even indices go down
                            offset = (idx // 2) * spacing
                            ctrl_top = setpoint - offset
                            ctrl_bottom = ctrl_top - controller_height
                    
                    # Add individual controller range box
                    fig.add_shape(
                        type="rect",
                        x0=box_left, x1=box_right,
                        y0=ctrl_bottom, y1=ctrl_top,
                        line=dict(color=color, width=1, dash="dot"),
                        fillcolor=color,
                        opacity=0.1
                    )
                    
                    # Add controller label at the top of each box
                    fig.add_annotation(
                        x=(box_left + box_right) / 2,
                        y=ctrl_top + pid_height * 0.05,  # Slightly above the controller box
                        text=controller_name,
                        showarrow=False,
                        font=dict(size=8, color=color)
                    )
                
                # Add feedback loop path - proper control loop shape (dotted line)
                # Calculate key heights relative to the PID box
                feedback_exit_y = setpoint + pid_height * 0.05     # Exit slightly above setpoint
                feedback_high_y = box_top + pid_height * 0.2       # Peak above PID box
                
                # Feedback path: out from box → up → across → down → back into box
                feedback_line_x = [
                    box_right,              # Exit right side of PID box
                    current_time + duration, # Go out to end of component period
                    current_time + duration, # Up at end of period
                    current_time,           # Across to start of period
                    current_time,           # Down at start of period
                    box_left                # Back into left side of PID box
                ]
                feedback_line_y = [
                    feedback_exit_y,        # Exit at 55% height
                    feedback_exit_y,        # Stay at exit level going out
                    feedback_high_y,        # Up to 110% height
                    feedback_high_y,        # Across at high level
                    feedback_exit_y,        # Down to 55% height
                    feedback_exit_y         # Back into box at 55% height
                ]
                
                fig.add_trace(go.Scatter(
                    x=feedback_line_x, 
                    y=feedback_line_y, 
                    mode="lines",
                    line=dict(color="red", width=1, dash="dash"),
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                # Add controller label
                fig.add_annotation(
                    x=(box_left + box_right) / 2,
                    y=(box_bottom + box_top) / 2,
                    text="PID",
                    showarrow=False,
                    font=dict(size=10, color="blue")
                )
        current_time += dur
    fig.add_trace(go.Scatter(x=t_points, y=y_points, mode="lines"))
    
    # Set x-axis range based on toggle
    if "fixed" in x_axis_toggle and total_runtime > 0:
        # Fixed to organism runtime
        fig.update_layout(
            title=f"{value_label} Profile", 
            xaxis_title="Time (hours)", 
            yaxis_title=f"{value_label} ({unit})", 
            height=1000,
            xaxis=dict(range=[0, total_runtime])
        )
    else:
        # Auto-scale to data
        fig.update_layout(
            title=f"{value_label} Profile", 
            xaxis_title="Time (hours)", 
            yaxis_title=f"{value_label} ({unit})", 
            height=1000
        )
    
    return fig

@app.callback(
    Output("json-output", "children"),
    Input("export-btn", "n_clicks"),
    [State("components-store", "data"),
     State("process-type", "value")],
    prevent_initial_call=True
)
def export_json(_, comps, process_type):
    if not comps:
        return html.P("No components to export", style={"color": "red"})
    
    # Create dynamic key based on process type
    if process_type:
        key = f"{process_type.lower()}_profile"
    else:
        key = "profile"
    
    clean_comps = [{k: v for k, v in comp.items() if k != "id"} for comp in comps]
    return html.Pre(json.dumps({key: clean_comps}, indent=2), style={
        "backgroundColor": "#f8f9fa", "padding": "10px", "border": "1px solid #dee2e6",
        "borderRadius": "5px", "fontSize": "12px", "overflow": "auto", "maxHeight": "300px"
    })

if __name__ == "__main__":
    app.run_server(debug=True)
