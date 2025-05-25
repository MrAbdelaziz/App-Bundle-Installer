import subprocess
import os
import time

def get_connected_devices():
    """Get list of connected ADB devices."""
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=True
        )
        devices = []
        lines = result.stdout.strip().split('\n')[1:]  # Skip the first line "List of devices attached"
        for line in lines:
            if line.strip() and '\tdevice' in line:
                device_id = line.split('\t')[0]
                devices.append(device_id)
        return devices
    except subprocess.CalledProcessError as e:
        print(f"Error getting device list: {e}")
        return []

def get_package_folders(pulled_apks_dir):
    """Get all package folders from the pulled APKs directory."""
    package_folders = []
    if not os.path.exists(pulled_apks_dir):
        return package_folders
    
    for item in os.listdir(pulled_apks_dir):
        item_path = os.path.join(pulled_apks_dir, item)
        if os.path.isdir(item_path):
            package_folders.append(item_path)
    
    return sorted(package_folders)

def get_apk_paths(folder_path):
    """Get the list of APK paths from the specified folder."""
    apk_paths = []
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".apk"):
            apk_paths.append(os.path.join(folder_path, file_name))
    return sorted(apk_paths)

def install_single_apk(apk_path, device_name):
    """Install a single APK file."""
    try:
        subprocess.run(
            ["adb", "-s", device_name, "install", "-r", apk_path],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def install_split_apks(package_name, apk_paths, device_name):
    """Install split APKs on the specified device."""
    try:
        total_size = sum(os.path.getsize(apk_path) for apk_path in apk_paths)
        
        # Create a directory on the device to store the APKs
        remote_dir = f"/data/local/tmp/{package_name.replace('/', '_')}"
        subprocess.run(
            ["adb", "-s", device_name, "shell", "mkdir", "-p", remote_dir],
            check=True,
            capture_output=True
        )
        
        # Push each APK to the device
        for apk_path in apk_paths:
            apk_name = os.path.basename(apk_path)
            remote_path = f"{remote_dir}/{apk_name}"
            subprocess.run(
                ["adb", "-s", device_name, "push", apk_path, remote_path],
                check=True,
                capture_output=True
            )
        
        # Start a new install session
        result = subprocess.run(
            ["adb", "-s", device_name, "shell", "pm", "install-create", "-r", "-S", str(total_size)],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Extract session ID and remove non-numeric characters
        session_id = ''.join(filter(str.isdigit, result.stdout.strip()))
        
        # Stage each APK
        for index, apk_path in enumerate(apk_paths):
            apk_name = os.path.basename(apk_path)
            remote_path = f"{remote_dir}/{apk_name}"
            apk_size = os.path.getsize(apk_path)
            subprocess.run(
                ["adb", "-s", device_name, "shell", "pm", "install-write", "-S", str(apk_size), session_id, str(index), remote_path],
                check=True,
                capture_output=True
            )
        
        # Commit the installation
        subprocess.run(
            ["adb", "-s", device_name, "shell", "pm", "install-commit", session_id],
            check=True,
            capture_output=True
        )
        
        # Clean up the APKs from the device
        subprocess.run(
            ["adb", "-s", device_name, "shell", "rm", "-r", remote_dir],
            check=True,
            capture_output=True
        )
        
        return True
    except subprocess.CalledProcessError as e:
        # Clean up on error
        try:
            subprocess.run(
                ["adb", "-s", device_name, "shell", "rm", "-r", remote_dir],
                capture_output=True
            )
        except:
            pass
        return False

def install_package(package_folder, device_name):
    """Install a package (single or split APKs)."""
    package_name = os.path.basename(package_folder)
    apk_paths = get_apk_paths(package_folder)
    
    if not apk_paths:
        return False, "No APK files found"
    
    if len(apk_paths) == 1:
        # Single APK installation
        success = install_single_apk(apk_paths[0], device_name)
        return success, "Single APK" if success else "Failed to install single APK"
    else:
        # Split APKs installation
        success = install_split_apks(package_name, apk_paths, device_name)
        return success, f"Split APKs ({len(apk_paths)} files)" if success else "Failed to install split APKs"

def main():
    # Get script directory and pulled APKs directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pulled_apks_dir = os.path.join(script_dir, "pulled_apks")
    
    if not os.path.exists(pulled_apks_dir):
        print(f"Error: '{pulled_apks_dir}' directory not found.")
        print("Please run the APK puller script first to create the pulled_apks directory.")
        return
    
    # Get connected devices
    devices = get_connected_devices()
    if not devices:
        print("No ADB devices connected.")
        return
    
    # Select device if multiple are connected
    if len(devices) == 1:
        device_name = devices[0]
        print(f"Using device: {device_name}")
    else:
        print("Multiple devices found:")
        for i, device in enumerate(devices, 1):
            print(f"{i}. {device}")
        
        while True:
            try:
                choice = int(input("Select device number: ")) - 1
                if 0 <= choice < len(devices):
                    device_name = devices[choice]
                    break
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    # Get all package folders
    package_folders = get_package_folders(pulled_apks_dir)
    if not package_folders:
        print(f"No package folders found in {pulled_apks_dir}")
        return
    
    print(f"\nFound {len(package_folders)} packages to install:")
    for i, folder in enumerate(package_folders, 1):
        package_name = os.path.basename(folder)
        apk_count = len(get_apk_paths(folder))
        print(f"{i:2d}. {package_name} ({apk_count} APK{'s' if apk_count != 1 else ''})")
    
    # Ask for confirmation
    print(f"\nThis will install all packages to device: {device_name}")
    confirm = input("Continue? (y/N): ").lower().strip()
    if confirm not in ['y', 'yes']:
        print("Installation cancelled.")
        return
    
    print("\n" + "="*60)
    print("Starting installation...")
    print("="*60)
    
    successful_installs = 0
    failed_installs = 0
    
    for i, package_folder in enumerate(package_folders, 1):
        package_name = os.path.basename(package_folder)
        print(f"\n[{i}/{len(package_folders)}] Installing {package_name}...")
        
        success, details = install_package(package_folder, device_name)
        
        if success:
            print(f"✓ Successfully installed - {details}")
            successful_installs += 1
        else:
            print(f"✗ Failed to install - {details}")
            failed_installs += 1
        
        # Small delay between installations
        if i < len(package_folders):
            time.sleep(1)
    
    print("\n" + "="*60)
    print("Installation Summary:")
    print(f"Successfully installed: {successful_installs} packages")
    print(f"Failed to install: {failed_installs} packages")
    print(f"Total packages: {len(package_folders)}")
    print("="*60)

if __name__ == "__main__":
    main()
