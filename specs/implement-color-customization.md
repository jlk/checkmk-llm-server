# Color Customization for Interactive Mode

## Overview
Create a flexible color customization system that allows users to personalize the interactive mode appearance through configuration files, environment variables, and runtime commands.

## Current State Analysis

### Existing Foundation
- **UIManager Class**: Comprehensive ANSI color support in `checkmk_mcp_server/interactive/ui_manager.py`
- **Current Colors**: 8 base colors (red, green, yellow, blue, magenta, cyan, white) plus styles (bold, dim, reset)
- **Message Types**: 6 styled message types with predefined colors:
  - `INFO`: blue with ℹ️ icon
  - `SUCCESS`: green with ✅ icon
  - `WARNING`: yellow with ⚠️ icon
  - `ERROR`: red with ❌ icon
  - `HELP`: cyan with 🔧 icon
  - `PROMPT`: magenta with 🔧 icon
- **Configuration System**: Robust config system supporting YAML/JSON/TOML and environment variables

### Current Limitations
- Fixed color scheme with no customization options
- No theme support for different user preferences
- Limited color palette (only 8 basic colors)
- No accessibility considerations (high-contrast modes)
- No runtime color changes without restart

## Implementation Plan

### Phase 1: Enhanced Color System

#### 1.1 Expand Color Palette
**Goal**: Support more colors and advanced terminal features

**Implementation**:
- Add 256-color support for modern terminals
- Add bright color variants (bright_red, bright_green, etc.)
- Add RGB/hex color support for terminals that support it
- Add background color variants
- Add text effects (underline, strikethrough, blink)

**New Colors to Add**:
```python
colors = {
    # Basic colors (existing)
    'red': '\033[31m',
    'green': '\033[32m',
    # ... existing colors ...
    
    # Bright variants
    'bright_red': '\033[91m',
    'bright_green': '\033[92m',
    'bright_yellow': '\033[93m',
    'bright_blue': '\033[94m',
    'bright_magenta': '\033[95m',
    'bright_cyan': '\033[96m',
    'bright_white': '\033[97m',
    
    # Additional colors
    'orange': '\033[38;5;208m',
    'purple': '\033[38;5;129m',
    'pink': '\033[38;5;205m',
    'gray': '\033[90m',
    
    # Text effects
    'underline': '\033[4m',
    'strikethrough': '\033[9m',
}
```

#### 1.2 Theme System
**Goal**: Predefined color themes for different preferences

**Themes to Implement**:
1. **Default Theme**: Current colors (blue info, green success, etc.)
2. **Dark Theme**: Optimized for dark terminals with brighter colors
3. **Light Theme**: Optimized for light terminals with darker colors
4. **Minimal Theme**: Reduced colors, more monochrome
5. **High Contrast Theme**: Accessibility-focused with high contrast
6. **Colorful Theme**: More vibrant colors for visual appeal

**Theme Structure**:
```python
themes = {
    'default': {
        'info': 'blue',
        'success': 'green',
        'warning': 'yellow',
        'error': 'red',
        'help': 'cyan',
        'prompt': 'magenta',
    },
    'dark': {
        'info': 'bright_blue',
        'success': 'bright_green',
        'warning': 'bright_yellow',
        'error': 'bright_red',
        'help': 'bright_cyan',
        'prompt': 'bright_magenta',
    },
    # ... other themes
}
```

### Phase 2: Configuration Integration

#### 2.1 Configuration Schema
**Goal**: Add UI configuration to the existing config system

**Add to `config.py`**:
```python
class UIConfig(BaseModel):
    """Configuration for UI appearance."""
    
    theme: str = Field(default="default", description="Color theme name")
    use_colors: bool = Field(default=True, description="Enable colored output")
    auto_detect_terminal: bool = Field(default=True, description="Auto-detect terminal capabilities")
    custom_colors: Optional[Dict[str, str]] = Field(None, description="Custom color overrides")

class AppConfig(BaseModel):
    """Main application configuration."""
    
    checkmk: CheckmkConfig
    llm: LLMConfig
    ui: UIConfig = Field(default_factory=UIConfig)  # Add UI config
    # ... existing fields
```

#### 2.2 Configuration File Support
**Goal**: Allow UI customization through config files

