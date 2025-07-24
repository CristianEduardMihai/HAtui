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
    dashboard: DashboardConfig

class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config: Optional[Config] = None
    
    def load_config(self) -> Config:
        # load config from yaml file and get HA details from env
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
            entities = []
            for entity_data in data['dashboard']['entities']:
                entities.append(EntityConfig(**entity_data))
            
            # build the full config
            self.config = Config(
                homeassistant=HomeAssistantConfig(**ha_config),
                dashboard=DashboardConfig(
                    name=data['dashboard']['name'],
                    refresh_interval=data['dashboard']['refresh_interval'],
                    rows=data['dashboard']['rows'],
                    cols=data['dashboard']['cols'],
                    entities=entities
                )
            )
            
            return self.config
            
        except Exception as e:
            raise Exception(f"Failed to load config: {e}")
    
    def save_config(self) -> None:
        # save dashboard config back to yaml (but not HA connection stuff)
        if not self.config:
            raise Exception("No config loaded to save")
        
        try:
            # only save dashboard config, not HA connection details
            config_dict = {
                'dashboard': {
                    'name': self.config.dashboard.name,
                    'refresh_interval': self.config.dashboard.refresh_interval,
                    'rows': self.config.dashboard.rows,
                    'cols': self.config.dashboard.cols,
                    'entities': [asdict(entity) for entity in self.config.dashboard.entities]
                }
            }
            
            with open(self.config_path, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
                
        except Exception as e:
            raise Exception(f"Failed to save config: {e}")
    
    def add_entity(self, entity_id: str, row: int, col: int, entity_type: str = "auto") -> None:
        # add new entity to the dashboard at specific position
        if not self.config:
            raise Exception("No config loaded")
        
        # make sure position isn't already taken
        for entity in self.config.dashboard.entities:
            if entity.row == row and entity.col == col:
                raise Exception(f"Position ({row}, {col}) is already occupied")
        
        # add it and save right away
        new_entity = EntityConfig(entity=entity_id, position=[row, col], type=entity_type)
        self.config.dashboard.entities.append(new_entity)
        self.save_config()
    
    def remove_entity(self, entity_id: str) -> bool:
        # remove entity from dashboard
        if not self.config:
            return False
        
        original_count = len(self.config.dashboard.entities)
        self.config.dashboard.entities = [
            entity for entity in self.config.dashboard.entities 
            if entity.entity != entity_id
        ]
        
        if len(self.config.dashboard.entities) < original_count:
            self.save_config()
            return True
        return False
    
    def move_entity(self, entity_id: str, new_row: int, new_col: int) -> bool:
        # move entity to new spot on the grid
        if not self.config:
            return False
        
        # check if new position is already taken
        for entity in self.config.dashboard.entities:
            if entity.entity != entity_id and entity.row == new_row and entity.col == new_col:
                return False  # spot's taken
        
        # find the entity and update its position
        for entity in self.config.dashboard.entities:
            if entity.entity == entity_id:
                entity.position = [new_row, new_col]  # [row, col]
                self.save_config()
                return True
        
        return False
    
    def get_entity_at_position(self, row: int, col: int) -> Optional[EntityConfig]:
        # see what entity is at this grid position
        if not self.config:
            return None
        
        for entity in self.config.dashboard.entities:
            if entity.row == row and entity.col == col:
                return entity
        return None
    
    def is_position_empty(self, row: int, col: int) -> bool:
        # check if grid spot is empty
        return self.get_entity_at_position(row, col) is None
