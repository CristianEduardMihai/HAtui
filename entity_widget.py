import asyncio
import logging
from textual.widgets import Static
from textual.reactive import reactive
from textual.events import Click
from ha_client import HomeAssistantClient
from config_manager import EntityConfig

logger = logging.getLogger(__name__)

class EntityWidget(Static):
    # shows and controls home assistant entities
    
    def __init__(self, entity_config: EntityConfig, ha_client: HomeAssistantClient):
        super().__init__()
        self.entity_config = entity_config
        self.ha_client = ha_client
        self.state = "unknown"
        self.friendly_name = entity_config.entity.split('.')[-1].replace('_', ' ').title()
        self.attributes = {}
        self.entity_type = self._detect_entity_type()
        self.is_selected = False
        self.is_holding = False
        self.is_being_moved = False
        
        # basic styling
        self.styles.border = ("heavy", "white")
        self.styles.padding = (1, 1)
        self.styles.margin = (0, 1, 1, 0)
        self.styles.width = "100%"
        self.styles.height = 6
    
    def _detect_entity_type(self) -> str:
        # figure out what type of entity this is
        if self.entity_config.type != "auto":
            return self.entity_config.type
        
        domain = self.entity_config.entity.split('.')[0]
        if domain in ['light', 'switch', 'input_boolean']:
            return 'toggle'
        elif domain in ['sensor', 'binary_sensor']:
            return 'sensor'
        elif domain == 'climate':
            return 'climate'
        elif domain in ['script', 'automation']:
            return 'action'
        else:
            return 'sensor'  # when in doubt, treat as sensor
    
    def _get_icon(self) -> str:
        # pick an icon for the entity
        if self.entity_config.icon:
            return self.entity_config.icon
        
        domain = self.entity_config.entity.split('.')[0]
        icons = {
            'light': '💡',
            'switch': '🔌',
            'sensor': '📊',
            'binary_sensor': '🔍',
            'climate': '🌡️',
            'script': '📜',
            'automation': '🤖',
            'input_boolean': '✅'
        }
        return icons.get(domain, '❓')
    
    def _get_safe_id(self) -> str:
        # clean up entity ID for html/css
        return self.entity_config.entity.replace('.', '-').replace('_', '-')
    
    def compose(self):
        safe_id = self._get_safe_id()
        icon = self._get_icon()
        yield Static(f"{icon} {self.friendly_name}", id=f"title-{safe_id}")
        yield Static(f"State: {self.state}", id=f"state-{safe_id}")
        
        if self.entity_type == 'toggle':
            yield Static("SPACE: Toggle", id=f"help-{safe_id}")
        elif self.entity_type == 'action':
            yield Static("SPACE: Run", id=f"help-{safe_id}")
        else:
            yield Static("Read Only", id=f"help-{safe_id}")
    
    def update_display(self) -> None:
        # update widget to show current state
        try:
            safe_id = self._get_safe_id()
            
            # update state text
            state_widget = self.query_one(f"#state-{safe_id}", Static)
            
            # format display based on what kind of entity this is
            if self.entity_type == 'sensor':
                unit = self.attributes.get('unit_of_measurement', '')
                display_state = f"{self.state} {unit}".strip()
                state_widget.update(f"Value: {display_state}")
            elif self.entity_type == 'climate':
                temp = self.attributes.get('current_temperature', 'N/A')
                target = self.attributes.get('temperature', 'N/A')
                state_widget.update(f"Current: {temp}°C | Target: {target}°C")
            else:
                state_widget.update(f"State: {self.state}")
            
            # color coding based on state
            if self.is_holding:
                self.styles.border = ("heavy", "magenta")
                state_widget.styles.color = "magenta"
            elif self.is_being_moved:
                self.styles.border = ("dashed", "gray")
                state_widget.styles.color = "gray"
                self.styles.opacity = "50%"
            elif self.is_selected:
                self.styles.border = ("heavy", "cyan")
            elif self.state in ["on", "home", "heat", "cool"]:
                self.styles.border = ("heavy", "green")
                state_widget.styles.color = "green"
            elif self.state in ["off", "away", "unavailable"]:
                self.styles.border = ("heavy", "red")
                state_widget.styles.color = "red"
            elif self.state == "unknown":
                self.styles.border = ("heavy", "yellow")
                state_widget.styles.color = "yellow"
            else:
                self.styles.border = ("heavy", "blue")
                state_widget.styles.color = "blue"
            
            # update title with icon
            title_widget = self.query_one(f"#title-{safe_id}", Static)
            icon = self._get_icon()
            title_widget.update(f"{icon} {self.friendly_name}")
            
        except Exception:
            # widgets probably not ready yet
            pass
    
    def set_selected(self, selected: bool) -> None:
        # highlight or unhighlight this widget
        self.is_selected = selected
        self.update_display()
    
    def set_holding(self, holding: bool) -> None:
        # set holding state for moving entities
        self.is_holding = holding
        self.update_display()
    
    def set_being_moved(self, being_moved: bool) -> None:
        # set being moved state (dimmed on original position)
        self.is_being_moved = being_moved
        if not being_moved:
            self.styles.opacity = "100%"  # Restore opacity when not being moved
        self.update_display()
    
    async def refresh_state(self) -> None:
        # grab latest state from HA
        try:
            state_data = await self.ha_client.get_state(self.entity_config.entity)
            if state_data:
                self.state = state_data.get("state", "unknown")
                self.attributes = state_data.get("attributes", {})
                self.friendly_name = self.attributes.get("friendly_name", 
                    self.entity_config.entity.split('.')[-1].replace('_', ' ').title())
                self.update_display()
        except Exception as e:
            self.state = "error"
            self.update_display()
    
    async def toggle_entity(self) -> bool:
        # try to toggle or activate this entity
        try:
            if self.entity_type == 'toggle':
                # instant UI update - flip state immediately for zero-delay feedback
                old_state = self.state
                self.state = "on" if old_state == "off" else "off"
                self.update_display()
                
                # send command in background, don't wait for it
                asyncio.create_task(self._send_toggle_command(old_state))
                return True
                    
            elif self.entity_type == 'action':
                domain = self.entity_config.entity.split('.')[0]
                success = await self.ha_client.call_service(domain, "turn_on", self.entity_config.entity)
                if success:
                    # for scripts/automations, just refresh normally
                    await self.refresh_state()
                return success
            else:
                return False  # can't toggle sensors
                
        except Exception:
            return False
    
    async def _send_toggle_command(self, old_state: str) -> None:
        # send actual toggle command in background
        try:
            success = await self.ha_client.toggle_light(self.entity_config.entity)
            
            if not success:
                # if command failed, revert UI
                self.state = old_state
                self.update_display()
            else:
                # verify the change after a short delay
                await asyncio.sleep(0.1)
                await self.refresh_state()
                
        except Exception:
            # if anything goes wrong, revert the UI
            self.state = old_state
            self.update_display()
    
    async def _verify_state_change(self) -> None:
        # verify state change in background after a short delay
        await asyncio.sleep(0.1)  # very short delay to let HA process
        await self.refresh_state()

    def on_click(self, event: Click) -> None:
        # Forward click events to the main app for handling
        logger.debug(f"EntityWidget click - Entity: {self.entity_config.entity}, Event: {event}")
        # bubble the click event up to the main app
        # main app will handle entity selection/toggle logic
        event.bubble = True