**Example configuration (`config.yaml`)**:
```yaml
# Existing config sections...
checkmk:
  server_url: "https://checkmk.example.com"
  # ...

# New UI section
ui:
  theme: "dark"
  use_colors: true
  auto_detect_terminal: true
  custom_colors:
    info: "bright_blue"
    success: "bright_green"
    prompt: "purple"
```

#### 2.3 Environment Variables
**Goal**: Support environment-based color configuration

**Environment Variables**:
- `CHECKMK_UI_THEME`: Set theme (default, dark, light, minimal, high-contrast, colorful)
- `CHECKMK_UI_USE_COLORS`: Enable/disable colors (true/false)
- `CHECKMK_UI_INFO_COLOR`: Override info color
- `CHECKMK_UI_SUCCESS_COLOR`: Override success color
- `CHECKMK_UI_WARNING_COLOR`: Override warning color
- `CHECKMK_UI_ERROR_COLOR`: Override error color
- `CHECKMK_UI_HELP_COLOR`: Override help color
- `CHECKMK_UI_PROMPT_COLOR`: Override prompt color

### Phase 3: Implementation Details

#### 3.1 New File: `color_manager.py`
**Goal**: Centralized color management system

**Location**: `checkmk_mcp_server/interactive/color_manager.py`

**Key Classes**:
```python
class ColorManager:
    """Manages color themes and terminal capabilities."""
    
    def __init__(self, config: UIConfig):
        self.config = config
        self.terminal_capabilities = self._detect_terminal_capabilities()
        self.current_theme = self._load_theme(config.theme)
    
    def get_color_code(self, color_name: str) -> str:
        """Get ANSI color code for color name."""
    
    def get_message_color(self, message_type: MessageType) -> str:
        """Get color for specific message type."""
    
    def set_theme(self, theme_name: str) -> bool:
        """Change current theme."""
    
    def list_themes(self) -> List[str]:
        """List available themes."""
    
    def preview_colors(self) -> str:
        """Generate color preview text."""
    
    def _detect_terminal_capabilities(self) -> Dict[str, bool]:
        """Detect what the terminal supports."""
```

#### 3.2 Enhanced `ui_manager.py`
**Goal**: Integrate ColorManager into existing UIManager

**Changes**:
```python
class UIManager:
    def __init__(self, use_colors: bool = True, config: Optional[UIConfig] = None):
        self.use_colors = use_colors and sys.stdout.isatty()
        self.color_manager = ColorManager(config or UIConfig())
    
    def colorize(self, text: str, color: str) -> str:
        """Use ColorManager for color codes."""
        if not self.use_colors:
            return text
        
        color_code = self.color_manager.get_color_code(color)
        reset_code = self.color_manager.get_color_code('reset')
        return f"{color_code}{text}{reset_code}"
    
    # Update existing methods to use ColorManager
```

#### 3.3 Interactive Commands
**Goal**: Runtime color customization commands

**New Commands in Interactive Mode**:
1. `theme list` - Show available themes
2. `theme set <name>` - Change current theme
3. `theme current` - Show current theme
4. `colors show` - Preview all colors with examples
5. `colors test` - Test color combinations
6. `colors reset` - Reset to default theme

**Implementation in `cli.py`**:
```python
def handle_theme_command(self, args: List[str]) -> str:
    """Handle theme-related commands."""
    if not args:
        return "Usage: theme [list|set|current]"
    
    subcommand = args[0].lower()
    if subcommand == "list":
        themes = self.ui_manager.color_manager.list_themes()
        return f"Available themes: {', '.join(themes)}"
    elif subcommand == "set" and len(args) > 1:
        theme_name = args[1]
        if self.ui_manager.color_manager.set_theme(theme_name):
            return f"Theme changed to: {theme_name}"
        else:
            return f"Unknown theme: {theme_name}"
    elif subcommand == "current":
        current = self.ui_manager.color_manager.current_theme['name']
        return f"Current theme: {current}"
```

### Phase 4: Advanced Features

#### 4.1 Terminal Capability Detection
**Goal**: Adapt to terminal capabilities automatically

**Features**:
- Detect 256-color support
- Detect RGB/truecolor support
- Detect emoji support
- Fallback gracefully for limited terminals

