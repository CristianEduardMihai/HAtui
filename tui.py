import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Static, Button
from textual.reactive import reactive
from textual.binding import Binding
from ha_client import HomeAssistantClient


class LightWidget(Static):
    def __init__(self, entity_id: str, ha_client: HomeAssistantClient):
        super().__init__()
        self.entity_id = entity_id
        self.ha_client = ha_client
        self.state = "unknown"
        self.friendly_name = "Light"
        self.styles.border = ("heavy", "white")
        self.styles.padding = (1, 2)
        self.styles.margin = 1
    
    def compose(self) -> ComposeResult:
        yield Static(f"💡 {self.friendly_name}", id="light-title")
        yield Static(f"State: {self.state}", id="light-state")
        yield Static("Press [bold]SPACE[/] to toggle", id="light-help")
    
    def update_display(self) -> None:
        # Update the display with current state and name.
        try:
            # Update state
            state_widget = self.query_one("#light-state", Static)
            state_widget.update(f"State: {self.state}")
            
            # Update colors based on state
            if self.state == "on":
                self.styles.border = ("heavy", "green")
                state_widget.styles.color = "green"
            elif self.state == "off":
                self.styles.border = ("heavy", "red")
                state_widget.styles.color = "red"
            else:
                self.styles.border = ("heavy", "yellow")
                state_widget.styles.color = "yellow"
            
            # Update title
            title_widget = self.query_one("#light-title", Static)
            title_widget.update(f"💡 {self.friendly_name}")
        except Exception:
            # Widgets not ready yet, ignore
            pass
    
    async def refresh_state(self) -> None:
        # Fetch the current state from Home Assistant.
        try:
            state_data = await self.ha_client.get_state(self.entity_id)
            if state_data:
                self.state = state_data.get("state", "unknown")
                self.friendly_name = state_data.get("attributes", {}).get("friendly_name", self.entity_id)
                self.update_display()
        except Exception as e:
            self.state = "error"
            self.update_display()
            self.app.notify(f"Error fetching state: {e}", severity="error")
    
    async def toggle_light(self) -> None:
        # Toggle the light state.
        try:
            success = await self.ha_client.toggle_light(self.entity_id)
            if success:
                self.app.notify("Light toggled successfully!", severity="information")
                # Refresh state after a short delay
                await asyncio.sleep(0.5)
                await self.refresh_state()
            else:
                self.app.notify("Failed to toggle light", severity="error")
        except Exception as e:
            self.app.notify(f"Error toggling light: {e}", severity="error")


class SimpleTUI(App):
    # TUI for controlling a single Home Assistant light.

    CSS = """
    Screen {
        background: $surface;
    }
    
    Container {
        height: 100%;
        width: 100%;
        align: center middle;
    }
    
    LightWidget {
        width: 50;
        height: 8;
    }
    
    #light-title {
        text-align: center;
        text-style: bold;
    }
    
    #light-state {
        text-align: center;
        margin: 1 0;
    }
    
    #light-help {
        text-align: center;
        text-style: dim;
    }
    """
    
    BINDINGS = [
        Binding("space", "toggle_light", "Toggle Light"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.entity_id = "light.light_switch1_light"  # Your light entity
        self.ha_client = None
        self.light_widget = None
    
    def compose(self) -> ComposeResult:
        # UI layout.
        yield Header()
        with Container():
            with Vertical():
                self.light_widget = LightWidget(self.entity_id, self.ha_client)
                yield self.light_widget
        yield Footer()
    
    async def on_mount(self) -> None:
        # Initialize the app when it starts.
        try:
            # Initialize Home Assistant client
            self.ha_client = HomeAssistantClient()
            self.light_widget.ha_client = self.ha_client
            
            # Test connection
            if not await self.ha_client.test_connection():
                self.notify("Failed to connect to Home Assistant!", severity="error")
                return
            
            # Load initial state
            await self.light_widget.refresh_state()
            
            # Set up auto-refresh timer
            self.set_interval(3.0, self.auto_refresh)
            
            self.notify("Connected to Home Assistant!", severity="information")
            
        except Exception as e:
            self.notify(f"Initialization error: {e}", severity="error")
    
    async def auto_refresh(self) -> None:
        # Automatically refresh the light state.
        if self.light_widget:
            await self.light_widget.refresh_state()
    
    async def action_toggle_light(self) -> None:
        # Handle the toggle light action.
        if self.light_widget:
            await self.light_widget.toggle_light()
    
    async def action_refresh(self) -> None:
        # Handle manual refresh action.
        if self.light_widget:
            await self.light_widget.refresh_state()
            self.notify("State refreshed!", severity="information")


def main():
    # Run the TUI application.
    app = SimpleTUI()
    app.title = "Home Assistant TUI"
    app.sub_title = "Control your lights with ease"
    app.run()


if __name__ == "__main__":
    main()
