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
        self.edit_mode = False
        self.selected_row = 0
        self.selected_col = 0
        self.holding_entity = None
        self.holding_from_pos = None
    
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
            if self.holding_entity:
                entity_name = self.holding_entity.friendly_name
                status.update(f"Mode: EDIT | HOLDING: {entity_name} | Position: [{self.selected_row},{self.selected_col}] | arrows Move | ENTER Drop")
            else:
                widget = self.dashboard.get_widget_at(self.selected_row, self.selected_col)
                if widget:
                    entity_name = widget.friendly_name
                    status.update(f"Mode: EDIT | Position: [{self.selected_row},{self.selected_col}] | Selected: {entity_name} | ENTER Pick | 'a' Add | 'del' Remove")
                else:
                    status.update(f"Mode: EDIT | Position: [{self.selected_row},{self.selected_col}] | Empty Cell | 'a' Add | arrows Move")
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
            # If holding an entity, clear the holding state and ghost
            if self.holding_entity:
                self.dashboard.set_ghost_entity(None)
                self.holding_entity.set_being_moved(False)
                self.holding_entity = None
                self.holding_from_pos = None
            
            self.edit_mode = False
            self.dashboard.set_selected_position(-1, -1)  # clear all selectio
            self.update_status_bar()
    
    async def action_pick_drop_entity(self) -> None:
        # pick up or drop an entity for moving
        if not self.edit_mode:
            return
        
        if self.holding_entity:
            # Drop the entity at current position
            await self._drop_entity_at(self.selected_row, self.selected_col)
        else:
            # Pick up entity at current position
            widget = self.dashboard.get_widget_at(self.selected_row, self.selected_col)
            if widget:
                self.holding_entity = widget
                self.holding_from_pos = (self.selected_row, self.selected_col)
                # Set the original entity as "being moved" (dimmed)
                widget.set_being_moved(True)
                # Show ghost at cursor position
                self.dashboard.set_ghost_entity(widget, self.selected_row, self.selected_col)
                # Clear normal selection since we're now holding
                self.dashboard.set_selected_position(-1, -1)
                self.notify(f"Picked up {widget.friendly_name}", severity="information")
                self.update_status_bar()
    
    async def _drop_entity_at(self, row: int, col: int) -> None:
        # drop the held entity at specified position
        if not self.holding_entity:
            return
        
        # Check if trying to drop at same position
        if (row, col) == self.holding_from_pos:
            # Just clear being moved state and stay in place, clear ghost
            self.dashboard.set_ghost_entity(None)
            self.holding_entity.set_being_moved(False)
            self.holding_entity = None
            self.holding_from_pos = None
            # Restore normal selection
            self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            self.notify("Entity dropped at original position", severity="information")
            self.update_status_bar()
            return
        
        # Check if target position is occupied (ignore ghost)
        target_widget = self.dashboard.get_widget_at(row, col)
        if target_widget is not None and target_widget != self.holding_entity:
            self.notify(f"Position ({row}, {col}) is occupied", severity="warning")
            return
        
        # Update config with new position
        entity_id = self.holding_entity.entity_config.entity
        
        try:
            # Update config first
            if self.config_manager.move_entity(entity_id, row, col):
                # Store references for async operation
                old_row, old_col = self.holding_from_pos
                moved_entity = self.holding_entity
                
                # Clear ghost entity first
                self.dashboard.set_ghost_entity(None)
                
                # Let UI settle before continuing
                await asyncio.sleep(0.1)
                
                # Remove from old position in grid
                self.dashboard.remove_entity_widget(old_row, old_col)
                
                # Update widget's internal position
                moved_entity.entity_config.row = row
                moved_entity.entity_config.col = col
                
                # Clear being moved state
                moved_entity.set_being_moved(False)
                
                # Clear holding references
                self.holding_entity = None
                self.holding_from_pos = None
                
                # Let UI settle again
                await asyncio.sleep(0.1)
                
                # Add to new position in grid
                self.dashboard.add_entity_widget(moved_entity, row, col)
                
                # Restore normal selection
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                
                self.notify(f"Moved {entity_id} to ({row}, {col})", severity="information")
            else:
                # Config update failed, clear ghost and being moved state
                self.dashboard.set_ghost_entity(None)
                self.holding_entity.set_being_moved(False)
                self.holding_entity = None
                self.holding_from_pos = None
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.notify("Failed to update config", severity="error")
                
        except Exception as e:
            # Something went wrong, clear everything and restore to original state
            # Aka dont mess the config
            self.dashboard.set_ghost_entity(None)
            self.holding_entity.set_being_moved(False)
            self.holding_entity = None
            self.holding_from_pos = None
            self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            self.notify(f"Error moving entity: {e}", severity="error")
        
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
        # Move selection up
        if self.selected_row > 0:
            self.selected_row -= 1
            if not self.holding_entity:
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def action_move_down(self) -> None:
        # Move selection down
        if self.selected_row < self.dashboard.rows - 1:
            self.selected_row += 1
            if not self.holding_entity:
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def action_move_left(self) -> None:
        # Move selection left
        if self.selected_col > 0:
            self.selected_col -= 1
            if not self.holding_entity:
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def action_move_right(self) -> None:
        # Move selection right
        if self.selected_col < self.dashboard.cols - 1:
            self.selected_col += 1
            if not self.holding_entity:
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
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
