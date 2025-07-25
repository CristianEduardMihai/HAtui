from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical
from textual.binding import Binding
from textual.events import Key


class NameEditorScreen(ModalScreen[str]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]
    
    def __init__(self, current_name: str, entity_id: str):
        super().__init__()
        self.current_name = current_name
        self.entity_id = entity_id
    
    def compose(self) -> ComposeResult:
        with Vertical(id="name-editor-dialog"):
            yield Label(f"Edit display name for: {self.entity_id}")
            yield Label("(Leave empty to use Home Assistant name)")
            yield Label("Press Enter to save, Escape to cancel")
            self.name_input = Input(value=self.current_name, placeholder="Enter display name...")
            yield self.name_input
    
    def on_mount(self) -> None:
        # Focus the input field when dialog opens
        self.name_input.focus()
        if self.name_input.value:
            self.set_timer(0.1, self._select_all_text)
    
    def _select_all_text(self) -> None:
        try:
            if hasattr(self.name_input, 'select_range'):
                self.name_input.select_range(0, len(self.name_input.value))
            elif hasattr(self.name_input, 'cursor_position'):
                self.name_input.cursor_position = len(self.name_input.value)
        except Exception:
            pass
    
    async def on_key(self, event: Key) -> None:
        # Handle key events for keyboard-only operation
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.action_save()
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self.action_cancel()
    
    def action_save(self) -> None:
        new_name = self.name_input.value.strip()
        self.dismiss(new_name)
    
    def action_cancel(self) -> None:
        self.dismiss(None)
