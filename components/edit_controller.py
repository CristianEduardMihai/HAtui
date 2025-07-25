import asyncio
from typing import Optional, TYPE_CHECKING
from textual.widgets import Static
from entity_widget import EntityWidget
from config_manager import ConfigManager, EntityConfig
from components.entity_browser import EntityBrowserScreen

if TYPE_CHECKING:
    from components.main_tui import MainTUI


class EditController:
    # Handles all edit mode functionality for the dashboard
    
    def __init__(self, app: 'MainTUI'):
        self.app = app
        self.edit_mode = False
        self.selected_row = 0
        self.selected_col = 0
        self.holding_entity: Optional[EntityWidget] = None
        self.holding_from_pos: Optional[tuple] = None
    
    def toggle_edit_mode(self) -> None:
        # Toggle edit mode on/off
        self.edit_mode = not self.edit_mode
        if self.edit_mode:
            self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
        else:
            self.app.dashboard.set_selected_position(-1, -1)  # clear selection
        
        self.update_status_bar()
        self.app.notify(f"Edit mode: {'ON' if self.edit_mode else 'OFF'}", severity="information")
    
    def exit_edit_mode(self) -> None:
        # Exit edit mode and clear any held entities
        if self.edit_mode:
            # If holding an entity, clear the holding state and ghost
            if self.holding_entity:
                self.app.dashboard.set_ghost_entity(None)
                self.holding_entity.set_being_moved(False)
                self.holding_entity = None
                self.holding_from_pos = None
            
            self.edit_mode = False
            self.app.dashboard.set_selected_position(-1, -1)  # clear all selection
            self.update_status_bar()
    
    async def pick_drop_entity(self) -> None:
        # Pick up/drop entity for moving
        if not self.edit_mode:
            return
        
        if self.holding_entity:
            # Drop the entity at current position
            await self._drop_entity_at(self.selected_row, self.selected_col)
        else:
            # Pick up entity at current position
            widget = self.app.dashboard.get_widget_at(self.selected_row, self.selected_col)
            if widget:
                self.holding_entity = widget
                self.holding_from_pos = (self.selected_row, self.selected_col)
                # Set the original entity as "being moved" (dimmed)
                widget.set_being_moved(True)
                # Show ghost at cursor position
                self.app.dashboard.set_ghost_entity(widget, self.selected_row, self.selected_col)
                # Clear normal selection since we're now holding
                self.app.dashboard.set_selected_position(-1, -1)
                self.app.notify(f"Picked up {widget.friendly_name}", severity="information")
                self.update_status_bar()
    
    async def _drop_entity_at(self, row: int, col: int) -> None:
        # Drop the held entity at specified position
        if not self.holding_entity:
            return
        
        # Check if trying to drop at same position
        if (row, col) == self.holding_from_pos:
            # Just clear being moved state and stay in place, clear ghost
            self.app.dashboard.set_ghost_entity(None)
            self.holding_entity.set_being_moved(False)
            self.holding_entity = None
            self.holding_from_pos = None
            # Restore normal selection
            self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
            self.app.notify("Entity dropped at original position", severity="information")
            self.update_status_bar()
            return
        
        # Check if target position is occupied (ignore ghost)
        target_widget = self.app.dashboard.get_widget_at(row, col)
        if target_widget is not None and target_widget != self.holding_entity:
            self.app.notify(f"Position ({row}, {col}) is occupied", severity="warning")
            return
        
        # Update config with new position
        entity_id = self.holding_entity.entity_config.entity
        
        try:
            # Update config first
            if self.app.config_manager.move_entity(entity_id, row, col):
                # Store references for async operation
                old_row, old_col = self.holding_from_pos
                moved_entity = self.holding_entity
                
                # Clear ghost entity first
                self.app.dashboard.set_ghost_entity(None)
                
                # Let UI settle before continuing
                await asyncio.sleep(0.1)
                
                # Remove from old position in grid
                self.app.dashboard.remove_entity_widget(old_row, old_col)
                
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
                self.app.dashboard.add_entity_widget(moved_entity, row, col)
                
                # Restore normal selection
                self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
                
                self.app.notify(f"Moved {entity_id} to ({row}, {col})", severity="information")
            else:
                # Config update failed, clear ghost and being moved state
                self.app.dashboard.set_ghost_entity(None)
                self.holding_entity.set_being_moved(False)
                self.holding_entity = None
                self.holding_from_pos = None
                self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.app.notify("Failed to update config", severity="error")
                
        except Exception as e:
            # Something went wrong, clear everything and restore to original state
            self.app.dashboard.set_ghost_entity(None)
            self.holding_entity.set_being_moved(False)
            self.holding_entity = None
            self.holding_from_pos = None
            self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
            self.app.notify(f"Error moving entity: {e}", severity="error")
        
        self.update_status_bar()
    
    def add_entity(self) -> None:
        # open entity browser to add new entity
        if not self.edit_mode:
            self.app.notify("Enter edit mode first (press 'e')", severity="warning")
            return
        
        # get positions that are already taken
        occupied = set(self.app.dashboard.widgets_grid.keys())
        
        # Run the entity browser in a worker context
        self.app.run_worker(self._run_entity_browser(occupied))
    
    async def _run_entity_browser(self, occupied: set) -> None:
        # run the entity browser
        browser = EntityBrowserScreen(self.app.ha_client, occupied, self.selected_row, self.selected_col)
        result = await self.app.push_screen_wait(browser)
        
        if result:
            try:
                # add to config
                self.app.config_manager.add_entity(result["entity"], result["row"], result["col"])
                
                # create widget and add to dashboard
                entity_config = EntityConfig(result["entity"], [result["row"], result["col"]])
                widget = EntityWidget(entity_config, self.app.ha_client)
                self.app.dashboard.add_entity_widget(widget, result["row"], result["col"])
                await widget.refresh_state()
                
                self.app.notify(f"Added {result['entity']} at ({result['row']}, {result['col']})", severity="information")
                
            except Exception as e:
                self.app.notify(f"Error adding entity: {e}", severity="error")
    
    async def remove_entity(self) -> None:
        # Remove entity at current selected position
        if not self.edit_mode:
            return
        
        widget = self.app.dashboard.get_widget_at(self.selected_row, self.selected_col)
        if widget:
            entity_id = widget.entity_config.entity
            
            try:
                # remove from config and dashboard
                self.app.config_manager.remove_entity(entity_id)
                self.app.dashboard.remove_entity_widget(self.selected_row, self.selected_col)
                
                self.app.notify(f"Removed {entity_id}", severity="information")
            except Exception as e:
                self.app.notify(f"Error removing entity: {e}", severity="error")
        else:
            self.app.notify("No entity at current position to remove", severity="warning")
    
    def move_up(self) -> None:
        # move selection up
        if self.selected_row > 0:
            self.selected_row -= 1
            if not self.holding_entity:
                self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.app.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def move_down(self) -> None:
        # move down
        if self.selected_row < self.app.dashboard.rows - 1:
            self.selected_row += 1
            if not self.holding_entity:
                self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.app.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def move_left(self) -> None:
        # move left
        if self.selected_col > 0:
            self.selected_col -= 1
            if not self.holding_entity:
                self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.app.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def move_right(self) -> None:
        # move right
        if self.selected_col < self.app.dashboard.cols - 1:
            self.selected_col += 1
            if not self.holding_entity:
                self.app.dashboard.set_selected_position(self.selected_row, self.selected_col)
            else:
                # Move ghost entity to show where it will be dropped
                self.app.dashboard.set_ghost_entity(self.holding_entity, self.selected_row, self.selected_col)
            self.update_status_bar()
    
    def update_status_bar(self) -> None:
        # update status bar with current edit mode info and all relevant commands
        status = self.app.query_one("#status-bar", Static)
        if self.edit_mode:
            if self.holding_entity:
                entity_name = self.holding_entity.friendly_name
                status.update(f"[EDIT] Holding: {entity_name} | ↑↓←→: Move | Enter: Drop | Esc: Cancel")
            else:
                widget = self.app.dashboard.get_widget_at(self.selected_row, self.selected_col)
                if widget:
                    entity_name = widget.friendly_name
                    status.update(f"[EDIT] {entity_name} | ↑↓←→: Navigate | Enter: Pick | a: Add | Del: Remove | e: Exit Edit")
                else:
                    status.update(f"[EDIT] Empty cell | ↑↓←→: Navigate | a: Add Entity | e: Exit Edit")
        else:
            widget = self.app.dashboard.get_widget_at(self.selected_row, self.selected_col)
            if widget:
                entity_name = widget.friendly_name
                
                # view mode
                commands = ["↑↓←→: Navigate", "Space: Toggle"]
                
                if widget.entity_type == 'light' and widget.supports_brightness():
                    if widget.state == 'on' and 'brightness' in widget.attributes:
                        brightness_pct = round(widget.attributes.get('brightness', 0) / 255 * 100)
                        commands.append(f"Ctrl+↑↓: Brightness ({brightness_pct}%)")
                    else:
                        commands.append("Ctrl+↑↓: Brightness")
                
                # general commands
                commands.extend(["r: Refresh", "e: Edit Mode", "q: Quit"])
                
                status.update(f"[VIEW] {entity_name} | {' | '.join(commands)}")
            else:
                status.update(f"[VIEW] Empty cell | ↑↓←→: Navigate | r: Refresh | e: Edit Mode | q: Quit")
