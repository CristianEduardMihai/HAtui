import os
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

@dataclass
class EntityConfig:
    entity: str
    position: List[int]  # [row, col]
    type: str = "auto"  # auto, toggle, sensor, climate
    icon: Optional[str] = None
    display_name: Optional[str] = None
    
    @property
    def row(self) -> int:
        return self.position[0]
    
    @property 
    def col(self) -> int:
        return self.position[1]
    
    @row.setter
    def row(self, value: int):
        self.position[0] = value
        
    @col.setter
    def col(self, value: int):
        self.position[1] = value

@dataclass
class DashboardConfig:
    name: str
    refresh_interval: int
    rows: int
    cols: int
    entities: List[EntityConfig]

@dataclass
class HomeAssistantConfig:
    url: str
    token: str

@dataclass
class Config:
    homeassistant: HomeAssistantConfig
    dashboards: List[DashboardConfig]
    current_dashboard: int = 0 

class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Optional[Config] = None
    
    def create_default_config(self) -> None:
        default_config = {
            'current_dashboard': 0,
            'dashboards': [
                {
                    'name': 'Default Dashboard',
                    'rows': 3,
                    'cols': 3,
                    'refresh_interval': 5,
                    'entities': [
                        {
                            'entity': 'sun.sun',
                            'position': [0, 0],
                            'type': 'sensor',
                            'display_name': 'Sun Status'
                        }
                    ]
                }
            ]
        }
        
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
            print(f"Created default config file: {self.config_path}")
        except Exception as e:
            raise Exception(f"Failed to create default config: {e}")
    
    def load_config(self) -> Config:
        # load config from yaml file and get HA details from env
        # create default config if it doesn't exist
        if not os.path.exists(self.config_path):
            self.create_default_config()
        
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # always get HA config from .env, not from YAML
            ha_config = {
                'url': os.getenv('HA_URL', 'http://127.0.0.1:8123'),
                'token': os.getenv('HA_TOKEN', '')
            }
            
            if not ha_config['token']:
                raise Exception("HA_TOKEN environment variable is required")
            
            # turn entity data into proper objects
            dashboards = []
            
            if 'dashboard' in data:
                entities = []
                for entity_data in data['dashboard']['entities']:
                    entities.append(EntityConfig(**entity_data))
                
                dashboard = DashboardConfig(
                    name=data['dashboard']['name'],
                    refresh_interval=data['dashboard']['refresh_interval'],
                    rows=data['dashboard']['rows'],
                    cols=data['dashboard']['cols'],
                    entities=entities
                )
                dashboards.append(dashboard)
                current_dashboard = 0
                
            elif 'dashboards' in data:
                for dashboard_data in data['dashboards']:
                    entities = []
                    for entity_data in dashboard_data['entities']:
                        entities.append(EntityConfig(**entity_data))
                    
                    dashboard = DashboardConfig(
                        name=dashboard_data['name'],
                        refresh_interval=dashboard_data['refresh_interval'],
                        rows=dashboard_data['rows'],
                        cols=dashboard_data['cols'],
                        entities=entities
                    )
                    dashboards.append(dashboard)
                current_dashboard = data.get('current_dashboard', 0)
            else:
                raise Exception("Invalid config format - missing dashboard or dashboards section")
            
            # build the full config
            self.config = Config(
                homeassistant=HomeAssistantConfig(**ha_config),
                dashboards=dashboards,
                current_dashboard=current_dashboard
            )
            
            return self.config
            
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")
    
    def save_config(self) -> None:
        # save dashboard config back to yaml (but not HA connection stuff)
        if not self.config:
            raise Exception("No config loaded to save")
        
        try:
            # save in new multi-dashboard format
            config_dict = {
                'current_dashboard': self.config.current_dashboard,
                'dashboards': []
            }
            
            for dashboard in self.config.dashboards:
                dashboard_dict = {
                    'name': dashboard.name,
                    'refresh_interval': dashboard.refresh_interval,
                    'rows': dashboard.rows,
                    'cols': dashboard.cols,
                    'entities': [asdict(entity) for entity in dashboard.entities]
                }
                config_dict['dashboards'].append(dashboard_dict)
            
            with open(self.config_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                
        except Exception as e:
            raise Exception(f"Failed to save config: {e}")
    
    def get_current_dashboard(self) -> DashboardConfig:
        # Get the currently active dashboard
        if not self.config or not self.config.dashboards:
            raise Exception("No dashboards configured")
        
        index = self.config.current_dashboard
        if index >= len(self.config.dashboards):
            index = 0
            self.config.current_dashboard = 0
        
        return self.config.dashboards[index]
    
    def switch_dashboard(self, direction: int) -> DashboardConfig:
        # Switch to next/previous dashboard
        if not self.config or not self.config.dashboards:
            raise Exception("No dashboards configured")
        
        current = self.config.current_dashboard
        new_index = (current + direction) % len(self.config.dashboards)
        self.config.current_dashboard = new_index
        self.save_config()
        
        return self.config.dashboards[new_index]
    
    def get_dashboard_count(self) -> int:
        # Get total number of dashboards
        if not self.config:
            return 0
        return len(self.config.dashboards)
    
    def add_entity(self, entity_id: str, row: int, col: int, entity_type: str = "auto") -> None:
        # add new entity to the current dashboard at specific position
        if not self.config:
            raise Exception("No config loaded")
        
        current_dashboard = self.get_current_dashboard()
        
        # make sure position isn't already taken
        for entity in current_dashboard.entities:
            if entity.row == row and entity.col == col:
                raise Exception(f"Position ({row}, {col}) is already occupied")
        
        # add it and save right away
        new_entity = EntityConfig(entity=entity_id, position=[row, col], type=entity_type)
        current_dashboard.entities.append(new_entity)
        self.save_config()
    
    def remove_entity(self, entity_id: str) -> bool:
        # remove entity from current dashboard
        if not self.config:
            return False
        
        current_dashboard = self.get_current_dashboard()
        
        original_count = len(current_dashboard.entities)
        current_dashboard.entities = [
            entity for entity in current_dashboard.entities 
            if entity.entity != entity_id
        ]
        
        if len(current_dashboard.entities) < original_count:
            self.save_config()
            return True
        return False
    
    def move_entity(self, entity_id: str, new_row: int, new_col: int) -> bool:
        # move entity to new spot on the current dashboard grid
        if not self.config:
            return False
        
        current_dashboard = self.get_current_dashboard()
        
        # check if new position is already taken
        for entity in current_dashboard.entities:
            if entity.entity != entity_id and entity.row == new_row and entity.col == new_col:
                return False  # spot's taken
        
        # find the entity and update its position
        for entity in current_dashboard.entities:
            if entity.entity == entity_id:
                entity.position = [new_row, new_col]  # [row, col]
                self.save_config()
                return True
        
        return False
    
    def update_entity_display_name(self, entity_id: str, display_name: str) -> bool:
        # Update the display name for an entity in current dashboard
        if not self.config:
            return False
        
        current_dashboard = self.get_current_dashboard()
        
        # Find the entity and update its display name
        for entity in current_dashboard.entities:
            if entity.entity == entity_id:
                entity.display_name = display_name.strip() if display_name.strip() else None
                self.save_config()
                return True
        
        return False
    
    def get_entity_at_position(self, row: int, col: int) -> Optional[EntityConfig]:
        # see what entity is at this grid position in current dashboard
        if not self.config:
            return None
        
        current_dashboard = self.get_current_dashboard()
        
        for entity in current_dashboard.entities:
            if entity.row == row and entity.col == col:
                return entity
        return None
    
    def is_position_empty(self, row: int, col: int) -> bool:
        # check if grid spot is empty
        return self.get_entity_at_position(row, col) is None
    
    def add_dashboard(self, name: str, rows: int = 3, cols: int = 3, refresh_interval: int = 5) -> int:
        # Add a new dashboard and return its index
        if not self.config:
            raise Exception("No config loaded")
        
        new_dashboard = DashboardConfig(
            name=name,
            rows=rows,
            cols=cols,
            refresh_interval=refresh_interval,
            entities=[]
        )
        
        self.config.dashboards.append(new_dashboard)
        self.save_config()
        
        return len(self.config.dashboards) - 1
    
    def delete_dashboard(self, index: int) -> bool:
        # Delete dashboard at index, return True if successful
        if not self.config or index < 0 or index >= len(self.config.dashboards):
            return False
        
        # Can't delete the last dashboard
        if len(self.config.dashboards) <= 1:
            return False
        
        # Remove the dashboard
        self.config.dashboards.pop(index)
        
        # Adjust current dashboard index if needed
        if index == self.config.current_dashboard:
            # Deleted current dashboard, move to previous or 0
            self.config.current_dashboard = max(0, index - 1)
        elif index < self.config.current_dashboard:
            # Deleted dashboard before current, adjust index
            self.config.current_dashboard -= 1
        
        self.save_config()
        return True
    
    def rename_dashboard(self, index: int, new_name: str) -> bool:
        # Rename dashboard at index
        if not self.config or index < 0 or index >= len(self.config.dashboards):
            return False
        
        self.config.dashboards[index].name = new_name.strip()
        self.save_config()
        return True
