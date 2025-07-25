from textual.containers import Container, Grid
from textual.widgets import Static
from textual.app import ComposeResult
from typing import Dict, Optional
from entity_widget import EntityWidget


class GridDashboard(Container):
    # grid container for showing entities in dashboard layout
    def __init__(self, rows: int, cols: int):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.widgets_grid: Dict[tuple, EntityWidget] = {}
        self.selected_position: Optional[tuple] = None
        self.ghost_entity: Optional[EntityWidget] = None  # entity moving
        self.ghost_position: Optional[tuple] = None  # position of ghost/moving entity
    
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
                # clear entity widget selection
                self.widgets_grid[(old_row, old_col)].set_selected(False)
            else:
                # clear empty cell selection
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
        # get whatever widget is at this position
        return self.widgets_grid.get((row, col))
    
    def set_ghost_entity(self, original_entity: Optional[EntityWidget], row: int = -1, col: int = -1) -> None:
        # Show a "ghost" entity at the specified position for moving preview
        # clear any existing ghost first
        if self.ghost_entity and self.ghost_position:
            old_row, old_col = self.ghost_position
            try:
                self.ghost_entity.remove()
                # Restore empty cell so we dont cannibalize the grid
                if (old_row, old_col) not in self.widgets_grid:
                    grid = self.query_one("#entity-grid", Grid)
                    empty_cell = Static(f"[{old_row},{old_col}]\n\nEmpty\nPress E to edit", 
                                      id=f"cell-{old_row}-{old_col}", 
                                      classes="empty-cell")
                    # Calculate position and insert
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
        
        # Show new ghost if requested
        if original_entity and row >= 0 and col >= 0:
            # Only show ghost in empty cells
            if (row, col) not in self.widgets_grid:
                try:
                    # Remove empty cell temporarily
                    empty_cell = self.query_one(f"#cell-{row}-{col}")
                    grid = self.query_one("#entity-grid", Grid)
                    cell_index = list(grid.children).index(empty_cell)
                    empty_cell.remove()
                    
                    # Create a ghost display widget
                    ghost_widget = Static(f"{original_entity.friendly_name}\nState: {original_entity.state}\n(Moving...)", 
                                        classes="ghost-entity")
                    ghost_widget.styles.border = ("heavy", "magenta")
                    ghost_widget.styles.height = 6
                    
                    # Insert ghost at correct position
                    if cell_index < len(grid.children):
                        grid.mount(ghost_widget, before=list(grid.children)[cell_index])
                    else:
                        grid.mount(ghost_widget)
                    
                    # Track the ghost
                    self.ghost_entity = ghost_widget
                    self.ghost_position = (row, col)
                except:
                    pass