#### 4.2 Accessibility Features
**Goal**: Ensure usability for users with visual impairments

**High-Contrast Theme**:
```python
'high_contrast': {
    'info': 'bright_white',
    'success': 'bright_white',
    'warning': 'black',  # on yellow background
    'error': 'bright_white',  # on red background
    'help': 'bright_white',
    'prompt': 'bright_white',
    'use_backgrounds': True,
}
```

#### 4.3 Color Preview System
**Goal**: Help users choose and test colors

**Preview Features**:
- Show all message types with current colors
- Display color palette with names
- Test combinations before applying
- Show before/after when changing themes

### Phase 5: Testing Strategy

#### 5.1 Unit Tests
**File**: `tests/test_color_manager.py`

**Test Cases**:
- Color code generation
- Theme loading and switching
- Terminal capability detection
- Configuration integration
- Invalid theme handling

#### 5.2 Integration Tests
**File**: `tests/test_ui_color_integration.py`

**Test Cases**:
- End-to-end color application
- Config file color loading
- Environment variable overrides
- Interactive command functionality

#### 5.3 Terminal Compatibility Tests
**Manual Testing**:
- Test on different terminal emulators
- Test on different operating systems
- Test with limited color terminals
- Test accessibility with screen readers

### Phase 6: Documentation Updates

#### 6.1 Configuration Documentation
**Update**: `examples/configs/` files

**Add UI examples**:
```yaml
# examples/configs/ui-themes.yaml
ui:
  theme: "dark"
  use_colors: true
  custom_colors:
    info: "bright_blue"
    success: "bright_green"
```

#### 6.2 README Updates
**Add section**: "Customizing Colors and Themes"

**Content**:
- How to set themes
- Available themes
- Custom color configuration
- Environment variables
- Interactive commands

#### 6.3 Help System Updates
**Update**: `help_system.py`

**Add help entries**:
- Theme commands help
- Color commands help
- Configuration examples

## Implementation Priority

### High Priority (Week 1)
1. Create ColorManager class with basic theme support
2. Integrate ColorManager into UIManager
3. Add basic theme switching commands
4. Update configuration system

### Medium Priority (Week 2)
1. Implement predefined themes (dark, light, minimal)
2. Add configuration file support
3. Add environment variable support
4. Create color preview functionality

### Low Priority (Week 3)
1. Add advanced color features (256-color, RGB)
2. Implement accessibility features
3. Add terminal capability detection
4. Create comprehensive tests

## Success Metrics

### Functional Requirements
- ✅ Users can change themes via config files
- ✅ Users can change themes via environment variables
- ✅ Users can change themes via interactive commands
- ✅ At least 5 predefined themes available
- ✅ Custom color overrides work correctly
- ✅ Graceful fallback for terminals without color support

### User Experience Requirements
- ✅ Theme changes apply immediately in interactive mode
- ✅ Color preview helps users choose themes
- ✅ High-contrast theme improves accessibility
- ✅ Documentation is clear and comprehensive

### Technical Requirements
- ✅ No breaking changes to existing functionality
- ✅ Backward compatibility with current configurations
- ✅ Performance impact is minimal
- ✅ Code is well-tested and maintainable

## Risk Mitigation

### Terminal Compatibility
- **Risk**: Colors don't work on some terminals
- **Mitigation**: Auto-detection and graceful fallback

### Performance Impact
- **Risk**: Color processing slows down output
- **Mitigation**: Cache color codes and optimize rendering

### Configuration Complexity
- **Risk**: Too many options confuse users
- **Mitigation**: Sensible defaults and clear documentation

### Accessibility
- **Risk**: Colors make interface less accessible
- **Mitigation**: High-contrast theme and option to disable colors

## Future Enhancements

### Advanced Color Features
- Custom theme creation wizard
- Color scheme import/export
- Integration with terminal theme detection
- Seasonal/time-based theme switching

### Visual Enhancements
- Gradient text effects
- Animated prompts
- Custom icons per theme
- Theme-based layout changes

### Integration Features
- Sync with system dark/light mode
- Integration with popular terminal themes
- Theme sharing community
- Plugin system for custom themes