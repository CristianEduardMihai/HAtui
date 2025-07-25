import asyncio
import os
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from textual.events import Key
from typing import Optional
from ha_client import HomeAssistantClient
from config_manager import ConfigManager, EntityConfig
from entity_widget import EntityWidget
from components.entity_browser import EntityBrowserScreen
from components.grid_dashboard import GridDashboard
from components.edit_controller import EditController


class MainTUI(App):
    # main TUI app with interactive config
    CSS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "styles", "main.css")
    
    BINDINGS = [
        Binding("space", "handle_space_key", "Toggle Entity"),
        Binding("ctrl+up", "brightness_up", "Brightness Up"),
        Binding("ctrl+down", "brightness_down", "Brightness Down"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "edit_mode", "Edit Mode"),
        Binding("a", "add_entity", "Add Entity"),
        Binding("delete", "remove_entity", "Remove"),
        Binding("enter", "pick_drop_entity", "Pick/Drop"),
        Binding("up", "move_up", "Move Up"),
        Binding("down", "move_down", "Move Down"), 
        Binding("left", "move_left", "Move Left"),
        Binding("right", "move_right", "Move Right"),
        Binding("escape", "exit_edit", "Exit Edit"),
        Binding("q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ha_client = None
        self.dashboard = None
        self.edit_controller = EditController(self)
        self.last_toggle_time = {} 
    
    def compose(self) -> ComposeResult:
        yield Header()
        self.dashboard = GridDashboard(3, 3)
        yield self.dashboard
        yield Static("Mode: View | Press 'e' for Edit Mode", id="status-bar")
        yield Footer()
    
    async def on_mount(self) -> None:
        # start up the app
        try:
            # load config file
            config = self.config_manager.load_config()
            # connect to HA
            self.ha_client = HomeAssistantClient()
            
            # make sure connection works
            if not await self.ha_client.test_connection():
                self.notify("Failed to connect to Home Assistant!", severity="error")
                return
            
            # update grid size from config
            self.dashboard.rows = config.dashboard.rows
            self.dashboard.cols = config.dashboard.cols
            
            # load entities from config
            await self.load_entities_from_config()
            
            # start auto-refresh timer
            self.set_interval(config.dashboard.refresh_interval, self.auto_refresh)
            
            # initialize selection in view mode
            self.dashboard.set_selected_position(self.edit_controller.selected_row, self.edit_controller.selected_col)
            self.edit_controller.update_status_bar()
            
            # set the title to the dashboard name
            self.title = config.dashboard.name
            
            self.notify("Connected to Home Assistant!", severity="information")
            
        except Exception as e:
            self.notify(f"Initialization error: {e}", severity="error")
    
    async def load_entities_from_config(self) -> None:
        # load up all the entities from config file
        config = self.config_manager.config
        if not config:
            return
        
        for entity_config in config.dashboard.entities:
            # Validate position is within grid bounds
            if (entity_config.row >= self.dashboard.rows or 
                entity_config.col >= self.dashboard.cols or
                entity_config.row < 0 or entity_config.col < 0):
                self.notify(f"Skipping {entity_config.entity}: position ({entity_config.row}, {entity_config.col}) is outside grid bounds", 
                           severity="warning")
                continue
            
            try:
                widget = EntityWidget(entity_config, self.ha_client)
                self.dashboard.add_entity_widget(widget, entity_config.row, entity_config.col)
                await widget.refresh_state()
            except Exception as e:
                self.notify(f"Error loading entity {entity_config.entity}: {e}", severity="error")
    
    async def auto_refresh(self) -> None:
        # refresh all entity states automatically
        try:
            # Create a copy of the values to avoid dictionary changed during iteration
            widgets_to_refresh = list(self.dashboard.widgets_grid.values())
            for widget in widgets_to_refresh:
                try:
                    await widget.refresh_state()
                except Exception as e:
                    # Skip widgets that might have been removed or are in an invalid state
                    self.notify(f"Skipping refresh for widget: {e}", severity="warning")
        except Exception as e:
            # Handle any other errors in auto-refresh
            self.notify(f"Auto-refresh error: {e}", severity="error")
    
    def action_edit_mode(self) -> None:
        # toggle edit mode on/off
        self.edit_controller.toggle_edit_mode()
    
    def action_exit_edit(self) -> None:
        # exit edit mode
        self.edit_controller.exit_edit_mode()
    
    async def action_pick_drop_entity(self) -> None:
        # pick up or drop an entity for moving
        await self.edit_controller.pick_drop_entity()
    
    def action_add_entity(self) -> None:
        # open entity browser to add new entity
        self.edit_controller.add_entity()
    
    async def action_remove_entity(self) -> None:
        # remove entity at current selected position
        await self.edit_controller.remove_entity()
    
    def action_move_up(self) -> None:
        # Move selection up
        self.edit_controller.move_up()
        # Update status bar if a light is selected
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        self.update_status_with_brightness(widget)
    
    def action_move_down(self) -> None:
        # Move selection down
        self.edit_controller.move_down()
        # Update status bar if a light is selected
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        self.update_status_with_brightness(widget)
    
    def action_move_left(self) -> None:
        # Move selection left
        self.edit_controller.move_left()
        # Update status bar if a light is selected
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        self.update_status_with_brightness(widget)
    
    def action_move_right(self) -> None:
        # Move selection right
        self.edit_controller.move_right()
        # Update status bar if a light is selected
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        self.update_status_with_brightness(widget)
        
    async def action_brightness_up(self) -> None:
        # Increase brightness of selected light
        import time
        
        if self.edit_controller.edit_mode:
            return
        
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        if not widget or not widget.supports_brightness():
            return
            
        entity_id = widget.entity_config.entity
        brightness_key = f"{entity_id}_brightness_up"
        
        # Check for debouncing
        current_time = time.time()
        if brightness_key in self.last_toggle_time:
            time_since_last = current_time - self.last_toggle_time[brightness_key]
            if time_since_last < 0.1:
                return
                
        self.last_toggle_time[brightness_key] = current_time
        
        # Adjust brightness
        success = await widget.adjust_brightness("up")
        if success:
            current_pct = round(widget.attributes.get('brightness', 0) / 255 * 100)
            
            self.update_status_with_brightness(widget)
        else:
            self.notify("Cannot adjust brightness", severity="warning")
    
    async def action_brightness_down(self) -> None:
        # Decrease brightness of selected light
        import time
        
        if self.edit_controller.edit_mode:
            return
        
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        if not widget or not widget.supports_brightness():
            return
            
        entity_id = widget.entity_config.entity
        brightness_key = f"{entity_id}_brightness_down"
        
        # debouncing
        current_time = time.time()
        if brightness_key in self.last_toggle_time:
            time_since_last = current_time - self.last_toggle_time[brightness_key]
            if time_since_last < 0.1:
                return
                
        self.last_toggle_time[brightness_key] = current_time
        
        # Adjust brightness
        success = await widget.adjust_brightness("down")
        if success:
            current_pct = round(widget.attributes.get('brightness', 0) / 255 * 100)
            
            # Update status
            self.update_status_with_brightness(widget)
        else:
            self.notify("Cannot adjust brightness", severity="warning")
    
    async def action_refresh(self) -> None:
        # manually refresh all entities
        await self.auto_refresh()
        self.notify("Refreshed all entities!", severity="information")
    
    def update_status_with_brightness(self, widget) -> None:
        if widget and widget.entity_type == 'light' and widget.supports_brightness() and widget.state == 'on':
            brightness_pct = round(widget.attributes.get('brightness', 0) / 255 * 100)
            status_bar = self.query_one("#status-bar", Static)
            if self.edit_controller.edit_mode:
                status_bar.update(f"Mode: Edit | CTRL+↑↓: Brightness ({brightness_pct}%)")
            else:
                status_bar.update(f"Mode: View | CTRL+↑↓: Brightness ({brightness_pct}%)")
        else:
            self.edit_controller.update_status_bar()
    
    
    async def action_handle_space_key(self) -> None:
        import time
        if self.edit_controller.edit_mode:
            return
        widget = self.dashboard.get_widget_at(self.edit_controller.selected_row, self.edit_controller.selected_col)
        if not widget:
            return
            
        entity_id = widget.entity_config.entity
        entity_type = widget.entity_type
    
        # debouncing
        current_time = time.time()
        if entity_id in self.last_toggle_time:
            time_since_last_toggle = current_time - self.last_toggle_time[entity_id]            
            if entity_type == 'light' and time_since_last_toggle < 0.5:
                return
            elif time_since_last_toggle < 0.2:
                return
        
        self.last_toggle_time[entity_id] = current_time
        
        if entity_type != 'light':
            success = await widget.toggle_entity()
            if success:
                self.notify(f"{entity_id} toggled!", severity="information")
            else:
                self.notify(f"Cannot toggle {entity_id}", severity="warning")
            return
            
    
    async def on_unmount(self) -> None:
        # clean up HTTP client when app shuts down
        if self.ha_client:
            await self.ha_client.close()
