from textual.containers import Container, Horizontal
from textual.widgets import Static, Button, Input, Label
from textual.screen import ModalScreen
from textual.app import ComposeResult
from typing import List
from ha_client import HomeAssistantClient


class EntityBrowserScreen(ModalScreen):
    # popup for browsing and picking HA entities
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
