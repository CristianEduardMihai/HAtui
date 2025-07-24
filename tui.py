import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Vertical, Horizontal
from textual.widgets import Header, Footer, Static, Button, Input, Select, Label
from textual.reactive import reactive
from textual.binding import Binding
from textual.screen import ModalScreen
from typing import List, Optional, Dict
from ha_client import HomeAssistantClient
from config_manager import ConfigManager, EntityConfig
from entity_widget import EntityWidget


class EntityBrowserScreen(ModalScreen):
    # modal popup for browsing and picking HA entities
    
    def __init__(self, ha_client: HomeAssistantClient, occupied_positions: set):
        super().__init__()
        self.ha_client = ha_client
        self.occupied_positions = occupied_positions
        self.entities = []
        self.selected_entity = None
        self.selected_row = 0
        self.selected_col = 0
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Add New Entity", id="browser-title")
            yield Static("Loading entities...", id="entity-list")
            yield Label("Select Position:")
            with Horizontal():
                yield Label("Row:")
                yield Input(placeholder="0", id="row-input")
                yield Label("Col:")
                yield Input(placeholder="0", id="col-input")
            yield Label("Entity Number:")
            yield Input(placeholder="1", id="entity-input")
            with Horizontal():
                yield Button("Add Entity", variant="primary", id="add-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")
    
    async def on_mount(self) -> None:
        await self.load_entities()
    
    async def load_entities(self) -> None:
        # load all available entities from HA
        try:
            all_entities = await self.ha_client.get_all_entities()
            
            # filter to useful types and sort them nicely
            useful_domains = ['light', 'switch', 'sensor', 'binary_sensor', 'climate', 'script', 'automation', 'input_boolean']
            filtered_entities = [
                entity for entity in all_entities 
                if entity['entity_id'].split('.')[0] in useful_domains
            ]
            
            # sort by domain then by friendly name
            self.entities = sorted(filtered_entities, 
                                 key=lambda x: (x['entity_id'].split('.')[0], 
                                               x.get('attributes', {}).get('friendly_name', x['entity_id'])))
            
            entity_list = self.query_one("#entity-list", Static)
            if self.entities:
                entity_text = "\n".join([
                    f"{i+1:2d}. {entity.get('attributes', {}).get('friendly_name', entity['entity_id'])} ({entity['entity_id']})"
                    for i, entity in enumerate(self.entities[:20])  # show first 20
                ])
                entity_list.update(f"Select entity number (1-{min(len(self.entities), 20)}):\n{entity_text}")
            else:
                entity_list.update("No entities found")
            
        except Exception as e:
            entity_list = self.query_one("#entity-list", Static)
            entity_list.update(f"Error loading entities: {e}")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "add-btn":
            self.add_selected_entity()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "row-input" or event.input.id == "col-input":
            self.add_selected_entity()
    
    def add_selected_entity(self) -> None:
        # add the picked entity to the dashboard
        try:
            # get which entity they picked
            entity_input = self.query_one("#entity-input", Input)
            try:
                entity_num = int(entity_input.value or "1") - 1
                if entity_num < 0 or entity_num >= len(self.entities):
                    self.notify("Invalid entity number", severity="error")
                    return
            except ValueError:
                self.notify("Invalid entity number", severity="error")
                return
            
            # get where they want to put it
            row_input = self.query_one("#row-input", Input)
            col_input = self.query_one("#col-input", Input)
            
            try:
                row = int(row_input.value or "0")
                col = int(col_input.value or "0")
            except ValueError:
                self.notify("Invalid row/col values", severity="error")
                return
            
            # make sure spot isn't taken
            if (row, col) in self.occupied_positions:
                self.notify(f"Position ({row}, {col}) is already occupied", severity="error")
                return
            
            # grab the entity and send it back
            selected_entity = self.entities[entity_num]
            entity_id = selected_entity['entity_id']
            
            result = {"entity": entity_id, "row": row, "col": col}
            self.dismiss(result)
                
        except Exception as e:
            self.notify(f"Error adding entity: {e}", severity="error")


