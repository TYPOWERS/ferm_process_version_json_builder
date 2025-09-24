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


class ProfileBuilder:
    def __init__(self, app):
        self.app = app
        self.setup_callbacks()
    
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
                                            {"label": "Agitation", "value": "Agitation"},
                                            {"label": "pH", "value": "pH"},
                                            {"label": "Acid", "value": "Acid"},
                                            {"label": "Base", "value": "Base"},
                                            {"label": "Media A", "value": "Media A"},
                                            {"label": "Temperature", "value": "Temperature"}
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
                                ], width=6),
                                dbc.Col([
                                    dbc.Button("Export JSON", id="export-btn", color="success", disabled=True)
                                ], width=6)
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
            [Input("component-type", "value")]
        )
        def update_dynamic_fields(component_type):
            if not component_type:
                return [], True

            fields = []
            
            if component_type == "constant":
                fields = [
                    html.Label("Setpoint:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "setpoint"}, type="number", placeholder="Enter setpoint value", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]
            elif component_type == "ramp":
                fields = [
                    html.Label("Start Value:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "start-value"}, type="number", placeholder="Enter start value", className="mb-2"),
                    html.Label("End Value:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "end-value"}, type="number", placeholder="Enter end value", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]
            elif component_type == "pwm":
                fields = [
                    html.Label("High Value:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "high-value"}, type="number", placeholder="Enter high value", className="mb-2"),
                    html.Label("Low Value:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "low-value"}, type="number", placeholder="Enter low value", className="mb-2"),
                    html.Label("Pulse Percentage:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "pulse-percent"}, type="number", placeholder="Enter pulse percentage", className="mb-2"),
                    html.Label("Duration (hours):"),
                    dbc.Input(id={"type": "dynamic-input", "id": "duration"}, type="number", placeholder="Enter duration in hours", className="mb-2")
                ]
            elif component_type == "pid":
                fields = [
                    html.Label("Controller Name:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "controller-name"}, type="text", placeholder="Enter controller name", className="mb-2"),
                    html.Label("Setpoint:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "setpoint"}, type="number", placeholder="Enter setpoint value", className="mb-2"),
                    html.Label("Min Allowed:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "min-allowed"}, type="number", placeholder="Enter minimum allowed value", className="mb-2"),
                    html.Label("Max Allowed:"),
                    dbc.Input(id={"type": "dynamic-input", "id": "max-allowed"}, type="number", placeholder="Enter maximum allowed value", className="mb-2"),
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
             State({"type": "dynamic-input", "id": ALL}, "value"),
             State({"type": "dynamic-input", "id": ALL}, "id")],
            prevent_initial_call=True
        )
        def create_new_component(add_clicks, component_type, components, input_values, input_ids):
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
                    "start_temp": field_values.get("start-value"),
                    "end_temp": field_values.get("end-value"),
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
            component_elements = self._create_component_elements(components)
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
             State("selected-component", "data"),
             State({"type": "dynamic-input", "id": ALL}, "value"),
             State({"type": "dynamic-input", "id": ALL}, "id")],
            prevent_initial_call=True
        )
        def update_existing_component(update_clicks, component_type, components, selected_component_id, input_values, input_ids):
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
                        start_temp = field_values.get("start-value")
                        end_temp = field_values.get("end-value") 
                        duration = field_values.get("duration")
                        
                        print(f"📝 Ramp field values: start_temp={start_temp}, end_temp={end_temp}, duration={duration}")
                        
                        try:
                            start_val = float(start_temp) if start_temp is not None and start_temp != "" else None
                            end_val = float(end_temp) if end_temp is not None and end_temp != "" else None
                            duration_val = float(duration) if duration is not None and duration != "" else None
                            
                            # Check if start and end temps are the same (within tolerance)
                            if start_val is not None and end_val is not None:
                                if abs(start_val - end_val) < 0.1:  # Same value (within 0.1 tolerance)
                                    print(f"📝 Converting ramp to constant: {start_val} == {end_val}")
                                    updated_component.update({
                                        "type": "constant",
                                        "setpoint": start_val,
                                        "duration": duration_val
                                    })
                                    # Remove ramp-specific fields
                                    updated_component.pop("start_temp", None)
                                    updated_component.pop("end_temp", None)
                                else:
                                    print(f"📝 Keeping as ramp: {start_val} → {end_val}")
                                    updated_component.update({
                                        "type": "ramp",
                                        "start_temp": start_val,
                                        "end_temp": end_val,
                                        "duration": duration_val
                                    })
                            else:
                                # Missing values, keep as entered
                                updated_component.update({
                                    "start_temp": start_val,
                                    "end_temp": end_val,
                                    "duration": duration_val
                                })
                        except (ValueError, TypeError) as e:
                            print(f"❌ Error converting ramp values: {e}")
                            # Keep original values if conversion fails
                            updated_component.update({
                                "start_temp": start_temp,
                                "end_temp": end_temp,
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
            component_elements = self._create_component_elements(updated_components)
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
        
        # Export JSON callback
        @self.app.callback(
            Output("export-btn", "disabled"),
            [Input("profile-components", "data")]
        )
        def update_export_button(components):
            return len(components or []) == 0

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

            # Create dynamic key based on process type
            if process_type:
                key = f"{process_type.lower()}_profile"
            else:
                key = "profile"

            # Remove internal 'id' field from components
            clean_components = [{k: v for k, v in comp.items() if k != "id"} for comp in components]

            return html.Pre(json.dumps({key: clean_components}, indent=2), style={
                "backgroundColor": "#f8f9fa",
                "padding": "10px",
                "border": "1px solid #dee2e6",
                "borderRadius": "5px",
                "fontSize": "12px",
                "overflow": "auto",
                "maxHeight": "300px"
            })
        
        # Update component list when store changes
        @self.app.callback(
            [Output("component-list", "children", allow_duplicate=True),
             Output("component-count-badge", "children", allow_duplicate=True)],
            [Input("profile-components", "data")],
            prevent_initial_call=True
        )
        def update_component_list_display(components):
            if not components:
                return [html.P("Add components to build your profile", className="text-muted text-center")], "0 components"
            
            component_elements = self._create_component_elements(components)
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
                    value = component_to_edit.get('start_temp', "")
                elif field_name == 'end-value':
                    value = component_to_edit.get('end_temp', "")
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
        
    
    def _create_component_elements(self, components):
        """Create visual elements for component list"""
        if not components:
            return [html.P("Add components to build your profile", className="text-muted text-center")]
        
        elements = []
        for i, component in enumerate(components):
            # Create component card
            card = dbc.Card([
                dbc.CardBody([
                    html.H6(f"{component['type'].title()} Component", className="card-title"),
                    html.P(self._format_component_details(component), className="card-text"),
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
    
    def _format_component_details(self, component):
        """Format component details for display"""
        comp_type = component['type']
        
        if comp_type == "constant":
            duration = component.get('duration', 0)
            duration_str = f"{duration/24:.1f}d" if duration >= 24 else f"{duration:.1f}h"
            return f"Setpoint: {component.get('setpoint', 'N/A')}, Duration: {duration_str}"
        elif comp_type == "ramp":
            duration = component.get('duration', 0) 
            duration_str = f"{duration/24:.1f}d" if duration >= 24 else f"{duration:.1f}h"
            return f"From {component.get('start_temp', 'N/A')} to {component.get('end_temp', 'N/A')}, Duration: {duration_str}"
        elif comp_type == "pwm":
            duration = component.get('duration', 0)
            duration_str = f"{duration/24:.1f}d" if duration >= 24 else f"{duration:.1f}h"
            return f"High: {component.get('high_temp', 'N/A')}, Low: {component.get('low_temp', 'N/A')}, Pulse: {component.get('pulse_percent', 'N/A')}%, Duration: {duration_str}"
        elif comp_type == "pid":
            duration = component.get('duration', 0)
            duration_str = f"{duration/24:.1f}d" if duration >= 24 else f"{duration:.1f}h"
            return f"Controller: {component.get('controller', 'N/A')}, Setpoint: {component.get('setpoint', 'N/A')}, Duration: {duration_str}"
        
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


# Function to integrate with main app
def setup_profile_builder(app):
    """Setup profile builder functionality in the main app"""
    profile_builder = ProfileBuilder(app)
    return profile_builder