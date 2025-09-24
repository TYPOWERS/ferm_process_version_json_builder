#!/usr/bin/env python3
"""
File Selector Sidebar Module
Handles setpoint file selection, grouping, and processing for the integrated app
"""

import os
import glob
import pandas as pd
from dash import dcc, html, Input, Output, State, callback, MATCH, ALL
import dash_bootstrap_components as dbc
import dash
from datetime import datetime
import re

from process_setpoint_files import SetpointProcessor


class FileSelector:
    def __init__(self, app):
        self.app = app
        self.processor = SetpointProcessor()
        self.setup_callbacks()
    
    def get_layout(self):
        """Return the file selector sidebar layout"""
        return html.Div([
            # Folder selection section
            dbc.Card([
                dbc.CardBody([
                    html.H5("📁 Select Data Folder", className="card-title"),
                    dbc.InputGroup([
                        dbc.Input(
                            id="folder-path-input",
                            placeholder="Enter folder path",
                            type="text",
                            value="\\\\wsl.localhost\\Ubuntu\\home\\tpowers\\_Code\\ferm_process_version_json_builder\\04\\04"
                        ),
                        dbc.Button(
                            "Load Files",
                            id="load-folder-btn",
                            color="primary"
                        )
                    ], className="mb-3"),
                    html.Div(id="folder-status")
                ])
            ], className="mb-4"),
            
            # File selection section
            dbc.Card([
                dbc.CardBody([
                    html.H5("📊 Select Setpoint Files", className="card-title"),
                    
                    # Search and controls
                    dbc.Row([
                        dbc.Col([
                            dbc.Input(
                                id="file-search-input",
                                placeholder="Search files...",
                                type="text",
                                className="mb-3"
                            )
                        ], width=8),
                        dbc.Col([
                            dbc.ButtonGroup([
                                dbc.Button("Select All", id="select-all-files-btn", color="secondary", size="sm"),
                                dbc.Button("Clear All", id="clear-all-files-btn", color="secondary", size="sm")
                            ])
                        ], width=4)
                    ]),
                    
                    # File list with grouping
                    html.Div(id="file-group-toggles"),
                    html.Div(id="file-list-display"),
                    
                    # Action buttons
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([
                            dbc.Button(
                                "Process Selected Files",
                                id="process-files-btn",
                                color="success",
                                size="lg",
                                disabled=True,
                                className="w-100"
                            )
                        ], width=8),
                        dbc.Col([
                            dbc.Badge(
                                "0 selected",
                                id="selection-count-badge",
                                color="info",
                                className="fs-6"
                            )
                        ], width=4, className="d-flex align-items-center justify-content-end")
                    ])
                ])
            ], className="mb-4"),
            
            # Processing status
            dbc.Card([
                dbc.CardBody([
                    html.H6("🔄 Processing Status", className="card-title"),
                    html.Div(id="processing-status", children=[
                        html.P("No files processed yet.", className="text-muted mb-0")
                    ])
                ])
            ])
        ])
    
    def setup_callbacks(self):
        """Setup all callbacks for the file selector"""
        
        # Folder loading callback
        @self.app.callback(
            [Output("folder-status", "children"),
             Output("file-data-store", "data")],
            [Input("load-folder-btn", "n_clicks")],
            [State("folder-path-input", "value")],
            prevent_initial_call=True
        )
        def load_folder_files(n_clicks, folder_path):
            if not n_clicks or not folder_path:
                return dash.no_update, dash.no_update
            
            if not os.path.exists(folder_path):
                status = dbc.Alert(
                    f"❌ Folder not found: {folder_path}",
                    color="danger"
                )
                return status, {}
            
            # Use processor to discover files
            self.processor.data_folder = folder_path
            grouped_files = self.processor.discover_files()
            
            # Extract inoculation time from the grouped files result
            inoculation_time = grouped_files.get('inoculation_time')
            
            total_files = len(grouped_files.get('named_sp', [])) + len(grouped_files.get('variable_sp', []))
            
            if total_files > 0:
                status_messages = [
                    html.Strong("✅ Files loaded successfully!"),
                    html.Br(),
                    f"📊 Named SP: {len(grouped_files.get('named_sp', []))} files",
                    html.Br(),
                    f"🔢 Variable SP: {len(grouped_files.get('variable_sp', []))} files"
                ]
                
                # Add inoculation time to status if found
                if inoculation_time:
                    status_messages.extend([
                        html.Br(),
                        f"🕐 Inoculation time: {inoculation_time}"
                    ])
                
                status = dbc.Alert(status_messages, color="success")
            else:
                status = dbc.Alert(
                    "⚠️ No setpoint files found in this folder",
                    color="warning"
                )
            
            return status, grouped_files
        
        # Toggle buttons callback
        @self.app.callback(
            Output("file-group-toggles", "children"),
            [Input("file-data-store", "data"),
             Input("selected-setpoint-files", "data")],
            [State("named-sp-collapsed", "data"),
             State("variable-sp-collapsed", "data")],
            prevent_initial_call=True
        )
        def update_toggle_buttons(file_data, selected_files, named_collapsed, var_collapsed):
            if not file_data:
                return []
            
            # Default collapse states
            if named_collapsed is None:
                named_collapsed = False  # Named SP starts expanded
            if var_collapsed is None:
                var_collapsed = True   # Variable SP starts collapsed
            
            selected_files = selected_files or []
            toggles = []
            
            # Named SP toggle
            named_files = file_data.get('named_sp', [])
            if named_files:
                named_count = len([f for f in named_files if f['path'] in selected_files])
                named_toggle = dbc.Button([
                    html.I(className=f"fas fa-chevron-{'down' if not named_collapsed else 'right'} me-2"),
                    f"📊 Named SP ({named_count}/{len(named_files)} selected)"
                ],
                    id="named-sp-toggle",
                    color="light",
                    className="w-100 text-start mb-2",
                    style={'border': '1px solid #dee2e6'}
                )
                toggles.append(named_toggle)
            
            # Variable SP toggle is now moved to the content section
            
            return toggles
        
        # File list display callback
        @self.app.callback(
            Output("file-list-display", "children"),
            [Input("file-data-store", "data"),
             Input("file-search-input", "value"),
             Input("named-sp-collapsed", "data"),
             Input("variable-sp-collapsed", "data")],
            [State("selected-setpoint-files", "data")],
            prevent_initial_call=True
        )
        def update_file_list_display(file_data, search_value, named_collapsed, var_collapsed, selected_files):
            if not file_data:
                return html.P("Load a folder to see files", className="text-muted")
            
            # Default collapse states
            if named_collapsed is None:
                named_collapsed = False  # Named SP starts expanded
            if var_collapsed is None:
                var_collapsed = True   # Variable SP starts collapsed
            
            selected_files = selected_files or []
            
            file_groups = []
            
            # Named SP section
            named_files = file_data.get('named_sp', [])
            if named_files and not named_collapsed:
                # Apply search filter
                if search_value:
                    visible_named = [f for f in named_files if 
                                   search_value.lower() in f['name'].lower() or 
                                   f['path'] in selected_files]
                else:
                    visible_named = named_files
                
                named_checkboxes = self._create_file_checkboxes(visible_named, selected_files)
                file_groups.extend(named_checkboxes)

            # Variable SP toggle (positioned after named content)
            var_files = file_data.get('variable_sp', [])
            if var_files:
                var_count = len([f for f in var_files if f['path'] in selected_files])
                var_toggle = dbc.Button([
                    html.I(className=f"fas fa-chevron-{'down' if not var_collapsed else 'right'} me-2"),
                    f"🔢 Variable SP ({var_count}/{len(var_files)} selected)"
                ],
                    id="variable-sp-toggle",
                    color="light",
                    className="w-100 text-start mb-2 mt-3",  # Added mt-3 for spacing
                    style={'border': '1px solid #dee2e6'}
                )
                file_groups.append(var_toggle)

            # Variable SP section
            if var_files and not var_collapsed:
                # Apply search filter
                if search_value:
                    visible_var = [f for f in var_files if 
                                 search_value.lower() in f['name'].lower() or 
                                 f['path'] in selected_files]
                else:
                    visible_var = var_files
                
                var_checkboxes = self._create_file_checkboxes(visible_var, selected_files)
                file_groups.extend(var_checkboxes)
            
            return html.Div(file_groups) if file_groups else html.P("No files found", className="text-muted")
        
        # File selection callback
        @self.app.callback(
            [Output("selected-setpoint-files", "data"),
             Output("selection-count-badge", "children"),
             Output("process-files-btn", "disabled")],
            [Input("select-all-files-btn", "n_clicks"),
             Input("clear-all-files-btn", "n_clicks"),
             Input({"type": "sidebar-file-checkbox", "index": ALL}, "value")],
            [State("selected-setpoint-files", "data"),
             State({"type": "sidebar-file-checkbox", "index": ALL}, "id"),
             State("file-data-store", "data"),
             State("file-search-input", "value"),
             State("named-sp-collapsed", "data"),
             State("variable-sp-collapsed", "data")],
            prevent_initial_call=True
        )
        def update_file_selection(select_all_clicks, clear_all_clicks, checkbox_values, current_selected, checkbox_ids, file_data, search_value, named_collapsed, var_collapsed):
            ctx = dash.callback_context
            current_selected = current_selected or []
            
            if not ctx.triggered:
                return current_selected, f"{len(current_selected)} selected", len(current_selected) == 0
            
            trigger_id = ctx.triggered[0]['prop_id']
            
            if "select-all-files-btn" in trigger_id:
                # Select all visible files
                all_files = []
                if file_data:
                    if not named_collapsed:
                        all_files.extend(file_data.get('named_sp', []))
                    if not var_collapsed:
                        all_files.extend(file_data.get('variable_sp', []))
                
                if search_value:
                    all_files = [f for f in all_files if search_value.lower() in f['name'].lower()]
                
                selected = [f['path'] for f in all_files]
                
            elif "clear-all-files-btn" in trigger_id:
                selected = []
                
            else:
                # Handle individual checkbox changes
                selected = []
                if checkbox_values and checkbox_ids:
                    for checkbox_id, value in zip(checkbox_ids, checkbox_values):
                        if value:
                            selected.append(checkbox_id['index'])
            
            count_text = f"{len(selected)} selected"
            is_disabled = len(selected) == 0
            
            return selected, count_text, is_disabled
        
        # Toggle callbacks for collapsible sections
        @self.app.callback(
            Output("named-sp-collapsed", "data"),
            [Input("named-sp-toggle", "n_clicks")],
            [State("named-sp-collapsed", "data")],
            prevent_initial_call=True
        )
        def toggle_named_sp(n_clicks, is_collapsed):
            if n_clicks:
                return not is_collapsed if is_collapsed is not None else True
            return is_collapsed
        
        @self.app.callback(
            Output("variable-sp-collapsed", "data"),
            [Input("variable-sp-toggle", "n_clicks")],
            [State("variable-sp-collapsed", "data")],
            prevent_initial_call=True
        )
        def toggle_variable_sp(n_clicks, is_collapsed):
            if n_clicks:
                return not is_collapsed if is_collapsed is not None else False
            return is_collapsed
        
        # File processing callback
        @self.app.callback(
            [Output("setpoint-data", "data"),
             Output("processing-status", "children")],
            [Input("process-files-btn", "n_clicks")],
            [State("selected-setpoint-files", "data"),
             State("inoculation-time", "data")],
            prevent_initial_call=True
        )
        def process_selected_files(n_clicks, selected_files, inoculation_time):
            if not n_clicks or not selected_files:
                return dash.no_update, dash.no_update
            
            print(f"Processing {len(selected_files)} files...")
            
            # Process each selected file
            processed_data = {}
            success_count = 0
            
            status_items = [html.H6("📊 Processing Results:", className="mb-3")]
            
            for i, file_path in enumerate(selected_files):
                filename = os.path.basename(file_path)
                print(f"Processing file {i+1}/{len(selected_files)}: {filename}")
                
                try:
                    # Use the processor to read and process the file
                    df = self.processor.read_setpoint_file(file_path)
                    
                    if not df.empty:
                        # Convert to format suitable for storing and graphing
                        processed_data[filename] = {
                            'data': df.to_dict('records'),
                            'parameter': df['parameter'].iloc[0] if not df.empty else 'Unknown',
                            'file_path': file_path,
                            'points': len(df)
                        }
                        success_count += 1
                        
                        status_items.append(
                            dbc.Alert([
                                html.Strong(f"✅ {filename}"),
                                html.Br(),
                                f"📊 Parameter: {processed_data[filename]['parameter']}",
                                html.Br(),
                                f"📈 Data points: {processed_data[filename]['points']}"
                            ], color="success", className="py-2")
                        )
                    else:
                        status_items.append(
                            dbc.Alert(f"⚠️ {filename}: No valid data found", color="warning", className="py-2")
                        )
                        
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
                    status_items.append(
                        dbc.Alert(f"❌ {filename}: Processing error", color="danger", className="py-2")
                    )
            
            # Summary
            status_items.insert(1, dbc.Alert([
                html.Strong(f"📋 Summary:"),
                html.Br(),
                f"✅ Successfully processed: {success_count}/{len(selected_files)} files",
                html.Br(),
                f"🕐 Inoculation time: {inoculation_time or 'Not set'}"
            ], color="info", className="mb-3"))
            
            print(f"Processing complete: {success_count}/{len(selected_files)} files successful")
            
            return processed_data, html.Div(status_items)
    
    def _create_file_checkboxes(self, files, selected_files):
        """Helper method to create checkbox list for files"""
        checkboxes = []
        
        for file_info in files:
            is_selected = file_info['path'] in selected_files
            
            checkbox_item = dbc.Row([
                dbc.Col([
                    dbc.Checkbox(
                        id={"type": "sidebar-file-checkbox", "index": file_info['path']},
                        value=is_selected,
                        className="me-2"
                    ),
                    html.Label(
                        file_info['name'],
                        className="form-check-label",
                        style={'fontSize': '0.9rem', 'cursor': 'pointer'}
                    )
                ], className="d-flex align-items-center")
            ], className="mb-1 ms-3")
            
            checkboxes.append(checkbox_item)
        
        return checkboxes


# Function to integrate with main app
def setup_file_selector(app):
    """Setup file selector functionality in the main app"""
    file_selector = FileSelector(app)
    
    # Add required data stores to main app if not already present
    @app.callback(
        Output("file-sidebar-content", "children"),
        [Input("file-sidebar-open", "data")]
    )
    def update_file_sidebar_content(is_open):
        if is_open:
            return file_selector.get_layout()
        return html.Div()  # Empty when closed
    
    return file_selector