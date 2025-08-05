"""
HAtui Installer
Installs HAtui and creates a convenient shell alias for easy access.
It handles:
- Running the setup process (venv creation, dependency installation) - run.py
- Creating a shell alias based on the user's shell
- Adding the alias to the appropriate shell configuration file
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path
from run import HATuiRunner


class HATuiInstaller:
    def __init__(self):
        self.os_name = platform.system().lower()
        self.project_dir = Path(__file__).parent.absolute()
        self.venv_dir = self.project_dir / ".venv"
        
        # OS-specific configurations
        if self.os_name == "windows":
            self.venv_python = self.venv_dir / "Scripts" / "python.exe"
            self.shell_configs = [
                (Path.home() / ".bashrc", "bash"),
                (Path.home() / ".zshrc", "zsh"),
            ]
        else:
            self.venv_python = self.venv_dir / "bin" / "python"
            self.shell_configs = [
                (Path.home() / ".bashrc", "bash"),
                (Path.home() / ".zshrc", "zsh"),
                (Path.home() / ".config" / "fish" / "config.fish", "fish"),
            ]
    
    def print_banner(self):
        print("=" * 60)
        print("HAtui Installer - Home Assistant TUI Dashboard")
        print("=" * 60)
        print(f"OS: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version.split()[0]}")
        print(f"Installation Directory: {self.project_dir}")
        print("=" * 60)
        print("❗❗❗IMPORTANT: Do NOT move the HAtui folder after installation!")
        print("   The shell alias will point to this exact location.")
        print()
    
    def ask_user_confirmation(self):
        #Ask user if they want to proceed with installation. 
        while True:
            try:
                response = input("Do you want to proceed with the installation? (Y/n): ").strip().lower()
                if response == '' or response == 'y' or response == 'yes':
                    return True
                elif response == 'n' or response == 'no':
                    return False
                else:
                    print("Please enter 'Y' for yes or 'N' for no.")
                    
            except (EOFError, KeyboardInterrupt):
                print("\n\nInstallation cancelled by user.")
                return False
    
    def run_setup(self):
        print("Running HAtui setup...")
        print("-" * 40)
        
        # Create a runner instance and run the setup steps
        runner = HATuiRunner()
        
        try:
            runner.check_python_version()
            runner.create_virtual_environment()
            runner.install_dependencies()
            
            print("HAtui setup completed successfully!")
            
        except Exception as e:
            print(f"Setup failed: {e}")
            sys.exit(1)
    
    def detect_shell(self):
        #Detect the user's current shell. 
        try:
            # Get shell from environment
            shell = os.environ.get('SHELL', '')
            if shell:
                shell_name = Path(shell).name
                return shell_name
            
            # Fallback detection methods
            if self.os_name == "windows":
                return "cmd"  # or powershell
            else:
                return "bash"  # safe default
                
        except Exception:
            return "bash" if self.os_name != "windows" else "cmd"
    
    def get_alias_command(self, shell_name):
        #Generate the appropriate alias command for the shell. 
        hatui_command = f'"{self.venv_python}" "{self.project_dir / "main.py"}"'
        
        if shell_name in ["bash", "zsh"]:
            return f'alias hatui=\'{hatui_command}\''
        elif shell_name == "fish":
            return f'alias hatui \'{hatui_command}\''
        elif shell_name in ["cmd", "powershell"]:
            # For Windows, create a batch file instead
            return None
        else:
            # Default to bash-style
            return f'alias hatui=\'{hatui_command}\''
    
    def create_windows_alias(self):
        #Create a Windows batch file for the hatui command. 
        try:
            batch_content = f'@echo off\n"{self.venv_python}" "{self.project_dir / "main.py"}" %*\n'
            
            # Try multiple locations in order of preference
            potential_paths = [
                # System32 - usually in PATH but requires admin
                # Path(os.environ.get('WINDIR', 'C:\\Windows')) / "System32",
                
                # User's AppData\Local\Microsoft\WindowsApps - usually in PATH
                Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Microsoft' / 'WindowsApps',
                
                # User's local bin directory
                Path.home() / "bin",
                
                # Current project directory as fallback
                self.project_dir,
            ]
            
            success = False
            for target_dir in potential_paths:
                try:
                    if not target_dir.exists():
                        target_dir.mkdir(parents=True, exist_ok=True)
                    
                    batch_file = target_dir / "hatui.bat"
                    batch_file.write_text(batch_content)
                    
                    # Check if this directory is in PATH
                    current_path = os.environ.get('PATH', '')
                    if str(target_dir).lower() in current_path.lower():
                        print(f"Created Windows batch file: {batch_file}")
                        print("   This directory is already in your PATH - hatui command should work!")
                        success = True
                        break
                    else:
                        print(f"Created batch file: {batch_file}")
                        
                except (PermissionError, OSError) as e:
                    print(f"   Cannot write to {target_dir}: {e}")
                    continue
            
            if not success:
                # All locations failed to be in PATH, provide instructions
                print("\nBatch file created but directory not in PATH.")
                print("   Choose one of these options:")
                print(f"   1. Add the directory to your PATH environment variable")
                print(f"   2. Run hatui directly: python \"{self.project_dir / 'main.py'}\"")
                print(f"   3. Use the run.py script: python \"{self.project_dir / 'run.py'}\"")
                
                # Also try to provide PowerShell profile instructions
                self._suggest_powershell_profile()
            
            return True
            
        except Exception as e:
            print(f"Failed to create Windows batch file: {e}")
            return False
    
    def _suggest_powershell_profile(self):
        #Suggest adding a PowerShell function to the user's profile.
        try:
            # Get PowerShell profile path
            profile_result = subprocess.run(
                ['powershell', '-Command', 'echo $PROFILE'], 
                capture_output=True, text=True, timeout=10
            )
            
            if profile_result.returncode == 0:
                profile_path = profile_result.stdout.strip()
                print(f"\nAlternative: Add this function to your PowerShell profile:")
                print(f"   Profile location: {profile_path}")
                print(f"   Add this line:")
                print(f'   function hatui {{ & "{self.venv_python}" "{self.project_dir / "main.py"}" @args }}')
                print(f"   Then restart PowerShell or run: . $PROFILE")
                
        except Exception:
            pass  # If we can't get profile info, that's okay
    
    def add_shell_alias(self):
        #Add the hatui alias to the appropriate shell configuration file. 
        shell_name = self.detect_shell()
        print(f"Detected shell: {shell_name}")
        
        # Handle Windows separately
        if self.os_name == "windows":
            return self.create_windows_alias()
        
        alias_command = self.get_alias_command(shell_name)
        if not alias_command:
            print("Could not generate alias command for this shell")
            return False
        
        # Find the appropriate config file
        config_file = None
        config_type = None
        
        for config_path, shell_type in self.shell_configs:
            if shell_type == shell_name and config_path.exists():
                config_file = config_path
                config_type = shell_type
                break
        
        # If no existing config found, create the most common one
        if not config_file:
            if shell_name == "zsh":
                config_file = Path.home() / ".zshrc"
                config_type = "zsh"
            elif shell_name == "fish":
                config_file = Path.home() / ".config" / "fish" / "config.fish"
                config_type = "fish"
                # Create fish config directory if it doesn't exist
                config_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                config_file = Path.home() / ".bashrc"
                config_type = "bash"
        
        try:
            # Check if alias already exists
            if config_file.exists():
                content = config_file.read_text()
                if "alias hatui=" in content:
                    print(f"HAtui alias already exists in {config_file}")
                    print("   Removing old alias and adding new one...")
                    
                    # Remove existing alias lines
                    lines = content.split('\n')
                    lines = [line for line in lines if not line.strip().startswith('alias hatui=')]
                    content = '\n'.join(lines)
                else:
                    content = config_file.read_text()
            else:
                content = ""
            
            # Add the new alias
            if content and not content.endswith('\n'):
                content += '\n'
            
            content += f'\n# HAtui alias - added by installer\n{alias_command}\n'
            
            # Write back to file
            config_file.write_text(content)
            
            print(f"Added HAtui alias to {config_file}")
            print(f"Reload your shell or run: source {config_file}")
            
            return True
            
        except Exception as e:
            print(f"Failed to add alias to {config_file}: {e}")
            return False

    def show_completion_message(self):
        print("\n" + "=" * 60)
        print("HAtui Installation Complete!")
        print("=" * 60)
        print()
        print("Installation Location:")
        print(f"   {self.project_dir}")
        print()
        print("Configuration:")
        print("   Edit the .env file in the HAtui directory to configure")
        print("   your Home Assistant connection before first use.")
        print()
        print("Quick Start Options:")
        if self.os_name == "windows":
            print("   1. Try typing 'hatui' in a new terminal")
            print("   2. If that doesn't work, run directly:")
            print(f"      python \"{self.project_dir / 'run.py'}\"")
            print("   3. Or use the full path:")
            print(f"      python \"{self.project_dir / 'main.py'}\"")
        else:
            print("   1. Reload your shell: source ~/.bashrc (or ~/.zshrc)")
            print("   2. Then run: hatui")
            print("   3. Or run directly: python3 run.py")
        print()
        print("For help and documentation:")
        print("   https://github.com/CristianEduardMihai/HAtui")
        print("=" * 60)
    
    def install(self):
        #Run the complete installation process. 
        try:
            self.print_banner()
            
            # Ask for user confirmation
            if not self.ask_user_confirmation():
                print("\nInstallation cancelled. You can run HAtui manually with:")
                print(f"   python3 run.py")
                sys.exit(0)
            
            print("\nStarting installation...")
            print("=" * 60)
            
            self.run_setup()
            
            print("\n" + "-" * 40)
            print("Setting up shell alias...")
           
            alias_success = self.add_shell_alias()
            
            if alias_success:
                self.show_completion_message()
            else:
                print("\nInstallation completed, but alias creation failed.")
                print("You can still run HAtui using these methods:")
                print(f"   1. python \"{self.project_dir / 'run.py'}\"")
                print(f"   2. python \"{self.project_dir / 'main.py'}\"")
                if self.os_name == "windows":
                    print("   3. Add the batch file location to your PATH environment variable")
                    print("   4. Or add a PowerShell function to your profile (see instructions above)")
                else:
                    print("   3. Manually add this alias to your shell config:")
                    shell_name = self.detect_shell()
                    alias_cmd = self.get_alias_command(shell_name)
                    if alias_cmd:
                        print(f"      {alias_cmd}")
            
        except KeyboardInterrupt:
            print("\n\nInstallation interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nInstallation failed: {e}")
            sys.exit(1)


def main():
    installer = HATuiInstaller()
    installer.install()


if __name__ == "__main__":
    main()