class GridDashboard(Container):
    # grid container for showing entities in dashboard layout
    
    def __init__(self, rows: int, cols: int):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.widgets_grid: Dict[tuple, EntityWidget] = {}
        self.selected_position: Optional[tuple] = None
    
    def compose(self) -> ComposeResult:
        with Grid(id="entity-grid"):
            # create all grid positions initially as empty, but store them for later access
            for row in range(self.rows):
                for col in range(self.cols):
                    yield Static(f"[{row},{col}]\n\nEmpty\nPress E to edit", 
                               id=f"cell-{row}-{col}", 
                               classes="empty-cell")
    
    def add_entity_widget(self, widget: EntityWidget, row: int, col: int) -> None:
        # replace the empty cell at this position with the entity widget
        grid = self.query_one("#entity-grid", Grid)
        
        # find and remove the empty cell at this position
        try:
            empty_cell = self.query_one(f"#cell-{row}-{col}")
            cell_index = list(grid.children).index(empty_cell)
            empty_cell.remove()
        except:
            # if no empty cell, just append
            cell_index = len(grid.children)
        
        # add the entity widget and track it
        self.widgets_grid[(row, col)] = widget
        
        # insert at the correct position in the grid
        if cell_index < len(grid.children):
            grid.mount(widget, before=list(grid.children)[cell_index])
        else:
            grid.mount(widget)
    
    def remove_entity_widget(self, row: int, col: int) -> None:
        # replace entity widget with empty cell
        if (row, col) not in self.widgets_grid:
            return
            
        grid = self.query_one("#entity-grid", Grid)
        widget = self.widgets_grid.pop((row, col))
        
        # find the position of the widget to remove
        try:
            cell_index = list(grid.children).index(widget)
            widget.remove()
        except:
            cell_index = len(grid.children)
        
        # add back empty cell at the same position
        empty_cell = Static(f"[{row},{col}]\n\nEmpty\nPress E to edit", 
                          id=f"cell-{row}-{col}", 
                          classes="empty-cell")
        
        if cell_index < len(grid.children):
            grid.mount(empty_cell, before=list(grid.children)[cell_index])
        else:
            grid.mount(empty_cell)
    
    def set_selected_position(self, row: int, col: int) -> None:
        # highlight a specific grid position
        # clear old selection first
        if self.selected_position:
            old_row, old_col = self.selected_position
            if (old_row, old_col) in self.widgets_grid:
                self.widgets_grid[(old_row, old_col)].set_selected(False)
        
        # set new selection
        self.selected_position = (row, col)
        if (row, col) in self.widgets_grid:
            self.widgets_grid[(row, col)].set_selected(True)
    
    def get_widget_at(self, row: int, col: int) -> Optional[EntityWidget]:
        # get whatever widget is at this position
        return self.widgets_grid.get((row, col))


class MainTUI(App):
    # main TUI app with interactive config
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #entity-grid {
        grid-size: 3 3;
        grid-gutter: 1 1;
        margin: 2;
        height: auto;
    }
    
    .empty-cell {
        border: dashed $primary;
        text-align: center;
        height: 6;
        content-align: center middle;
        color: $text-muted;
    }
    
    EntityWidget {
        height: 6;
    }
    
    #status-bar {
        dock: bottom;
        height: 3;
        background: $panel;
        padding: 1;
    }
    
    /* Entity Browser Modal */
    EntityBrowserScreen {
        align: center middle;
    }
    
    EntityBrowserScreen > Container {
        background: $panel;
        border: thick $primary;
        width: 60;
        height: 20;
        padding: 2;
    }
    
    #browser-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    """
    
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
            status.update("Mode: View | Press 'e' for Edit Mode")
    
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
                entity_config = EntityConfig(result["entity"], result["row"], result["col"])
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
       # Move selection up or move entity up.
        if self.edit_mode:
            if self.selected_row > 0:
                new_row = self.selected_row - 1
                if self._try_move_entity(new_row, self.selected_col):
                    self.selected_row = new_row
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def action_move_down(self) -> None:
       # Move selection down or move entity down.
        if self.edit_mode:
            if self.selected_row < self.dashboard.rows - 1:
                new_row = self.selected_row + 1
                if self._try_move_entity(new_row, self.selected_col):
                    self.selected_row = new_row
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def action_move_left(self) -> None:
       # Move selection left or move entity left.
        if self.edit_mode:
            if self.selected_col > 0:
                new_col = self.selected_col - 1
                if self._try_move_entity(self.selected_row, new_col):
                    self.selected_col = new_col
                self.dashboard.set_selected_position(self.selected_row, self.selected_col)
                self.update_status_bar()
    
    def action_move_right(self) -> None:
       # Move selection right or move entity right.
        if self.edit_mode:
            if self.selected_col < self.dashboard.cols - 1:
                new_col = self.selected_col + 1
                if self._try_move_entity(self.selected_row, new_col):
                    self.selected_col = new_col
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


if __name__ == "__main__":
    app = MainTUI()
    app.title = "Home Assistant TUI"
    app.run()
