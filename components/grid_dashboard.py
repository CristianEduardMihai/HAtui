from textual.containers import Container, Grid
from textual.widgets import Static
from textual.app import ComposeResult
from textual.events import Click
from typing import Dict, Optional
from entity_widget import EntityWidget


class GridDashboard(Container):
    # main grid layout for entities
    def __init__(self, rows: int, cols: int):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.widgets_grid: Dict[tuple, EntityWidget] = {}
        self.selected_position: Optional[tuple] = None
        self.ghost_entity: Optional[EntityWidget] = None  # entity moving
        self.ghost_position: Optional[tuple] = None  # position of ghost/moving entity
        self.is_edit_mode: bool = False
    
    def get_empty_cell_text(self, row: int, col: int) -> str:
        action_text = "Press A to add" if self.is_edit_mode else "Press E to edit"
        return f"[{row},{col}]\n\nEmpty\n{action_text}"
    
    def compose(self) -> ComposeResult:
        with Grid(id="entity-grid"):
            # fill grid with empty cells first
            for row in range(self.rows):
                for col in range(self.cols):
                    yield Static(self.get_empty_cell_text(row, col), 
                               id=f"cell-{row}-{col}", 
                               classes="empty-cell")
    
    def add_entity_widget(self, widget: EntityWidget, row: int, col: int) -> None:
        # swap out empty cell with the actual entity
        grid = self.query_one("#entity-grid", Grid)
        
        # remove empty cell
        try:
            empty_cell = self.query_one(f"#cell-{row}-{col}")
            cell_index = list(grid.children).index(empty_cell)
            empty_cell.remove()
        except:
            # no empty cell? just stick it at the end
            cell_index = len(grid.children)
        
        # track the widget and mount it
        self.widgets_grid[(row, col)] = widget
        
        # put it in the right spot
        if cell_index < len(grid.children):
            grid.mount(widget, before=list(grid.children)[cell_index])
        else:
            grid.mount(widget)
    
    def remove_entity_widget(self, row: int, col: int) -> None:
        # put empty cell back where entity was
        if (row, col) not in self.widgets_grid:
            return
            
        grid = self.query_one("#entity-grid", Grid)
        widget = self.widgets_grid.pop((row, col))
        
        # find where the widget is and yeet it
        try:
            cell_index = list(grid.children).index(widget)
            widget.remove()
        except:
            cell_index = len(grid.children)
        
        # put empty cell back
        empty_cell = Static(self.get_empty_cell_text(row, col), 
                          id=f"cell-{row}-{col}", 
                          classes="empty-cell")
        
        if cell_index < len(grid.children):
            grid.mount(empty_cell, before=list(grid.children)[cell_index])
        else:
            grid.mount(empty_cell)
    
    def set_selected_position(self, row: int, col: int) -> None:
        # highlight whatever's at this position
        # clear old highlight first
        if self.selected_position:
            old_row, old_col = self.selected_position
            if (old_row, old_col) in self.widgets_grid:
                # unhighlight entity
                self.widgets_grid[(old_row, old_col)].set_selected(False)
            else:
                # unhighlight empty cell
                try:
                    old_empty = self.query_one(f"#cell-{old_row}-{old_col}")
                    old_empty.styles.border = ("dashed", "white")
                except:
                    pass
        
        # set new selection
        self.selected_position = (row, col)
        if row >= 0 and col >= 0:  # valid position
            if (row, col) in self.widgets_grid:
                # highlight entity widget
                self.widgets_grid[(row, col)].set_selected(True)
            else:
                # highlight empty cell
                try:
                    empty_cell = self.query_one(f"#cell-{row}-{col}")
                    empty_cell.styles.border = ("heavy", "cyan")
                except:
                    pass
    
    def get_widget_at(self, row: int, col: int) -> Optional[EntityWidget]:
        # just grab whatever's at this spot
        return self.widgets_grid.get((row, col))
    
    def set_edit_mode(self, is_edit_mode: bool) -> None:
        if self.is_edit_mode != is_edit_mode:
            self.is_edit_mode = is_edit_mode
            for row in range(self.rows):
                for col in range(self.cols):
                    if (row, col) not in self.widgets_grid:
                        try:
                            empty_cell = self.query_one(f"#cell-{row}-{col}")
                            empty_cell.update(self.get_empty_cell_text(row, col))
                        except:
                            pass
    
    def set_ghost_entity(self, original_entity: Optional[EntityWidget], row: int = -1, col: int = -1) -> None:
        # show a "ghost" preview when moving entities around
        # clear old ghost first
        if self.ghost_entity and self.ghost_position:
            old_row, old_col = self.ghost_position
            try:
                self.ghost_entity.remove()
                # put empty cell back so we don't break the grid
                if (old_row, old_col) not in self.widgets_grid:
                    grid = self.query_one("#entity-grid", Grid)
                    empty_cell = Static(self.get_empty_cell_text(old_row, old_col), 
                                      id=f"cell-{old_row}-{old_col}", 
                                      classes="empty-cell")
                    # figure out where to put it
                    cell_index = old_row * self.cols + old_col
                    if cell_index < len(grid.children):
                        grid.mount(empty_cell, before=list(grid.children)[cell_index])
                    else:
                        grid.mount(empty_cell)
            except:
                pass
        
        # Reset ghost tracking
        self.ghost_entity = None
        self.ghost_position = None
        
        # show new ghost if we need to
        if original_entity and row >= 0 and col >= 0:
            # only show ghost in empty spots
            if (row, col) not in self.widgets_grid:
                try:
                    # yeet the empty cell temporarily
                    empty_cell = self.query_one(f"#cell-{row}-{col}")
                    grid = self.query_one("#entity-grid", Grid)
                    cell_index = list(grid.children).index(empty_cell)
                    empty_cell.remove()
                    
                    # Create a ghost display widget
                    ghost_widget = Static(f"{original_entity.friendly_name}\nState: {original_entity.state}\n(Moving...)", 
                                        classes="ghost-entity")
                    ghost_widget.styles.border = ("heavy", "magenta")
                    ghost_widget.styles.height = 6
                    
                    # put ghost in the right spot
                    if cell_index < len(grid.children):
                        grid.mount(ghost_widget, before=list(grid.children)[cell_index])
                    else:
                        grid.mount(ghost_widget)
                    
                    # track the ghost
                    self.ghost_entity = ghost_widget
                    self.ghost_position = (row, col)
                except:
                    pass
    
    def on_click(self, event: Click) -> None:
        # forward clicks to main app
        # Let the click bubble up to the main app for handling
        event.bubble = True
        event.stop()
        self.app.post_message(event)
