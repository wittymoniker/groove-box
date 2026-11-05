import json
import os
from typing import Dict, Any, List

class ProjectManager:
    def __init__(self, filename: str = "groovebox_project.json"):
        self.filename = filename

    def serialize_channel(self, channel_name: str, channel_obj: Any) -> Dict[str, Any]:
        """Extracts serializable state from a synth or mixer channel."""
        return {
            "name": channel_name,
            "local_volume": getattr(channel_obj, "local_volume", 1.0),
            "sidechain_depth": getattr(channel_obj, "sidechain_depth", 0.0),
            "sidechain_source": getattr(channel_obj, "sidechain_source_name", None),
            "eq_params": getattr(channel_obj, "eq_params", {"low": 0.0, "mid": 0.0, "high": 0.0})
        }

    def save_project(self, channels: Dict[str, Any], global_settings: Dict[str, Any] = None) -> bool:
        """Saves the current session state to a JSON project file."""
        try:
            project_data = {
                "version": "1.0",
                "global_settings": global_settings or {"tempo": 120.0, "master_vol": 0.9},
                "channels": {name: self.serialize_channel(name, obj) for name, obj in channels.items()}
            }
            
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=4)
                
            print(f"[ProjectManager] Project successfully saved to {os.path.abspath(self.filename)}")
            return True
        except Exception as e:
            print(f"[ProjectManager Error] Failed to save project: {e}")
            return False

    def load_project(self) -> Dict[str, Any]:
        """Loads session state from the JSON project file."""
        if not os.path.exists(self.filename):
            print(f"[ProjectManager Warning] Project file '{self.filename}' not found.")
            return {}
            
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
                
            print(f"[ProjectManager] Project successfully loaded from {os.path.abspath(self.filename)}")
            return project_data
        except Exception as e:
            print(f"[ProjectManager Error] Failed to load project: {e}")
            return {}

# --- Standalone Testing Routine ---
if __name__ == "__main__":
    # Mock channel objects for testing serialization
    class MockChannel:
        def __init__(self, vol, depth, source, eq):
            self.local_volume = vol
            self.sidechain_depth = depth
            self.sidechain_source_name = source
            self.eq_params = eq

    # Initialize mock active channels
    active_channels = {
        "PanelSynth": MockChannel(0.85, 0.0, None, {"low": 1.5, "mid": 0.0, "high": -1.0}),
        "GeometricSynth": MockChannel(0.90, 0.45, "PanelSynth", {"low": 0.0, "mid": 2.0, "high": 0.5})
    }

    manager = ProjectManager("test_project.json")
    
    # Test Saving
    print("--- Testing Project Save ---")
    manager.save_project(active_channels, {"tempo": 128.0, "master_vol": 0.95})

    # Test Loading
    print("\n--- Testing Project Load ---")
    loaded_data = manager.load_project()
    print(json.dumps(loaded_data, indent=4))
    
    # Clean up test file
    if os.path.exists("test_project.json"):
        os.remove("test_project.json")
        print("\n[Test Cleanup] Removed test_project.json")
