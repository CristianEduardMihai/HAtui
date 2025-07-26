# HAtui - Home Assistant Terminal UI

Standalone, self-contained TUI tool that lets users control and monitor their Home Assistant smart home setup through customizable terminal dashboards.

## 🎥 Live Demo

Check out HAtui in action: **[Live Demo Video](https://youtu.be/t3SGov1zZ1c)**
* stream has HUUGE delay, sorry for that

Want to try it yourself? Use this demo environment:

```bash
# Copy to .env file
HA_URL=https://demo-ha-container.mihais-ai-playground.xyz
HA_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIzOTk2MDBkMzZlYWU0NmU2YTAwMDE5NmYwOTBlMmJkOCIsImlhdCI6MTc1MzQ0NjYyNiwiZXhwIjoyMDY4ODA2NjI2fQ.nfePeS-QQ8oA0wjOuyzRfdfT3v8Tkdp-bowuaQ5uQ58
```

config.yaml already has the two entities set up, so you can start playing right away

❗Please report any bugs you may find
And keep in mind, stream might go down at any time. Power here is weird.

## Features

- **Multi-Dashboard Support**: Create and manage multiple custom dashboards
- **Real-time Control**: Toggle lights, adjust brightness, monitor sensors
- **Keyboard Navigation**: Full keyboard-driven interface
- **Entity Management**: Add, remove, and rename entities in edit mode
- **Dashboard Management**: Create, delete, rename, and reorder dashboards
- **Brightness Staging**: Smooth brightness control with staging to prevent API flooding
- **Auto-Configuration**: Creates default config on first run

## Installation & Usage

### Quick Start (One Command)

1. **Clone and run**:
   ```bash
   git clone https://github.com/CristianEduardMihai/HAtui.git
   cd HAtui
   python3 run.py # python if you're on Windows
   ```

That's it! The runner script will automatically:
- Detect your operating system
- Create a virtual environment
- Install all dependencies
- Launch HAtui (You'll still need to configure your Home Assistant connection in the `.env` file)


### Configuration

Before first use, set up your Home Assistant connection:

```bash
# Copy the example and edit with your details
cp example.env .env

# Edit .env with your Home Assistant URL and token
# HA_URL=http://your-ha-instance:8123
# HA_TOKEN=your_long_lived_access_token
```

### Alternative: Pre-built Binaries

Pre-built binaries are available in the [Releases](https://github.com/CristianEduardMihai/HAtui/releases) section:

- **Windows**: `hatui-windows.exe`
- **Linux**: `hatui-linux`
- **macOS**: `hatui-macos`

Download the appropriate binary for your platform, set up the `.env` file, and run!

## Controls

### Navigation
- **Arrow Keys** (↑↓←→): Navigate entities
- **Space**: Toggle entity (lights, switches, etc.)
- **Ctrl+↑↓**: Adjust brightness (for lights)
- **Ctrl+←→**: Switch between dashboards
- **r**: Refresh entities
- **q**: Quit

### Edit Mode
- **e**: Enter edit mode
- **a**: Add new entity
- **Delete**: Remove entity
- **Enter**: Pick/Drop entity (move entities)
- **n**: Edit entity name
- **d**: Dashboard management
- **Escape**: Exit edit mode

### Dashboard Management (in edit mode)
- **Ctrl+N**: Create new dashboard
- **F2**: Rename dashboard
- **Delete**: Delete dashboard
- **Ctrl+↑↓**: Reorder dashboards
- **Enter**: Switch to dashboard
- **Escape**: Close manager

## Getting Your Home Assistant Token

1. In Home Assistant, go to your **Profile** (click your username)
2. Scroll down to **Security** section
3. Click **Long-lived access tokens**
4. Click **Create Token**
5. Give it a name (e.g., "HAtui")
6. Copy the generated token to your `.env` file

## Configuration

HAtui automatically creates a `config.yaml` file on first run with a sample dashboard. You can:

- Edit this file directly
- Use the built-in dashboard and entity management (press 'e' for edit mode)
- Create multiple dashboards with different entity layouts

### Example config.yaml structure:
```yaml
current_dashboard: 0
dashboards:
  - name: "Living Room"
    rows: 3
    cols: 3
    refresh_interval: 5
    entities:
      - entity: "light.living_room"
        position: [0, 0]
        type: "light"
        display_name: "Main Light"
```