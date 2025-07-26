import os
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, ListView, ListItem, Label, Input
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
from textual.events import Key
from typing import Optional, Callable
from config_manager import ConfigManager, DashboardConfig


class DashboardManagerScreen(ModalScreen):
    CSS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "styles", "dashboard_manager.css")
    
    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
        Binding("up", "cursor_up", "↑"),
        Binding("down", "cursor_down", "↓"),
        Binding("ctrl+n", "new_dashboard", "New"),
        Binding("delete", "delete_dashboard", "Delete"),
        Binding("f2", "rename_dashboard", "Rename"),
        Binding("ctrl+up", "move_dashboard_up", "Move Up"),
        Binding("ctrl+down", "move_dashboard_down", "Move Down"),
        Binding("enter", "confirm_action", "Confirm"),
    ]
    
    def __init__(self, config_manager: ConfigManager, on_change: Optional[Callable] = None):
        super().__init__()
        self.config_manager = config_manager
        self.on_change = on_change
        self.dashboards = []
        self.selected_index = 0
        self.mode = "view"  # view, new, rename
        self.input_widget = None
        self.list_widget = None
        
    def compose(self) -> ComposeResult:
        self.dashboards = self.config_manager.config.dashboards.copy()
        
        with Vertical(id="manager_container"):
            yield Static("Dashboard Manager", classes="title")
            
            # Dashboard list
            list_items = []
            for i, dashboard in enumerate(self.dashboards):
                current_marker = " [CURRENT]" if i == self.config_manager.config.current_dashboard else ""
                list_items.append(ListItem(Label(f"{dashboard.name}{current_marker}"), classes="dashboard_item"))
            
            self.list_widget = ListView(*list_items, id="dashboard_list")
            yield self.list_widget
            
            # Input area (initially hidden)
            with Vertical(id="input_container"):
                self.input_widget = Input(placeholder="Dashboard name...", id="dashboard_input")
                self.input_widget.display = False
                yield self.input_widget
            
            # Instructions
            yield Static(
                "In Dashboard Manager:\n" +
                "Navigate with ↑↓\n" +
                "Reorder with Ctrl+↑↓\n" +
                "Create with Ctrl+N\n" +
                "Rename with F2\n" +
                "Delete with Delete\n" +
                "Cancel with Escape",
                id="instructions"
            )
    
    def on_mount(self) -> None:
        # Set initial focus and selection.
        self.list_widget.index = self.config_manager.config.current_dashboard
        self.selected_index = self.config_manager.config.current_dashboard
        self.list_widget.focus()
    
    def action_cursor_up(self) -> None:
        # Move selection up.
        if self.mode == "view" and self.dashboards:
            self.selected_index = max(0, self.selected_index - 1)
            self.list_widget.index = self.selected_index
    
    def action_cursor_down(self) -> None:
        # Move selection down.
        if self.mode == "view" and self.dashboards:
            self.selected_index = min(len(self.dashboards) - 1, self.selected_index + 1)
            self.list_widget.index = self.selected_index
    
    def action_new_dashboard(self) -> None:
        # Start creating a new dashboard.
        if self.mode != "view":
            return
            
        self.mode = "new"
        self.input_widget.display = True
        self.input_widget.value = ""
        self.input_widget.placeholder = "Enter new dashboard name..."
        self.input_widget.focus()
    
    def action_rename_dashboard(self) -> None:
        # Start renaming the selected dashboard.
        if self.mode != "view" or not self.dashboards:
            return
            
        self.mode = "rename"
        self.input_widget.display = True
        self.input_widget.value = self.dashboards[self.selected_index].name
        self.input_widget.placeholder = "Enter new name..."
        self.input_widget.focus()
        # Select all text for easy editing by setting selection
        self.call_later(self._select_all_text)
    
    def _select_all_text(self) -> None:
        # Helper method to select all text in the input widget.
        if self.input_widget and self.input_widget.value:
            # Set cursor to end and select all
            self.input_widget.cursor_position = len(self.input_widget.value)
            # Create selection from start to end
            self.input_widget.selection = (0, len(self.input_widget.value))
    
    def action_delete_dashboard(self) -> None:
        # Delete the selected dashboard.
        if self.mode != "view" or not self.dashboards or len(self.dashboards) <= 1:
            return # if 1 dashboard, dont delete
        
        # Remove the dashboard
        deleted_dashboard = self.dashboards.pop(self.selected_index)
        
        # Adjust current dashboard index if needed
        current_idx = self.config_manager.config.current_dashboard
        if self.selected_index == current_idx:
            # Deleted current dashboard, move to previous or 0
            new_current = max(0, current_idx - 1)
            self.config_manager.config.current_dashboard = new_current
        elif self.selected_index < current_idx:
            # Deleted dashboard before current, adjust index
            self.config_manager.config.current_dashboard = current_idx - 1
        
        # Update config
        self.config_manager.config.dashboards = self.dashboards
        self.config_manager.save_config()
        
        # Adjust selection
        if self.selected_index >= len(self.dashboards):
            self.selected_index = len(self.dashboards) - 1
        
        # Refresh the list
        self._refresh_dashboard_list()
        
        # Notify parent
        if self.on_change:
            self.on_change()
    
    def action_move_dashboard_up(self) -> None:
        # Move the selected dashboard up in the list.
        if self.mode != "view" or not self.dashboards or self.selected_index <= 0:
            return
        
        # Swap dashboards
        current_idx = self.config_manager.config.current_dashboard
        
        # If moving current dashboard, update current index
        if self.selected_index == current_idx:
            self.config_manager.config.current_dashboard = current_idx - 1
        elif self.selected_index - 1 == current_idx:
            self.config_manager.config.current_dashboard = current_idx + 1
        
        # Swap the dashboards
        self.dashboards[self.selected_index], self.dashboards[self.selected_index - 1] = \
            self.dashboards[self.selected_index - 1], self.dashboards[self.selected_index]
        
        # Update selection
        self.selected_index -= 1
        
        # Update config and refresh
        self.config_manager.config.dashboards = self.dashboards
        self.config_manager.save_config()
        self._refresh_dashboard_list()
        
        if self.on_change:
            self.on_change()
    
    def action_move_dashboard_down(self) -> None:
        # Move the selected dashboard down in the list.
        if self.mode != "view" or not self.dashboards or self.selected_index >= len(self.dashboards) - 1:
            return
        
        # Swap dashboards
        current_idx = self.config_manager.config.current_dashboard
        
        # If moving current dashboard, update current index
        if self.selected_index == current_idx:
            self.config_manager.config.current_dashboard = current_idx + 1
        elif self.selected_index + 1 == current_idx:
            self.config_manager.config.current_dashboard = current_idx - 1
        
        # Swap the dashboards
        self.dashboards[self.selected_index], self.dashboards[self.selected_index + 1] = \
            self.dashboards[self.selected_index + 1], self.dashboards[self.selected_index]
        
        # Update selection
        self.selected_index += 1
        
        # Update config and refresh
        self.config_manager.config.dashboards = self.dashboards
        self.config_manager.save_config()
        self._refresh_dashboard_list()
        
        if self.on_change:
            self.on_change()
    
    def action_confirm_action(self) -> None:
        # Confirm the current action (new or rename).
        if self.mode == "new":
            name = self.input_widget.value.strip()
            if name:
                # Create new dashboard
                new_dashboard = DashboardConfig(
                    name=name,
                    rows=3,
                    cols=3, 
                    refresh_interval=5,
                    entities=[]
                )
                self.dashboards.append(new_dashboard)
                self.config_manager.config.dashboards = self.dashboards
                self.config_manager.save_config()
                
                # Select the new dashboard
                self.selected_index = len(self.dashboards) - 1
                self._refresh_dashboard_list()
                
                # Switch to the new dashboard
                self.config_manager.config.current_dashboard = self.selected_index
                self.config_manager.save_config()
                
                if self.on_change:
                    self.on_change()
            
            self._exit_input_mode()
            
        elif self.mode == "rename":
            name = self.input_widget.value.strip()
            if name and self.dashboards:
                # Update dashboard name
                self.dashboards[self.selected_index].name = name
                self.config_manager.config.dashboards = self.dashboards
                self.config_manager.save_config()
                
                self._refresh_dashboard_list()
                
                if self.on_change:
                    self.on_change()
            
            self._exit_input_mode()
        
        elif self.mode == "view":
            # Switch to selected dashboard
            if self.dashboards and 0 <= self.selected_index < len(self.dashboards):
                self.config_manager.config.current_dashboard = self.selected_index
                self.config_manager.save_config()
                
                if self.on_change:
                    self.on_change()
                
                self.dismiss()
    
    def _exit_input_mode(self) -> None:
        # Exit input mode and return to view mode.
        self.mode = "view"
        self.input_widget.display = False
        self.list_widget.focus()
    
    def _refresh_dashboard_list(self) -> None:
        # Refresh the dashboard list display.
        self.list_widget.clear()
        
        for i, dashboard in enumerate(self.dashboards):
            current_marker = " [CURRENT]" if i == self.config_manager.config.current_dashboard else ""
            self.list_widget.append(ListItem(Label(f"{dashboard.name}{current_marker}"), classes="dashboard_item"))
        
        # Ensure selection is valid
        if self.dashboards:
            self.selected_index = min(self.selected_index, len(self.dashboards) - 1)
            self.list_widget.index = self.selected_index
    
    def on_key(self, event: Key) -> None:
        # Handle additional key events.
        if self.mode in ["new", "rename"]:
            if event.key == "escape":
                self._exit_input_mode()
                event.stop()
            elif event.key == "enter":
                self.action_confirm_action()
                event.stop()
        
    def action_dismiss(self) -> None:
        if self.mode in ["new", "rename"]:
            self._exit_input_mode()
        else:
            self.dismiss()
