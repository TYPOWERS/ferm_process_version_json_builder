# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application
```bash
python app.py
```
The Dash app will start on http://127.0.0.1:8050 by default.

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Development & Debugging
```bash
# Run with debug mode (default in app.py)
python app.py
```
The app runs with `debug=True` by default, enabling hot reloading during development.

## Project Architecture

### Core Structure
This is a Dash-based web application for building fermentation temperature profiles. The application generates JSON configurations that describe temperature control sequences over time.

### Key Components

**Temperature Profile Components:**
- `constant`: Flat temperature line (setpoint, duration)
- `ramp`: Linear temperature change (start_temp, end_temp, duration) 
- `pwm`: Pulse width modulation pattern (high_temp, low_temp, pulse_percent, duration)
- `pid`: PID controller configuration (controller name, setpoint, min/max allowed, duration)

**Main Application Flow:**
1. User selects component type from dropdown
2. Dynamic form fields appear based on component type
3. User fills in parameters and clicks "Add Component"
4. Component is added to list and graph updates in real-time
5. Components can be reordered via drag-and-drop or move buttons
6. JSON can be exported containing the complete profile

### Data Flow
- `components-store`: Dash Store containing list of all temperature components
- `selected-component`: Tracks currently selected component for editing/moving
- `pid-controller-count`: Manages dynamic PID controller form generation
- `total-runtime`: Organism-specific total runtime (Bl/Bs: 5 days, Ao/An: 7 days, Ec: 3 days)
- `used-runtime`: Cumulative runtime of added components (auto-fills remaining duration when 0)
- `drag-data`: Handles drag-and-drop reordering via JavaScript-Python bridge
- Components are rendered as both a selectable list and a Plotly time-series graph
- Graph shows cumulative time progression with proper temperature transitions

### Interactive Features
- **Drag-and-drop reordering**: Custom JavaScript implementation for component reordering
- **Dynamic form generation**: Fields change based on selected component type
- **Real-time graphing**: Plotly graph updates automatically as components are added/modified
- **Multi-controller PID**: Supports multiple PID controllers in a single component

### Benchling Integration
Use benchling-sdk for any Benchling database operations to check for existing profiles and prevent duplicates.

### Technology Stack
- **Frontend Framework**: Dash with Bootstrap components (dash-bootstrap-components)
- **Plotting**: Plotly for interactive temperature graphs
- **Data Handling**: Pandas for CSV processing
- **Styling**: Custom CSS with drag-and-drop animations
- **State Management**: Dash Store components for client-side state

### Key Code Patterns
- **Pattern matching inputs**: Uses `{"type": "dynamic-input", "id": ALL}` for flexible form handling
- **Callback chaining**: Complex callbacks with `allow_duplicate=True` for state updates
- **Custom JavaScript**: Embedded drag-and-drop functionality in `app.index_string`
- **UUID generation**: Each component gets unique ID for tracking and manipulation
- **Clientside callbacks**: Uses `app.clientside_callback` for performance-critical drag operations
- **Dynamic form generation**: Fields change based on component type and previous inputs (e.g., PID controllers auto-add)

## Code Style
- Use benchling sdk for any benchling interaction
- Follow Dash callback patterns with proper input/output/state declarations
- Use Bootstrap classes for consistent styling
- Implement proper error handling for form validation