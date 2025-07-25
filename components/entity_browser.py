from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static, Button, Input, Label, ListView, ListItem
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.binding import Binding
from typing import List, Dict, Any
from ha_client import HomeAssistantClient


class EntityBrowserScreen(ModalScreen):
    # popup for browsing and picking HA entities with search
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select_or_add", "Select/Add"),
        Binding("tab", "focus_next", "Next Field"),
        Binding("shift+tab", "focus_previous", "Previous Field"),
        Binding("ctrl+a", "add_entity", "Add Entity"),
    ]
    
    def __init__(self, ha_client: HomeAssistantClient, occupied_positions: set, default_row: int = 0, default_col: int = 0):
        super().__init__()
        self.ha_client = ha_client
        self.occupied_positions = occupied_positions
        self.default_row = default_row
        self.default_col = default_col
        self.all_entities: List[Dict[str, Any]] = []
        self.filtered_entities: List[Dict[str, Any]] = []
        self.selected_entity_id = None
    
    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Add Entity to Dashboard", id="browser-title")
            yield Label("Use Tab to navigate, Enter to select, Ctrl+A to add, Escape to cancel", id="help-text")
            
            with Vertical():
                yield Label("Search for entity (type entity ID or friendly name):")
                yield Input(placeholder="e.g., light.main_light or Main Light", id="search-input")
                
                yield Label("Search Results (use arrows to navigate):", id="results-label")
                yield ListView(id="entity-list")
                
                yield Label("Position on dashboard:")
                with Horizontal(id="position-container"):
                    yield Label("Row:")
                    yield Input(value=str(self.default_row), id="row-input", classes="position-input")
                    yield Label("Col:")
                    yield Input(value=str(self.default_col), id="col-input", classes="position-input")
            
            with Horizontal():
                yield Button("Add Entity [Ctrl+A]", variant="primary", id="add-btn")
                yield Button("Cancel [Esc]", variant="default", id="cancel-btn")
    
    async def on_mount(self) -> None:
        await self.load_entities()
        self.query_one("#search-input", Input).focus()
    
    async def load_entities(self) -> None:
        # grab all entities from home assistant
        try:
            all_entities = await self.ha_client.get_all_entities()
            
            # filter to useful stuff and sort
            useful_domains = ['light', 'switch', 'sensor', 'binary_sensor', 'climate', 'script', 'automation', 'input_boolean', 'cover', 'fan', 'media_player']
            self.all_entities = [
                entity for entity in all_entities 
                if entity['entity_id'].split('.')[0] in useful_domains
            ]
            
            # sort by domain then name
            self.all_entities = sorted(self.all_entities, 
                                     key=lambda x: (x['entity_id'].split('.')[0], 
                                                   x.get('attributes', {}).get('friendly_name', x['entity_id'])))
            
            # Initially show some popular entities
            self.filter_entities("")
            
        except Exception as e:
            self.query_one("#results-label", Label).update(f"Error loading entities: {e}")
    
    def filter_entities(self, search_term: str) -> None:
        # search through entities
        search_term = search_term.lower().strip()
        
        if not search_term:
            # just show first 50 when nothing typed
            self.filtered_entities = self.all_entities[:50]
        else:
            # search entity id and friendly name
            self.filtered_entities = [
                entity for entity in self.all_entities
                if (search_term in entity['entity_id'].lower() or 
                    search_term in entity.get('attributes', {}).get('friendly_name', '').lower())
            ][:100]  # cap at 100 results
        
        self.update_entity_list()
    
    def update_entity_list(self) -> None:
        # refresh the list widget
        entity_list = self.query_one("#entity-list", ListView)
        entity_list.clear()
        
        if not self.filtered_entities:
            entity_list.append(ListItem(Label("No entities found. Try a different search term.")))
            return
        
        for entity in self.filtered_entities:
            entity_id = entity['entity_id']
            friendly_name = entity.get('attributes', {}).get('friendly_name', entity_id)
            domain = entity_id.split('.')[0]
            
            # Create a more compact display format
            if friendly_name != entity_id and len(friendly_name) < 40:
                display_text = f"{friendly_name} ({domain}) - {entity_id}"
            else:
                display_text = f"{entity_id} ({domain})"
            
            list_item = ListItem(Label(display_text))
            list_item.entity_id = entity_id  # Store for later use
            entity_list.append(list_item)
    
    def on_input_changed(self, event: Input.Changed) -> None:
        # Handle search input changes
        if event.input.id == "search-input":
            self.filter_entities(event.value)
            # Auto-select first entity if exact match
            if event.value.strip() and self.filtered_entities:
                exact_match = next((e for e in self.filtered_entities if e['entity_id'] == event.value.strip()), None)
                if exact_match:
                    self.selected_entity_id = exact_match['entity_id']
                    # Highlight the matching item in the list
                    self._highlight_entity_in_list(exact_match['entity_id'])
                elif len(self.filtered_entities) == 1:
                    # If only one result, auto-select it
                    self.selected_entity_id = self.filtered_entities[0]['entity_id']
                    entity_list = self.query_one("#entity-list", ListView)
                    entity_list.index = 0
    
    def _highlight_entity_in_list(self, entity_id: str) -> None:
        # Highlight the entity with the given ID in the list
        entity_list = self.query_one("#entity-list", ListView)
        for i, child in enumerate(entity_list.children):
            if hasattr(child, 'entity_id') and child.entity_id == entity_id:
                entity_list.index = i
                break
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Handle Enter key in inputs
        if event.input.id == "search-input":
            # If we have search results, focus the entity list
            if self.filtered_entities:
                entity_list = self.query_one("#entity-list", ListView)
                entity_list.focus()
                if entity_list.index is None and len(entity_list.children) > 0:
                    entity_list.index = 0
            elif event.value.strip():
                # Try to use the typed value as entity ID
                entity_id = event.value.strip()
                if any(e['entity_id'] == entity_id for e in self.all_entities):
                    self.selected_entity_id = entity_id
                    # Focus position inputs
                    self.query_one("#row-input", Input).focus()
                else:
                    self.notify("Entity not found. Please select from the list.", severity="error")
        elif event.input.id == "row-input":
            # Move to column input
            self.query_one("#col-input", Input).focus()
        elif event.input.id == "col-input":
            # Add the entity
            self.action_add_entity()
    
    def action_select_or_add(self) -> None:
        # Smart Enter key handler based on current focus
        focused = self.focused
        
        if focused and hasattr(focused, 'id'):
            if focused.id == "search-input":
                # In search: move to entity list or validate entity
                search_input = self.query_one("#search-input", Input)
                if search_input.value.strip() and self.filtered_entities:
                    entity_list = self.query_one("#entity-list", ListView)
                    entity_list.focus()
                    if entity_list.index is None and len(entity_list.children) > 0:
                        entity_list.index = 0
                elif search_input.value.strip():
                    # Direct entity ID entry
                    entity_id = search_input.value.strip()
                    if any(e['entity_id'] == entity_id for e in self.all_entities):
                        self.selected_entity_id = entity_id
                        self.query_one("#row-input", Input).focus()
                    else:
                        self.notify("Entity not found. Please select from the list.", severity="error")
            elif focused.id == "entity-list":
                # In entity list: select the highlighted entity and move to position
                entity_list = self.query_one("#entity-list", ListView)
                if entity_list.highlighted is not None and entity_list.highlighted < len(entity_list.children):
                    highlighted_item = entity_list.children[entity_list.highlighted]
                    if hasattr(highlighted_item, 'entity_id'):
                        self.selected_entity_id = highlighted_item.entity_id
                        # Update search input to show selected entity
                        search_input = self.query_one("#search-input", Input)
                        search_input.value = self.selected_entity_id
                        # Move to position inputs
                        self.query_one("#row-input", Input).focus()
            elif focused.id in ["row-input", "col-input"]:
                # In position inputs: add the entity
                self.action_add_entity()
            elif focused.id in ["add-btn", "cancel-btn"]:
                # On buttons: trigger button action
                if focused.id == "add-btn":
                    self.action_add_entity()
                else:
                    self.action_cancel()
        else:
            # Default: try to add entity
            self.action_add_entity()
    
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Handle entity selection from list
        if hasattr(event.item, 'entity_id'):
            self.selected_entity_id = event.item.entity_id
            # Update search input to show selected entity
            search_input = self.query_one("#search-input", Input)
            search_input.value = self.selected_entity_id
    
    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # Handle entity highlighting in list (for keyboard navigation)
        if event.item and hasattr(event.item, 'entity_id'):
            # Don't auto-select on highlight, just show what would be selected
            pass
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "add-btn":
            self.action_add_entity()
    
    def action_cancel(self) -> None:
        # close the popup
        self.dismiss(None)
    
    def action_add_entity(self) -> None:
        # add the selected entity to the dashboard
        try:
            # get entity id, prioritize selected_entity_id, then search input
            entity_id = self.selected_entity_id
            if not entity_id:
                search_input = self.query_one("#search-input", Input)
                entity_id = search_input.value.strip()
            
            if not entity_id:
                self.notify("please enter or select an entity", severity="error")
                return
            
            # validate entity exists
            entity_exists = any(e['entity_id'] == entity_id for e in self.all_entities)
            if not entity_exists:
                self.notify(f"entity '{entity_id}' not found", severity="error")
                return
            
            # get position
            row_input = self.query_one("#row-input", Input)
            col_input = self.query_one("#col-input", Input)
            
            try:
                row = int(row_input.value or str(self.default_row))
                col = int(col_input.value or str(self.default_col))
            except ValueError:
                self.notify("invalid row/col values. please enter numbers.", severity="error")
                return
            
            # check if position is occupied
            if (row, col) in self.occupied_positions:
                self.notify(f"position ({row}, {col}) is already occupied", severity="error")
                return
            
            # return the result
            result = {"entity": entity_id, "row": row, "col": col}
            self.dismiss(result)
                
        except Exception as e:
            self.notify(f"error adding entity: {e}", severity="error")
