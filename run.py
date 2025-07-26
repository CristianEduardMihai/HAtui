"""
HAtui One-Command Runner
This script automatically sets up and runs the HAtui application.
It handles:
- OS detection (Windows, macOS, Linux)
- Python virtual environment creation
- Dependency installation
- Application startup

Usage:
    python3 run.py # python if you're on Windows
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path


class HATuiRunner:
    def __init__(self):
        self.os_name = platform.system().lower()
        self.project_dir = Path(__file__).parent.absolute()
        self.venv_dir = self.project_dir / ".venv"
        self.requirements_file = self.project_dir / "requirements.txt"
        self.env_file = self.project_dir / ".env"
        
        # OS-specific configurations
        if self.os_name == "windows":
            self.python_exe = "python"
            self.pip_exe = self.venv_dir / "Scripts" / "pip"
            self.venv_python = self.venv_dir / "Scripts" / "python"
            self.activate_script = self.venv_dir / "Scripts" / "activate.bat"
        else:
            self.python_exe = "python3"
            self.pip_exe = self.venv_dir / "bin" / "pip"
            self.venv_python = self.venv_dir / "bin" / "python"
            self.activate_script = self.venv_dir / "bin" / "activate"
    
    def print_banner(self):
        print("=" * 60)
        print("HAtui - Home Assistant TUI Dashboard")
        print("=" * 60)
        print(f"OS: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Project: {self.project_dir}")
        print("=" * 60)
    
    def check_python_version(self):
        print("Checking Python version...")
        
        if sys.version_info < (3, 9):
            print("Error: Python 3.9 or higher is required!")
            print(f"   Current version: {sys.version}")
            print("   Please upgrade Python and try again.")
            sys.exit(1)
        
        print(f"Python {sys.version.split()[0]} - Compatible")
    
    def check_env_file(self):
        print("Checking environment configuration...")
        
        if not self.env_file.exists():
            print("Environment file (.env) not found!")
            print()
            print("You need to set up your Home Assistant connection:")
            print("1. Create a .env file in the project directory")
            print("2. Add your Home Assistant URL and token:")
            print("   HA_URL=http://your-ha-instance:8123")
            print("   HA_TOKEN=your_long_lived_access_token")
            
            example_env = self.project_dir / "example.env"
            if example_env.exists():
                print("You can copy the example file:")
                if self.os_name == "windows":
                    print("   copy example.env .env")
                else:
                    print("   cp example.env .env")
                print("Then edit .env with your details.")
            else:
                print("Create .env file with your Home Assistant details.")
            
            print()
            sys.exit(1)
        
        print("Environment file found")
    
    def create_virtual_environment(self):
        print("Setting up virtual environment...")
        
        if self.venv_dir.exists():
            print("Virtual environment already exists")
            return
        
        try:
            subprocess.run([
                sys.executable, "-m", "venv", str(self.venv_dir)
            ], check=True, capture_output=True)
            
            print("Virtual environment created successfully")
            
        except subprocess.CalledProcessError as e:
            print("Error creating virtual environment:")
            print(f"   {e}")
            print("   Please ensure you have python3-venv installed.")
            sys.exit(1)
    
    def install_dependencies(self):
        print("Installing dependencies...")
        
        try:
            subprocess.run([
                str(self.venv_python), "-m", "pip", "install", "-r", str(self.requirements_file)
            ], check=True, capture_output=True)
            
            print("Dependencies installed successfully")
            
        except subprocess.CalledProcessError as e:
            print("Error installing dependencies:")
            print(f"   {e}")
            sys.exit(1)

    def run_application(self):
        print("Starting HAtui...")
        print("=" * 60)
        
        try:
            os.chdir(self.project_dir)
            
            subprocess.run([
                str(self.venv_python), "main.py"
            ], check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"\nError running application: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n\nApplication stopped by user")
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            sys.exit(1)
    

    
    def run(self):
        try:
            self.print_banner()
            self.check_python_version()
            self.check_env_file()
            self.create_virtual_environment()
            self.install_dependencies()
            self.run_application()
            
        except KeyboardInterrupt:
            print("\n\nSetup interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nUnexpected error during setup: {e}")
            sys.exit(1)


def main():
    runner = HATuiRunner()
    runner.run()


if __name__ == "__main__":
    main()
