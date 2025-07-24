import asyncio
import os
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from typing import Optional
from ha_client import HomeAssistantClient
from config_manager import ConfigManager, EntityConfig
from entity_widget import EntityWidget
from components.entity_browser import EntityBrowserScreen
from components.grid_dashboard import GridDashboard


class MainTUI(App):
    # main TUI app with interactive config
    CSS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "styles", "main.css")
    
    BINDINGS = [
        Binding("space", "toggle_entity", "Toggle"),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "edit_mode", "Edit Mode"),
        Binding("a", "add_entity", "Add Entity"),
        Binding("delete", "remove_entity", "Remove"),
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
        self.edit_mode = False
        self.selected_row = 0
        self.selected_col = 0
    
    def compose(self) -> ComposeResult:
        yield Header()
        self.dashboard = GridDashboard(3, 3)  # Will be updated from config
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
            self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            self.update_status_bar()
            
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
            widget = EntityWidget(entity_config, self.ha_client)
            self.dashboard.add_entity_widget(widget, entity_config.row, entity_config.col)
            await widget.refresh_state()
    
    async def auto_refresh(self) -> None:
        # refresh all entity states automatically
        for widget in self.dashboard.widgets_grid.values():
            await widget.refresh_state()
    
    def update_status_bar(self) -> None:
        # update status bar with current mode info
        status = self.query_one("#status-bar", Static)
        if self.edit_mode:
            status.update(f"Mode: EDIT | Position: [{self.selected_row},{self.selected_col}] | 'a' Add | 'del' Remove | arrows Move")
        else:
            widget = self.dashboard.get_widget_at(self.selected_row, self.selected_col)
            if widget:
                entity_name = widget.friendly_name
                status.update(f"Mode: View | Position: [{self.selected_row},{self.selected_col}] | Selected: {entity_name} | SPACE: Toggle")
            else:
                status.update(f"Mode: View | Position: [{self.selected_row},{self.selected_col}] | Empty Cell | Press 'e' for Edit Mode")
    
    def action_edit_mode(self) -> None:
        # toggle edit mode on/off
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self.dashboard.set_selected_position(self.selected_row, self.selected_col)
        else:
            self.dashboard.set_selected_position(-1, -1)  # clear selection
        self.update_status_bar()
        self.notify(f"Edit mode: {'ON' if self.edit_mode else 'OFF'}", severity="information")
    
    def action_exit_edit(self) -> None:
        # exit edit mode
        if self.edit_mode:
            self.edit_mode = False
            self.dashboard.set_selected_position(-1, -1)
            self.update_status_bar()
    
    async def action_add_entity(self) -> None:
        # open entity browser to add new entity
        if not self.edit_mode:
            self.notify("Enter edit mode first (press 'e')", severity="warning")
            return
        
        # get positions that are already taken
        occupied = set(self.dashboard.widgets_grid.keys())
        
        # open the entity browser
        browser = EntityBrowserScreen(self.ha_client, occupied)
        result = await self.push_screen_wait(browser)
        
        if result:
            try:
                # add to config
                self.config_manager.add_entity(result["entity"], result["row"], result["col"])
                
                # create widget and add to dashboard
                entity_config = EntityConfig(result["entity"], [result["row"], result["col"]])
                widget = EntityWidget(entity_config, self.ha_client)
                self.dashboard.add_entity_widget(widget, result["row"], result["col"])
                await widget.refresh_state()
                
                self.notify(f"Added {result['entity']} at ({result['row']}, {result['col']})", severity="information")
                
            except Exception as e:
                self.notify(f"Error adding entity: {e}", severity="error")
    
    async def action_remove_entity(self) -> None:
        # remove entity at current selected position
        if not self.edit_mode:
            return
        
        widget = self.dashboard.get_widget_at(self.selected_row, self.selected_col)
        if widget:
            entity_id = widget.entity_config.entity
            
            # remove from config and dashboard
            self.config_manager.remove_entity(entity_id)
            self.dashboard.remove_entity_widget(self.selected_row, self.selected_col)
            
            self.notify(f"Removed {entity_id}", severity="information")
    
    def action_move_up(self) -> None:
        # Move selection up or move entity up in edit mode
        if self.edit_mode:
            if self.selected_row > 0:
                new_row = self.selected_row - 1
                if self._try_move_entity(new_row, self.selected_col):
                    self.selected_row = new_row
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
        else:
            # In view mode, navigate between positions
            if self.selected_row > 0:
                self.selected_row -= 1
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def action_move_down(self) -> None:
        # Move selection down or move entity down in edit mode
        if self.edit_mode:
            if self.selected_row < self.dashboard.rows - 1:
                new_row = self.selected_row + 1
                if self._try_move_entity(new_row, self.selected_col):
                    self.selected_row = new_row
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
        else:
            # In view mode, navigate between positions
            if self.selected_row < self.dashboard.rows - 1:
                self.selected_row += 1
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def action_move_left(self) -> None:
        # Move selection left or move entity left in edit mode
        if self.edit_mode:
            if self.selected_col > 0:
                new_col = self.selected_col - 1
                if self._try_move_entity(self.selected_row, new_col):
                    self.selected_col = new_col
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
        else:
            # In view mode, navigate between positions
            if self.selected_col > 0:
                self.selected_col -= 1
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def action_move_right(self) -> None:
        # Move selection right or move entity right in edit mode
        if self.edit_mode:
            if self.selected_col < self.dashboard.cols - 1:
                new_col = self.selected_col + 1
                if self._try_move_entity(self.selected_row, new_col):
                    self.selected_col = new_col
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
        else:
            # In view mode, navigate between positions
            if self.selected_col < self.dashboard.cols - 1:
                self.selected_col += 1
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def _try_move_entity(self, new_row: int, new_col: int) -> bool:
        # try to move entity to new position
        current_widget = self.dashboard.get_widget_at(self.selected_row, self.selected_col)
        if not current_widget:
            return True  # just move selection
        
        # check if target spot is empty
        if self.dashboard.get_widget_at(new_row, new_col) is not None:
            self.notify(f"Position ({new_row}, {new_col}) is occupied", severity="warning")
            return False
        
        # move the entity
        entity_id = current_widget.entity_config.entity
        if self.config_manager.move_entity(entity_id, new_row, new_col):
            # update widget position
            self.dashboard.remove_entity_widget(self.selected_row, self.selected_col)
            current_widget.entity_config.row = new_row
            current_widget.entity_config.col = new_col
            self.dashboard.add_entity_widget(current_widget, new_row, new_col)
            
            self.notify(f"Moved {entity_id} to ({new_row}, {new_col})", severity="information")
            return True
        
        return False
    
    async def action_toggle_entity(self) -> None:
        # toggle entity at current position
        if self.edit_mode:
            return  # don't toggle in edit mode
        
        widget = self.dashboard.get_widget_at(self.selected_row, self.selected_col)
        if widget:
            success = await widget.toggle_entity()
            if success:
                self.notify("Entity toggled!", severity="information")
            else:
                self.notify("Cannot toggle this entity", severity="warning")
    
    async def action_refresh(self) -> None:
        # manually refresh all entities
        await self.auto_refresh()
        self.notify("Refreshed all entities!", severity="information")
    
    async def on_unmount(self) -> None:
        # clean up HTTP client when app shuts down
        if self.ha_client:
            await self.ha_client.close()
