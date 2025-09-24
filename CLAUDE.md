# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Application

**Main integrated application (recommended):**
```bash
python integrated_app.py
```

**Original single-file application:**
```bash
python app.py
```

Both applications will start on http://127.0.0.1:8050 by default.

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Key Dependencies
- `dash==2.14.1`: Core web framework
- `plotly==5.17.0`: Interactive graphing
- `pandas==2.1.1`: Data processing
- `benchling-sdk`: Benchling database integration
- `dash-bootstrap-components==1.5.0`: UI components
- `scipy>=1.10.0`: Scientific computing for analysis algorithms
- `uuid`: Component unique identification

### Development & Debugging
```bash
# Run with debug mode (default in app.py)
python app.py
```
The app runs with `debug=True` by default, enabling hot reloading during development.

## Project Architecture

### Core Structure
This is a Dash-based web application for building fermentation process profiles. The application generates JSON configurations that describe process control sequences over time.

### Multi-App Architecture
The project follows a modular structure with multiple integrated applications:

**Core Applications:**
- `integrated_app.py`: Main integrated application combining multiple functionalities (recommended)
- `app.py`: Original single-file Dash application for profile building

**Modular Components:**
- `sidebar_file_selector.py`: File browser and setpoint selection sidebar
- `sidebar_octopus.py`: Secondary sidebar (placeholder for future features)
- `component_builder.py`: Analysis engine for automatic component generation from setpoint data
- `derivative_component_builder.py`: Extended analysis capabilities for component generation
- `profile_builder.py`: Core profile building functionality
- `process_setpoint_files.py`: Setpoint file processing and visualization

**Testing and Development:**
- `test_ramp_detection.py`: Tests for ramp detection algorithms

### Key Components

**Process Profile Components:**
- `constant`: Flat setpoint line (setpoint, duration)
- `ramp`: Linear value change (start_temp, end_temp, duration) 
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
- `components-store`: Dash Store containing list of all profile components
- `selected-component`: Tracks currently selected component for editing/moving
- `pid-controller-count`: Manages dynamic PID controller form generation
- `total-runtime`: Organism-specific total runtime (Bl/Bs: 5 days, Ao/An: 7 days, Ec: 3 days)
- `used-runtime`: Cumulative runtime of added components (auto-fills remaining duration when 0)
- `drag-data`: Handles drag-and-drop reordering via JavaScript-Python bridge
- Components are rendered as both a selectable list and a Plotly time-series graph
- Graph shows cumulative time progression with proper value transitions

### Interactive Features
- **Drag-and-drop reordering**: Custom JavaScript implementation for component reordering
- **Dynamic form generation**: Fields change based on selected component type
- **Real-time graphing**: Plotly graph updates automatically as components are added/modified
- **Multi-controller PID**: Supports multiple PID controllers in a single component
- **Sidebar Interface**: Overlay sidebars (1/2 screen width) with toggle icons for file selection and future features
- **Graph Overlay**: Displays profile components over setpoint data with coordinated time alignment via inoculation time
- **Component Editing**: Click-to-edit workflow with update/add toggle functionality

### Intelligent Component Generation
The application includes sophisticated analysis engines that can automatically detect patterns in setpoint data and generate profile components:

**Pattern Recognition Algorithms:**
- **Constant Detection**: Identifies flat periods with 0 variance threshold, merges adjacent constants with same values
- **Ramp Detection**: Identifies linear changes with 1-unit tolerance, merges similar slopes within tolerance
- **PID Detection**: Recognizes control patterns from sequences of 3+ small constant changes
- **Component Consolidation**: Merges adjacent similar components to minimize complexity and create efficient profiles

**Processing Configuration:**
- **Value Rounding**: 1 decimal place precision for setpoint values
- **Duration Precision**: 5-minute minimum precision for time durations
- **Minimum Thresholds**: 10-minute minimum duration for component generation
- **Data Source**: Uses step-function processed setpoint data for analysis

**Workflow Integration:**
- Auto-generates components from uploaded setpoint files
- Provides review/approval interface before adding to profile
- Supports individual component editing before bulk approval
- Replaces existing manual components when approved

### Benchling Integration
Use benchling-sdk for any Benchling database operations to check for existing profiles and prevent duplicates.

### Technology Stack
- **Frontend Framework**: Dash with Bootstrap components (dash-bootstrap-components)
- **Plotting**: Plotly for interactive process graphs
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

### File Structure Patterns
- **Modular callbacks**: Each module handles its own callback registration
- **Shared stores**: Use Dash Store components for cross-module communication
- **Import patterns**: Clean module interfaces with defined responsibilities
- **Component isolation**: Each sidebar and feature area maintained separately

## Code Style
- Use benchling sdk for any benchling interaction
- Follow Dash callback patterns with proper input/output/state declarations
- Use Bootstrap classes for consistent styling
- Implement proper error handling for form validation
- Maintain modular structure when adding new features
- Use UUID generation for unique component tracking
- Round numerical values consistently (1 decimal for measurements, 5-minute duration precision)