import subprocess
import os

def get_apk_paths(folder_path):
    """Get the list of APK paths from the specified folder."""
    apk_paths = []
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".apk"):
            apk_paths.append(os.path.join(folder_path, file_name))
    return apk_paths


def install_split_apks(package_name, apk_paths, device_name):
    """Install split APKs on the specified device."""
    total_size = sum(os.path.getsize(apk_path) for apk_path in apk_paths)

    # Create a directory on the device to store the APKs
    remote_dir = f"/data/local/tmp/{package_name}"
    subprocess.run(
        ["adb", "-s", device_name, "shell", "mkdir", "-p", remote_dir],
        check=True
    )

    # Push each APK to the device
    for apk_path in apk_paths:
        apk_name = os.path.basename(apk_path)
        remote_path = f"{remote_dir}/{apk_name}"
        subprocess.run(
            ["adb", "-s", device_name, "push", apk_path, remote_path],
            check=True
        )

    # Start a new install session
    result = subprocess.run(
        ["adb", "-s", device_name, "shell", "pm", "install-create", "-S", str(total_size)],
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
            check=True
        )

    # Commit the installation
    subprocess.run(
        ["adb", "-s", device_name, "shell", "pm", "install-commit", session_id],
        check=True
    )

    # Clean up the APKs from the device
    subprocess.run(
        ["adb", "-s", device_name, "shell", "rm", "-r", remote_dir],
        check=True
    )

def main():
    package_name = input("Enter the package name: ")
    device_name = input("Enter the ADB device name: ")

    apk_paths = get_apk_paths(package_name)

    if not apk_paths:
        print(f"No APK files found in folder: {package_name}")
        return

    install_split_apks(package_name, apk_paths, device_name)
    print("Finished installing split APKs.")

if __name__ == "__main__":
    main()
