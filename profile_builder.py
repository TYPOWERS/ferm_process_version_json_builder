#!/usr/bin/env python3
"""
Profile Builder Module
Extracted from original app.py - handles fermentation profile component building
"""

import dash
from dash import dcc, html, Input, Output, State, ALL, ctx
import plotly.graph_objects as go
import json
import uuid
import dash_bootstrap_components as dbc
import tempfile
import os
import matplotlib.pyplot as plt
import numpy as np

# Process units mapping
PROCESS_UNITS = {
    "Temperature": "C",
    "Agitation": "rpm",
    "pH Lower": "",
    "pH Upper": "",
    "Acid": "mL/hr",
    "Base": "mL/hr",
    "Feed 1": "mL/hr",
    "Feed 2": "mL/hr",
    "Feed 3": "mL/hr",
    "DO": "%",
}


class ProfileBuilder:
    def __init__(self, app):
        self.app = app
        self.setup_callbacks()

    def get_process_unit(self, process_type):
        """Get unit for a given process type"""
        return PROCESS_UNITS.get(process_type, "")

    def calculate_component_timing(self, components):
        """Calculate start_time and end_time for each component"""
        current_time = 0
        updated_components = []

        for i, comp in enumerate(components):
            updated_comp = comp.copy()
            updated_comp['index'] = i
            updated_comp['start_time'] = round(current_time, 2)
            current_time += comp.get('duration', 0)
            updated_comp['end_time'] = round(current_time, 2)
            updated_components.append(updated_comp)

        return updated_components

    def generate_clean_profile_json(self, components):
        """Generate clean profile JSON for storage (components only, no metadata)"""
        if not components:
            return {"profile": []}

        # Remove internal 'id' field from components, keep original structure
        clean_components = []
        for comp in components:
            clean_comp = {k: v for k, v in comp.items() if k not in ["id", "index", "start_time", "end_time"]}
            clean_components.append(clean_comp)

        return {"profile": clean_components}

    def generate_profile_metadata(self, components, process_type):
        """Generate metadata for the profile"""
        if not components:
            return {}

        # Calculate totals
        total_components = len(components)
        total_duration = sum(comp.get('duration', 0) for comp in components)

        # Get component types
        component_types = list(set(comp['type'] for comp in components))

        # Calculate value ranges - ignore 0 from first component
        value_range = {"min": None, "max": None}

        for comp_index, comp in enumerate(components):
            values = []
            comp_type = comp['type']

            if comp_type == 'constant':
                setpoint = comp.get('setpoint')
                if setpoint is not None:
                    # Skip 0 values from first component for min calculation
                    if comp_index == 0 and setpoint == 0:
                        # Only add to max, not min
                        if value_range["max"] is None or setpoint > value_range["max"]:
                            value_range["max"] = setpoint
                    else:
                        values.append(setpoint)
            elif comp_type == 'ramp':
                start_setpoint = comp.get('start_setpoint')
                end_setpoint = comp.get('end_setpoint')
                if start_setpoint is not None:
                    # Skip 0 values from first component for min calculation
                    if comp_index == 0 and start_setpoint == 0:
                        if value_range["max"] is None or start_setpoint > value_range["max"]:
                            value_range["max"] = start_setpoint
                    else:
                        values.append(start_setpoint)
                if end_setpoint is not None:
                    values.append(end_setpoint)
            elif comp_type == 'pwm':
                high_temp = comp.get('high_temp')
                low_temp = comp.get('low_temp')
                if high_temp is not None:
                    values.append(high_temp)
                if low_temp is not None:
                    # Skip 0 values from first component for min calculation
                    if comp_index == 0 and low_temp == 0:
                        if value_range["max"] is None or low_temp > value_range["max"]:
                            value_range["max"] = low_temp
                    else:
                        values.append(low_temp)
            elif comp_type == 'pid':
                setpoint = comp.get('setpoint')
                min_allowed = comp.get('min_allowed')
                max_allowed = comp.get('max_allowed')
                if setpoint is not None:
                    # Skip 0 values from first component for min calculation
                    if comp_index == 0 and setpoint == 0:
                        if value_range["max"] is None or setpoint > value_range["max"]:
                            value_range["max"] = setpoint
                    else:
                        values.append(setpoint)
                if min_allowed is not None:
                    values.append(min_allowed)
                if max_allowed is not None:
                    values.append(max_allowed)

            # Update value range
            for value in values:
                if value is not None:
                    if value_range["min"] is None or value < value_range["min"]:
                        value_range["min"] = value
                    if value_range["max"] is None or value > value_range["max"]:
                        value_range["max"] = value

        return {
            "parameter": process_type,
            "unit": self.get_process_unit(process_type),
            "total_components": total_components,
            "total_duration": total_duration,
            "component_types": component_types,
            "value_range": value_range
        }
    
    def get_layout(self):
        """Return the profile builder layout"""
        return html.Div([
            # Process Configuration
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("🧬 Process Configuration", className="card-title"),
                            dbc.Row([
                                dbc.Col([
                                    html.Label("Process Type:"),
                                    dcc.Dropdown(
                                        id="process-type",
                                        options=[
                                            {"label": f"{process_type} ({unit})" if unit else process_type, "value": process_type}
                                            for process_type, unit in PROCESS_UNITS.items()
                                        ],
                                        placeholder="Select process type"
                                    )
                                ], width=6),
                                dbc.Col([
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
                                ], width=6)
                            ])
                        ])
                    ])
                ], width=12)
            ], className="mb-4"),
            
            # Component Builder Section
            dbc.Row([
                # Component Builder
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H5("🔧 Component Builder", className="card-title"),
                            
                            html.Label("Component Type:"),
                            dcc.Dropdown(
                                id="component-type",
                                options=[
                                    {"label": "Constant", "value": "constant"},
                                    {"label": "Ramp", "value": "ramp"},
                                    {"label": "PWM", "value": "pwm"},
                                    {"label": "PID", "value": "pid"}
                                ],
                                placeholder="Select component type",
                                className="mb-3"
                            ),
                            
                            # Dynamic fields based on component type
                            html.Div(id="dynamic-fields", className="mb-3"),
                            
                            # Component action buttons
                            dbc.Row([
                                dbc.Col([
                                    dbc.Button("Add Component", id="add-btn", color="primary", disabled=True, size="sm", className="w-100")
                                ], width=6),
                                dbc.Col([
                                    dbc.Button("Update Component", id="update-btn", color="success", size="sm", className="w-100", style={"display": "none"})
                                ], width=6)
                            ])
                        ])
                    ])
                ], width=6),
                
                # Component List
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.H5("📋 Profile Components", className="card-title d-inline"),
                                dbc.Badge("0 components", id="component-count-badge", color="secondary", className="ms-2")
                            ]),
                            
                            
                            # Main component list with drag & drop
                            html.Div(id="component-list", style={
                                "minHeight": "200px",
                                "border": "2px dashed #ccc",
                                "borderRadius": "5px",
                                "padding": "10px"
                            }, children=[
                                html.P("Add components to build your profile", className="text-muted text-center")
                            ]),
                            
                            # Drag trigger (hidden)
                            html.Button(id="drag-trigger-btn", style={"display": "none"}),
                            dcc.Store(id="drag-data", data={}),
                            
                            # Action buttons
                            html.Hr(),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Button("Clear All", id="clear-btn", color="danger", outline=True)
                                ], width=4),
                                dbc.Col([
                                    dbc.Button("Export JSON", id="export-btn", color="success", disabled=True)
                                ], width=4),
                                dbc.Col([
                                    dbc.Button("Upload to Benchling", id="upload-benchling-btn", color="primary", disabled=True)
                                ], width=4)
                            ]),

                            # JSON output display
                            html.Hr(),
                            html.Div(id="json-output", className="mt-3")
                        ])
                    ])
                ], width=6)
            ])
        ])
    
    def get_drag_and_drop_js(self):
        """Return the JavaScript for drag and drop functionality"""
        return """
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
        """
    
    def setup_callbacks(self):
        """Setup all callbacks for the profile builder"""
        
        # Dynamic fields callback
        @self.app.callback(
            [Output("dynamic-fields", "children"),
             Output("add-btn", "disabled")],
            [Input("component-type", "value")],
            [State("process-type", "value")]
        )
        def update_dynamic_fields(component_type, process_type):
            if not component_type:
                return [], True

            # Get unit for current process type
            unit = self.get_process_unit(process_type) if process_type else ""
            unit_suffix = f" ({unit})" if unit else ""

            fields = []

            if component_type == "constant":
                fields = [
                    html.Label(f"Setpoint{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "setpoint"}, type="number", placeholder=f"Enter setpoint value{unit_suffix}", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]
            elif component_type == "ramp":
                fields = [
                    html.Label(f"Start Value{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "start-value"}, type="number", placeholder=f"Enter start value{unit_suffix}", className="mb-2"),
                    html.Label(f"End Value{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "end-value"}, type="number", placeholder=f"Enter end value{unit_suffix}", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]
            elif component_type == "pwm":
                fields = [
                    html.Label(f"High Value{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "high-value"}, type="number", placeholder=f"Enter high value{unit_suffix}", className="mb-2"),
                    html.Label(f"Low Value{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "low-value"}, type="number", placeholder=f"Enter low value{unit_suffix}", className="mb-2"),
                    html.Label("Pulse Percentage:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "pulse-percent"}, type="number", placeholder="Enter pulse percentage", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]
            elif component_type == "pid":
                fields = [
                    html.Label("Controller Name:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "controller-name"}, type="text", placeholder="Enter controller name", className="mb-2"),
                    html.Label(f"Setpoint{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "setpoint"}, type="number", placeholder=f"Enter setpoint value{unit_suffix}", className="mb-2"),
                    html.Label(f"Min Allowed{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "min-allowed"}, type="number", placeholder=f"Enter minimum allowed value{unit_suffix}", className="mb-2"),
                    html.Label(f"Max Allowed{unit_suffix}:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "max-allowed"}, type="number", placeholder=f"Enter maximum allowed value{unit_suffix}", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]

            return fields, False
        
        # Create new component callback
        @self.app.callback(
            [Output("profile-components", "data"),
             Output("component-list", "children"),
             Output("component-count-badge", "children")],
            [Input("add-btn", "n_clicks")],
            [State("component-type", "value"),
             State("profile-components", "data"),
             State("process-type", "value"),
             State({"type": "dynamic-input", "id": ALL}, "value"),
             State({"type": "dynamic-input", "id": ALL}, "id")],
            prevent_initial_call=True
        )
        def create_new_component(add_clicks, component_type, components, process_type, input_values, input_ids):
            if not add_clicks or not component_type:
                return dash.no_update, dash.no_update, dash.no_update

            components = components or []
            
            # Create a dictionary of field values from the ALL pattern inputs
            field_values = {}
            if input_values and input_ids:
                for value, id_dict in zip(input_values, input_ids):
                    if isinstance(id_dict, dict) and "id" in id_dict:
                        field_values[id_dict["id"]] = value
            
            # Create component based on type
            component = {"type": component_type, "id": str(uuid.uuid4())}
            
            # Map input values based on component type
            if component_type == "constant":
                component.update({
                    "setpoint": field_values.get("setpoint"),
                    "duration": field_values.get("duration")
                })
            elif component_type == "ramp":
                component.update({
                    "start_setpoint": field_values.get("start-value"),
                    "end_setpoint": field_values.get("end-value"),
                    "duration": field_values.get("duration")
                })
            elif component_type == "pwm":
                component.update({
                    "high_temp": field_values.get("high-value"),
                    "low_temp": field_values.get("low-value"),
                    "pulse_percent": field_values.get("pulse-percent"),
                    "duration": field_values.get("duration")
                })
            elif component_type == "pid":
                component.update({
                    "controller": field_values.get("controller-name"),
                    "setpoint": field_values.get("setpoint"),
                    "min_allowed": field_values.get("min-allowed"),
                    "max_allowed": field_values.get("max-allowed"),
                    "duration": field_values.get("duration")
                })
            
            print(f"📝 Created new component: {component}")
            components.append(component)

            # Create visual component list
            component_elements = self._create_component_elements(components, process_type)
            count_text = f"{len(components)} components"

            return components, component_elements, count_text

        # Update existing component callback
        @self.app.callback(
            [Output("profile-components", "data", allow_duplicate=True),
             Output("component-list", "children", allow_duplicate=True),
             Output("component-count-badge", "children", allow_duplicate=True),
             Output("add-btn", "style", allow_duplicate=True),
             Output("update-btn", "style", allow_duplicate=True),
             Output("component-type", "value", allow_duplicate=True)],
            [Input("update-btn", "n_clicks")],
            [State("component-type", "value"),
             State("profile-components", "data"),
             State("process-type", "value"),
             State("selected-component", "data"),
             State({"type": "dynamic-input", "id": ALL}, "value"),
             State({"type": "dynamic-input", "id": ALL}, "id")],
            prevent_initial_call=True
        )
        def update_existing_component(update_clicks, component_type, components, process_type, selected_component_id, input_values, input_ids):
            if not update_clicks or not component_type or not selected_component_id:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

            components = components or []
            
            # Create a dictionary of field values from the ALL pattern inputs
            field_values = {}
            if input_values and input_ids:
                for value, id_dict in zip(input_values, input_ids):
                    if isinstance(id_dict, dict) and "id" in id_dict:
                        field_values[id_dict["id"]] = value
            
            print(f"📝 Field values received: {field_values}")
            print(f"📝 Component type: {component_type}")
            print(f"📝 Selected component ID: {selected_component_id}")

            # Find and update the component
            updated_components = []
            for comp in components:
                if comp.get('id') == selected_component_id:
                    # Update this component
                    updated_component = comp.copy()
                    updated_component['type'] = component_type
                    
                    # Map input values based on component type
                    if component_type == "constant":
                        setpoint = field_values.get("setpoint")
                        duration = field_values.get("duration")
                        updated_component.update({
                            "setpoint": float(setpoint) if setpoint is not None and setpoint != "" else None,
                            "duration": float(duration) if duration is not None and duration != "" else None
                        })
                    elif component_type == "ramp":
                        start_setpoint = field_values.get("start-value")
                        end_setpoint = field_values.get("end-value")
                        duration = field_values.get("duration")

                        print(f"📝 Ramp field values: start_setpoint={start_setpoint}, end_setpoint={end_setpoint}, duration={duration}")

                        try:
                            start_val = float(start_setpoint) if start_setpoint is not None and start_setpoint != "" else None
                            end_val = float(end_setpoint) if end_setpoint is not None and end_setpoint != "" else None
                            duration_val = float(duration) if duration is not None and duration != "" else None

                            # Check if start and end setpoints are the same (within tolerance)
                            if start_val is not None and end_val is not None:
                                if abs(start_val - end_val) < 0.1:  # Same value (within 0.1 tolerance)
                                    print(f"📝 Converting ramp to constant: {start_val} == {end_val}")
                                    updated_component.update({
                                        "type": "constant",
                                        "setpoint": start_val,
                                        "duration": duration_val
                                    })
                                    # Remove ramp-specific fields
                                    updated_component.pop("start_setpoint", None)
                                    updated_component.pop("end_setpoint", None)
                                else:
                                    print(f"📝 Keeping as ramp: {start_val} → {end_val}")
                                    updated_component.update({
                                        "type": "ramp",
                                        "start_setpoint": start_val,
                                        "end_setpoint": end_val,
                                        "duration": duration_val
                                    })
                            else:
                                # Missing values, keep as entered
                                updated_component.update({
                                    "start_setpoint": start_val,
                                    "end_setpoint": end_val,
                                    "duration": duration_val
                                })
                        except (ValueError, TypeError) as e:
                            print(f"❌ Error converting ramp values: {e}")
                            # Keep original values if conversion fails
                            updated_component.update({
                                "start_setpoint": start_setpoint,
                                "end_setpoint": end_setpoint,
                                "duration": duration
                            })
                    elif component_type == "pwm":
                        updated_component.update({
                            "high_temp": field_values.get("high-value"),
                            "low_temp": field_values.get("low-value"),
                            "pulse_percent": field_values.get("pulse-percent"),
                            "duration": field_values.get("duration")
                        })
                    elif component_type == "pid":
                        updated_component.update({
                            "controller": field_values.get("controller-name"),
                            "setpoint": field_values.get("setpoint"),
                            "min_allowed": field_values.get("min-allowed"),
                            "max_allowed": field_values.get("max-allowed"),
                            "duration": field_values.get("duration")
                        })
                    
                    print(f"📝 Updated component: {updated_component}")
                    updated_components.append(updated_component)
                else:
                    updated_components.append(comp)
            
            # Update display
            component_elements = self._create_component_elements(updated_components, process_type)
            count_text = f"{len(updated_components)} components"

            # Reset to create mode
            add_style = {"display": "block"}
            update_style = {"display": "none"}

            return updated_components, component_elements, count_text, add_style, update_style, ""
        
        # Clear all callback
        @self.app.callback(
            [Output("profile-components", "data", allow_duplicate=True),
             Output("component-list", "children", allow_duplicate=True),
             Output("component-count-badge", "children", allow_duplicate=True)],
            [Input("clear-btn", "n_clicks")],
            prevent_initial_call=True
        )
        def clear_components(n_clicks):
            if n_clicks:
                return [], [html.P("Add components to build your profile", className="text-muted text-center")], "0 components"
            return dash.no_update, dash.no_update, dash.no_update
        
        # Export JSON and Upload buttons callback
        @self.app.callback(
            [Output("export-btn", "disabled"),
             Output("upload-benchling-btn", "disabled")],
            [Input("profile-components", "data"),
             Input("process-type", "value")]
        )
        def update_action_buttons(components, process_type):
            has_components = len(components or []) > 0
            has_process_type = process_type is not None and process_type != ""

            export_disabled = not has_components
            upload_disabled = not (has_components and has_process_type)

            return export_disabled, upload_disabled

        # Export JSON data callback
        @self.app.callback(
            Output("json-output", "children"),
            [Input("export-btn", "n_clicks")],
            [State("profile-components", "data"),
             State("process-type", "value")],
            prevent_initial_call=True
        )
        def export_json(n_clicks, components, process_type):
            if not n_clicks or not components:
                return html.P("No components to export", style={"color": "red"})

            if not process_type:
                return html.P("Please select a process type before exporting", style={"color": "red"})

            # Calculate timing for components
            timed_components = self.calculate_component_timing(components)

            # Remove internal 'id' field from components
            clean_components = [{k: v for k, v in comp.items() if k != "id"} for comp in timed_components]

            # Generate metadata
            metadata = self.generate_profile_metadata(components, process_type)

            # Create enhanced JSON structure
            enhanced_json = {
                "profile": clean_components,
                "summary": metadata
            }

            return html.Pre(json.dumps(enhanced_json, indent=2), style={
                "backgroundColor": "#f8f9fa",
                "padding": "10px",
                "border": "1px solid #dee2e6",
                "borderRadius": "5px",
                "fontSize": "12px",
                "overflow": "auto",
                "maxHeight": "300px"
            })

        # Upload to Benchling callback
        @self.app.callback(
            Output("json-output", "children", allow_duplicate=True),
            [Input("upload-benchling-btn", "n_clicks")],
            [State("profile-components", "data"),
             State("process-type", "value")],
            prevent_initial_call=True
        )
        def upload_to_benchling(n_clicks, components, process_type):
            print(f"🔄 Upload callback triggered: n_clicks={n_clicks}, components={len(components or [])}, process_type={process_type}")

            if not n_clicks or not components or not process_type:
                print("❌ Upload conditions not met")
                return dash.no_update

            print("✅ Starting Benchling upload...")
            # Generate enhanced profile JSON (same as export format)
            # Calculate timing for components
            timed_components = self.calculate_component_timing(components)

            # Remove internal 'id' field from components
            clean_components = [{k: v for k, v in comp.items() if k != "id"} for comp in timed_components]

            # Generate metadata
            metadata = self.generate_profile_metadata(components, process_type)

            # Create enhanced JSON structure (same as export)
            enhanced_profile = {
                "profile": clean_components,
                "summary": metadata
            }

            # Create a simple visualization using matplotlib
            image_path = self._create_profile_image(components, process_type)

            # Initialize BenchlingAPI
            from BenchlingAPI import BenchlingAPI
            benchling_api = BenchlingAPI('Test', 'automation')

            # Upload to Benchling if it doesn't exist
            result, exists_flag = benchling_api.create_fermentation_process_profile_if_not_exists(
                profile_type=process_type,
                profile_json=enhanced_profile,
                image_path=image_path
            )
            try:

                # Clean up temporary image file
                if os.path.exists(image_path):
                    os.remove(image_path)

                if not exists_flag and result:
                    return html.Div([
                        dbc.Alert([
                            f"✅ Profile uploaded to Benchling successfully! Name and Barcode: {result.name} ",
                            html.A("View in Benchling", href=result.web_url, target="_blank")
                        ],
                            color="success",
                            dismissable=True
                        )
                    ])
                elif exists_flag and result:
                    return html.Div([
                        dbc.Alert([
                            "ℹ️ Profile already exists in Benchling. ",
                            html.A("View in Benchling", href=result.web_url, target="_blank")
                        ],
                            color="info",
                            dismissable=True
                        )
                    ])
                
                else:
                    return html.Div([
                        dbc.Alert(
                            "Something went wrong during upload, but no error was raised.",
                            color="info",
                            dismissable=True
                        )
                    ])

            except Exception as e:
                import traceback
                full_error = traceback.format_exc()
                print(f"❌ Full Benchling upload error:")
                print(full_error)
                print(f"❌ Error type: {type(e).__name__}")
                print(f"❌ Error message: {str(e)}")

                return html.Div([
                    dbc.Alert(
                        f"❌ Error uploading to Benchling: {str(e)}",
                        color="danger",
                        dismissable=True
                    )
                ])

        # Update component list when store changes
        @self.app.callback(
            [Output("component-list", "children", allow_duplicate=True),
             Output("component-count-badge", "children", allow_duplicate=True)],
            [Input("profile-components", "data")],
            [State("process-type", "value")],
            prevent_initial_call=True
        )
        def update_component_list_display(components, process_type):
            components = components or []  # Ensure components is never None

            if len(components) == 0:
                return [html.P("Add components to build your profile", className="text-muted text-center")], "0 components"

            component_elements = self._create_component_elements(components, process_type)
            count_text = f"{len(components)} components"
            return component_elements, count_text

        # Delete component callback
        @self.app.callback(
            Output("profile-components", "data", allow_duplicate=True),
            [Input({"type": "delete-component-btn", "index": ALL}, "n_clicks")],
            [State("profile-components", "data"),
             State({"type": "delete-component-btn", "index": ALL}, "id")],
            prevent_initial_call=True
        )
        def delete_component(n_clicks_list, components, button_ids):
            if not any(n_clicks_list) or not components:
                return dash.no_update
            
            ctx = dash.callback_context
            if not ctx.triggered:
                return dash.no_update
            
            # Find which button was clicked
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            button_dict = eval(button_id)  # Convert string to dict
            component_id_to_delete = button_dict['index']
            
            # Remove component with matching ID
            updated_components = [comp for comp in components if comp.get('id') != component_id_to_delete]
            print(f"🗑️ Deleted component with ID: {component_id_to_delete}")
            
            return updated_components
        
        # Edit component callback - simplified to just switch buttons and set type
        @self.app.callback(
            [Output("component-type", "value", allow_duplicate=True),
             Output("add-btn", "style", allow_duplicate=True),
             Output("update-btn", "style", allow_duplicate=True)],
            [Input({"type": "edit-component-btn", "index": ALL}, "n_clicks")],
            [State("profile-components", "data"),
             State({"type": "edit-component-btn", "index": ALL}, "id")],
            prevent_initial_call=True
        )
        def edit_component(n_clicks_list, components, button_ids):
            if not any(n_clicks_list) or not components:
                return dash.no_update, dash.no_update, dash.no_update
            
            ctx = dash.callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update, dash.no_update
            
            # Find which button was clicked
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            button_dict = eval(button_id)  # Convert string to dict
            component_id_to_edit = button_dict['index']
            
            # Find the component to edit
            component_to_edit = None
            for comp in components:
                if comp.get('id') == component_id_to_edit:
                    component_to_edit = comp
                    break
            
            if not component_to_edit:
                return dash.no_update, dash.no_update, dash.no_update
            
            print(f"✏️ Editing component: {component_to_edit['type']}")
            
            # Set component type to trigger field creation, then populate via separate callback
            comp_type = component_to_edit['type']
            
            # Show Update button, hide Add button
            add_style = {"display": "none"}
            update_style = {"display": "block"}
            
            return comp_type, add_style, update_style
        
        # Populate fields after component type is set for editing
        @self.app.callback(
            Output({"type": "dynamic-input", "id": ALL}, "value", allow_duplicate=True),
            [Input("dynamic-fields", "children"),
             Input("update-btn", "style")],
            [State("profile-components", "data"),
             State("selected-component", "data"),
             State({"type": "dynamic-input", "id": ALL}, "id")],
            prevent_initial_call=True
        )
        def populate_edit_fields(dynamic_fields_children, update_btn_style, components, selected_component, field_ids):
            # Only populate when update button is visible (edit mode)
            if not update_btn_style or update_btn_style.get("display") == "none":
                return dash.no_update
            
            if not selected_component or not components:
                return dash.no_update
            
            # Find the component being edited
            component_to_edit = None
            for comp in components:
                if comp.get('id') == selected_component:
                    component_to_edit = comp
                    break
            
            if not component_to_edit:
                return dash.no_update
            
            print(f"🔧 Populating fields for component: {component_to_edit}")
            print(f"🔧 Available field IDs: {[f['id'] for f in field_ids]}")
            
            # Map field IDs to values with better error handling
            field_values = []
            for field_id in field_ids:
                field_name = field_id['id']
                
                # Handle special field mappings
                if field_name == 'setpoint':
                    value = component_to_edit.get('setpoint', "")
                elif field_name == 'duration':
                    value = component_to_edit.get('duration', "")
                elif field_name == 'start-value':
                    value = component_to_edit.get('start_setpoint', "")
                elif field_name == 'end-value':
                    value = component_to_edit.get('end_setpoint', "")
                elif field_name == 'high-value':
                    value = component_to_edit.get('high_temp', "")
                elif field_name == 'low-value':
                    value = component_to_edit.get('low_temp', "")
                elif field_name == 'pulse-percent':
                    value = component_to_edit.get('pulse_percent', "")
                elif field_name == 'controller-name':
                    value = component_to_edit.get('controller', "")
                elif field_name == 'min-allowed':
                    value = component_to_edit.get('min_allowed', "")
                elif field_name == 'max-allowed':
                    value = component_to_edit.get('max_allowed', "")
                else:
                    value = component_to_edit.get(field_name, "")
                
                # Ensure value is a string for input fields
                if value is None:
                    value = ""
                else:
                    value = str(value)
                
                field_values.append(value)
                print(f"🔧 Field '{field_name}' = '{value}'")
            
            return field_values
        
        # Store selected component ID when edit button is clicked
        @self.app.callback(
            Output("selected-component", "data", allow_duplicate=True),
            [Input({"type": "edit-component-btn", "index": ALL}, "n_clicks")],
            [State({"type": "edit-component-btn", "index": ALL}, "id")],
            prevent_initial_call=True
        )
        def store_selected_component(n_clicks_list, button_ids):
            if not any(n_clicks_list):
                return dash.no_update
            
            ctx = dash.callback_context
            if not ctx.triggered:
                return dash.no_update
            
            # Find which button was clicked
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            button_dict = eval(button_id)  # Convert string to dict
            return button_dict['index']
        
        # Drag and drop clientside callback
        self.app.clientside_callback(
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
        
        # Drag reorder callback
        @self.app.callback(
            Output("profile-components", "data", allow_duplicate=True),
            [Input("drag-data", "data")],
            [State("profile-components", "data")],
            prevent_initial_call=True
        )
        def handle_drag_reorder(drag_data, components):
            if not components or not drag_data:
                return components
            
            from_idx = drag_data.get("fromIndex")
            to_idx = drag_data.get("toIndex")
            
            if from_idx is not None and to_idx is not None and from_idx != to_idx:
                print(f"🔄 Reordering: moving component from {from_idx} to {to_idx}")
                
                # Move component from from_idx to to_idx
                component_to_move = components.pop(from_idx)
                components.insert(to_idx, component_to_move)
                
                print(f"✅ Reordered successfully, new length: {len(components)}")
                return components
            
            return components
        
    
    def _create_component_elements(self, components, process_type=None):
        """Create visual elements for component list"""
        if not components:
            return [html.P("Add components to build your profile", className="text-muted text-center")]

        elements = []
        for i, component in enumerate(components):
            # Create component card
            card = dbc.Card([
                dbc.CardBody([
                    html.H6(f"{component['type'].title()} Component", className="card-title"),
                    html.P(self._format_component_details(component, process_type), className="card-text"),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button("Edit",
                                id={"type": "edit-component-btn", "index": component.get('id', i)},
                                color="warning", size="md", className="w-100")
                        ], width=6),
                        dbc.Col([
                            dbc.Button("Delete",
                                id={"type": "delete-component-btn", "index": component.get('id', i)},
                                color="danger", size="md", className="w-100")
                        ], width=6)
                    ], className="g-2")
                ])
            ], className="component-block mb-2", style={"cursor": "grab"})

            elements.append(card)

        return elements
    
    def _format_component_details(self, component, process_type=None):
        """Format component details for display with units"""
        comp_type = component['type']
        unit = self.get_process_unit(process_type) if process_type else ""

        # Format duration
        duration = component.get('duration', 0)
        duration_str = f"{duration/24:.1f}d" if duration >= 24 else f"{duration:.1f}h"

        if comp_type == "constant":
            setpoint = component.get('setpoint', 'N/A')
            setpoint_str = f"{setpoint} {unit}" if unit and setpoint != 'N/A' else str(setpoint)
            return f"Setpoint: {setpoint_str}, Duration: {duration_str}"
        elif comp_type == "ramp":
            start_setpoint = component.get('start_setpoint', 'N/A')
            end_setpoint = component.get('end_setpoint', 'N/A')
            start_str = f"{start_setpoint} {unit}" if unit and start_setpoint != 'N/A' else str(start_setpoint)
            end_str = f"{end_setpoint} {unit}" if unit and end_setpoint != 'N/A' else str(end_setpoint)
            return f"From {start_str} to {end_str}, Duration: {duration_str}"
        elif comp_type == "pwm":
            high_temp = component.get('high_temp', 'N/A')
            low_temp = component.get('low_temp', 'N/A')
            high_str = f"{high_temp} {unit}" if unit and high_temp != 'N/A' else str(high_temp)
            low_str = f"{low_temp} {unit}" if unit and low_temp != 'N/A' else str(low_temp)
            pulse_percent = component.get('pulse_percent', 'N/A')
            return f"High: {high_str}, Low: {low_str}, Pulse: {pulse_percent}%, Duration: {duration_str}"
        elif comp_type == "pid":
            controller = component.get('controller', 'N/A')
            setpoint = component.get('setpoint', 'N/A')
            setpoint_str = f"{setpoint} {unit}" if unit and setpoint != 'N/A' else str(setpoint)
            return f"Controller: {controller}, Setpoint: {setpoint_str}, Duration: {duration_str}"

        return "Component details"
    
    def _create_generated_component_card(self, component):
        """Create a card for a generated component that needs approval"""
        details = self._format_component_details(component)
        confidence = component.get('confidence', 'medium')
        source = component.get('source_file', 'Unknown')
        
        return dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6(f"🤖 {component['type'].title()}", className="mb-1"),
                        html.P(details, className="mb-1 small"),
                        html.P(f"Source: {source}", className="mb-0 text-muted small")
                    ], width=8),
                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button("✓", 
                                id={"type": "approve-btn", "index": component.get('id', 'unknown')}, 
                                color="success", size="sm", title="Approve"),
                            dbc.Button("✏️", 
                                id={"type": "edit-generated-btn", "index": component.get('id', 'unknown')}, 
                                color="warning", size="sm", title="Edit"),
                            dbc.Button("✗", 
                                id={"type": "reject-btn", "index": component.get('id', 'unknown')}, 
                                color="danger", size="sm", title="Reject")
                        ])
                    ], width=4, className="text-end")
                ])
            ])
        ], className="mb-2", color="light", outline=True)

    def _create_profile_image(self, components, process_type):
        """Create a simple profile visualization image for Benchling upload"""
        if not components:
            return None

        # Generate profile timeline
        t_points, y_points = [], []
        current_time = 0

        for comp in components:
            dur = comp["duration"]
            if comp["type"] == "constant":
                t_points += [current_time, current_time + dur]
                y_points += [comp["setpoint"], comp["setpoint"]]
            elif comp["type"] == "ramp":
                t_points += [current_time, current_time + dur]
                y_points += [comp["start_setpoint"], comp["end_setpoint"]]
            elif comp["type"] == "pwm":
                # Simplified PWM representation
                t_points += [current_time, current_time + dur]
                y_points += [comp["low_temp"], comp["high_temp"]]
            elif comp["type"] == "pid":
                t_points += [current_time, current_time + dur]
                y_points += [comp["setpoint"], comp["setpoint"]]

            current_time += dur

        # Create matplotlib plot
        plt.figure(figsize=(10, 6))
        plt.plot(t_points, y_points, 'b-', linewidth=2)
        plt.xlabel('Time (hours)')
        plt.ylabel(f'{process_type} ({self.get_process_unit(process_type)})')
        plt.title(f'{process_type} Profile')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(temp_file.name, dpi=150, bbox_inches='tight')
        plt.close()

        return temp_file.name


# Function to integrate with main app
def setup_profile_builder(app):
    """Setup profile builder functionality in the main app"""
    profile_builder = ProfileBuilder(app)
    return profile_builder