import bpy
import sys
import threading
import subprocess
import importlib.util


# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------
def is_installed(package_name):
    """Check if a Python package is installed in Blender."""
    return importlib.util.find_spec(package_name) is not None

def install_packages():
    packages = ["opencv-python", "opencv-contrib-python", "opencv-python-headless"]
    try:
        for package in packages:
            if is_installed(package):
                subprocess.check_call([sys.executable,"-m","pip","uninstall","-y", package])
        subprocess.check_call([sys.executable,"-m","pip","install","mediapipe==0.10.14","opencv-python==4.11.0.86","cvzone==1.6.1"])
    except subprocess.CalledProcessError as e:
        print(f"Error installing packages: {e}")

def uninstall_packages():
    try:
        subprocess.check_call([sys.executable,"-m","pip","uninstall","-y","mediapipe","opencv-python", "opencv-contrib-python", "opencv-python-headless", "cvzone"])
    except subprocess.CalledProcessError as e:
        print(f"Error uninstalling packages: {e}")


def check_required_packages():
    """Return a list of missing required packages."""
    required = {
        "mediapipe": "mediapipe==0.10.14",
        "cv2": "opencv-python==4.11.0.86",
        "cvzone": "cvzone==1.6.1",
    }

    missing = []
    for module_name, package_name in required.items():
        if not is_installed(module_name):
            missing.append(package_name)
    return missing



# -------------------------------------------------------------
# OPERATORS
# -------------------------------------------------------------
class InstallAddonDependenciesOperator(bpy.types.Operator):
    """Install required Python dependencies"""
    bl_idname = "addon.install_dependencies"
    bl_label = "Install Dependencies"
    bl_description = "Install MediaPipe, OpenCV, and CVZone libraries."

    def execute(self, context):
        self.report({'INFO'}, "Installing dependencies... Check Blender console for progress.")
        threading.Thread(target=install_packages, daemon=True).start()
        return {'FINISHED'}

    def status_report(self, message):
        print(f"[Addon Installer] {message}")


class UninstallAddonDependenciesOperator(bpy.types.Operator):
    """Uninstall Python dependencies"""
    bl_idname = "addon.uninstall_dependencies"
    bl_label = "Uninstall Dependencies"
    bl_description = "Remove MediaPipe, OpenCV, and CVZone libraries"

    def execute(self, context):
        self.report({'INFO'}, "Uninstalling dependencies... Check Blender console for progress.")
        threading.Thread(target=uninstall_packages, daemon=True).start()
        return {'FINISHED'}

    def status_report(self, message):
        print(f"[Addon Uninstaller] {message}")


classes = [InstallAddonDependenciesOperator, UninstallAddonDependenciesOperator]
