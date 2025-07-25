import asyncio
import os
from textual.app import App, ComposeResult
from textual.widgets import Header, Static
from textual.binding import Binding
from textual.events import Key
from typing import Optional
from ha_client import HomeAssistantClient
from config_manager import ConfigManager, EntityConfig
from entity_widget import EntityWidget
from components.entity_browser import EntityBrowserScreen
from components.grid_dashboard import GridDashboard
from components.edit_controller import EditController
from components.name_editor import NameEditorScreen


class MainTUI(App):
    # main TUI app with interactive config
    CSS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "styles", "main.css")
    
    # All bindings
    BINDINGS = [
        # Base bindings
        Binding("up", "move_up", "↑"),
        Binding("down", "move_down", "↓"), 
        Binding("left", "move_left", "←"),
        Binding("right", "move_right", "→"),
        Binding("q", "quit", "Quit"),
        # View mode bindings
        Binding("space", "handle_space_key", "Toggle"),
        Binding("ctrl+up", "brightness_up", "Bright+"),
        Binding("ctrl+down", "brightness_down", "Bright-"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "edit_mode", "Edit"),
        # Edit mode bindings  
        Binding("a", "add_entity", "Add"),
        Binding("delete", "remove_entity", "Remove"),
        Binding("enter", "pick_drop_entity", "Pick/Drop"),
        Binding("n", "edit_name", "Edit Name"),
        Binding("escape", "exit_edit", "Exit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ha_client = None
        self.dashboard = None
        self.edit_controller = EditController(self)
        self.last_toggle_time = {}
        # brightness staging
        self.staged_brightness = {}
        self.brightness_commit_scheduled = False
    
    def compose(self) -> ComposeResult:
        yield Header()
        self.dashboard = GridDashboard(3, 3)
        yield self.dashboard
        yield Static("Mode: View | Press 'e' for Edit Mode", id="status-bar")
    
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
    
    async def commit_staged_brightness(self) -> None:
        # send all staged brightness changes to HA
        for entity_id, brightness in self.staged_brightness.items():
            try:
                widget = None
                # Find the widget for this entity
                for w in self.dashboard.widgets_grid.values():
                    if w.entity_config.entity == entity_id:
                        widget = w
                        break
                
                if widget:
                    # Set the brightness in HA
                    await widget.set_brightness_direct(brightness)
                    self.notify(f"Set {entity_id} brightness to {brightness}%", severity="information")
            except Exception as e:
                self.notify(f"Failed to set brightness for {entity_id}: {e}", severity="error")
        
        # Clear staged changes
        self.staged_brightness.clear()
    
    def schedule_brightness_commit(self) -> None:
        # Only schedule if not already scheduled
        if not self.brightness_commit_scheduled:
            self.brightness_commit_scheduled = True
            # Schedule commit after 1 second of no brightness changes
            self.set_timer(1.0, self._brightness_commit_callback)
    
    async def _brightness_commit_callback(self) -> None:
        # Reset the flag and commit
        self.brightness_commit_scheduled = False
        await self.commit_staged_brightness()
    
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
        if not self.edit_controller.edit_mode:
            return
        await self.edit_controller.pick_drop_entity()
    
    def action_add_entity(self) -> None:
        if not self.edit_controller.edit_mode:
            return
        self.edit_controller.add_entity()
    
    async def action_remove_entity(self) -> None:
        if not self.edit_controller.edit_mode:
            return
        await self.edit_controller.remove_entity()
    
    def action_edit_name(self) -> None:
        if not self.edit_controller.edit_mode:
            return
        self.edit_controller.edit_entity_name()
    
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
            if time_since_last < 0.05:  # Faster debounce for staging
                return
                
        self.last_toggle_time[brightness_key] = current_time
        
        # Get current brightness
        if entity_id in self.staged_brightness:
            current_brightness = self.staged_brightness[entity_id]
        else:
            current_brightness = round(widget.attributes.get('brightness', 0) / 255 * 100)
        
        # Increase brightness by 5%
        new_brightness = min(100, current_brightness + 5)
        
        # Stage the brightness change
        self.staged_brightness[entity_id] = new_brightness
        
        # Update widget display immediately for visual feedback
        widget.staged_brightness = new_brightness
        widget.refresh_display()
        
        # Schedule commit after user stops pressing keys
        self.schedule_brightness_commit()
        
        # Update status bar
        self.update_status_with_brightness(widget)
    
    async def action_brightness_down(self) -> None:
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
            if time_since_last < 0.05:  # Faster debounce for staging
                return
                
        self.last_toggle_time[brightness_key] = current_time
        
        # Get current brightness
        if entity_id in self.staged_brightness:
            current_brightness = self.staged_brightness[entity_id]
        else:
            current_brightness = round(widget.attributes.get('brightness', 0) / 255 * 100)
        
        # Decrease brightness by 5%
        new_brightness = max(0, current_brightness - 5)
        
        # Stage the brightness change
        self.staged_brightness[entity_id] = new_brightness
        
        # Update widget display immediately for visual feedback
        widget.staged_brightness = new_brightness
        widget.refresh_display()
        
        # Schedule commit after user stops pressing keys
        self.schedule_brightness_commit()
        
        # Update status bar
        self.update_status_with_brightness(widget)
    
    async def action_refresh(self) -> None:
        # manually refresh all entities
        await self.auto_refresh()
        self.notify("Refreshed all entities!", severity="information")
    
    def update_status_with_brightness(self, widget) -> None:
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
        
        success = await widget.toggle_entity()
        if success:
            self.notify(f"{entity_id} toggled!", severity="information")
        else:
            self.notify(f"Cannot toggle {entity_id}", severity="warning")
            
    
    async def on_unmount(self) -> None:
        # clean up HTTP client when app shuts down
        if self.ha_client:
            await self.ha_client.close()
