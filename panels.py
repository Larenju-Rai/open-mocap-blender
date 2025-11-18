import bpy
from . import globalVariables as gvar
from .PackageInstaller import check_required_packages



# -------------------------------------------------------------
# UI PANEL FOR INSTALLING DEPENDENCY PACKAGES
# -------------------------------------------------------------
class OpenMocapAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    REQUIRED_PACKAGES = ["mediapipe", "opencv-python", "cvzone"]

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Dependency Management", icon="PREFERENCES")

        missing = check_required_packages()

        if missing:
            col.label(text=f"Missing packages: {', '.join(missing)}", icon="ERROR")
            col.operator("addon.install_dependencies", text="Install Dependencies", icon="CONSOLE")
        else:
            col.label(text="All dependencies are installed.", icon="CHECKMARK")
            #col.operator("addon.uninstall_dependencies", text="Uninstall Dependencies", icon="TRASH")



# -------------------------------------------------------------
#UI PANEL FOR POSE TRACKING
# -------------------------------------------------------------
class PoseTrackingPanel(bpy.types.Panel):
    bl_label = "Pose Tracking"
    bl_idname = "Pose_Track_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Open Mocap"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.prop(scene, "multi_view_tracking")
        #layout.label(text="Realtime Pose-tracking")
        #layout.operator("object.start_tracking", text="Start RealTime Pose Tracking", icon='PLAY').track = "rt_pose"
        #layout.operator("object.stop_tracking", text="Stop Pose Tracking", icon='PAUSE').mode = "realtime"
        #layout.separator()
        #layout.label(text="Offline Pose-tracking")

        #Front Video
        if scene.multi_view_tracking:
            layout.label(text="Front Video")
        if gvar.front_video_path:
            layout.label(text = gvar.front_video_path, icon = 'FILE_MOVIE')
        if scene.multi_view_tracking:
            layout.operator("object.open_mocap_filebrowser", text="Select Front Video", icon='FILEBROWSER').video = "front_video_pose"
        else:
            layout.operator("object.open_mocap_filebrowser", text="Select Video", icon='FILEBROWSER').video = "front_video_pose"
        layout.operator("object.start_tracking", text="Start Pose Tracking", icon='PLAY').track = "front_pose"
        layout.operator("object.clear_video_path", text="Delete Video", icon='X').video = "front_video_pose"

        #Side Video
        if scene.multi_view_tracking:
            layout.separator()
            layout.label(text="Side Video")
            if gvar.side_video_path:
                layout.label(text = gvar.side_video_path, icon = 'FILE_MOVIE')
            layout.operator("object.open_mocap_filebrowser", text="Select Side Video", icon='FILEBROWSER').video = "side_video_pose"
            layout.operator("object.start_tracking", text="Start Pose Tracking", icon='PLAY').track = "side_pose"
            layout.operator("object.clear_video_path", text="Delete Video", icon='X').video = "side_video_pose"

        #Settings
        layout.separator()
        layout.label(text="Settings")
        layout.operator("object.stop_tracking", text="Stop Pose Tracking", icon='PAUSE')
        if scene.multi_view_tracking:
            layout.operator("object.combine_data", text="Combine Data", icon='PLUS').mode = "pose"
        layout.operator("object.animate_obj", text="Animate", icon='RENDER_ANIMATION')
        layout.operator("object.hide_skeleton", text="Hide/Unhide Empties", icon='HIDE_OFF').collection_name = "PoseEmpties"
        layout.operator("object.hide_skeleton", text="Hide/Unhide Skeleton", icon='HIDE_OFF').collection_name = "PoseSkeleton"
        layout.operator("object.clear_mocap_cache", text="Clear Capture Cache", icon='TRASH').cache = "pose"
        layout.separator()
        layout.label(text="Animation Baking")
        layout.prop(scene, "bake_rig", text="Select Rig")
        if scene.bake_rig:
            op = layout.operator("pose.toggle_copy_rotation", text="Toggle Constraints", icon="CONSTRAINT")
            op.target_rig = scene.bake_rig.name
        layout.prop(scene, "bake_frame_start")
        layout.prop(scene, "bake_frame_end")
        layout.prop(scene, "bake_only_selected")

        op = layout.operator("object.bake_motion", text="Bake Motion", icon="ACTION_TWEAK")
        if scene.bake_rig:
            op.target_rig = scene.bake_rig.name
        op.frame_start = scene.bake_frame_start
        op.frame_end = scene.bake_frame_end
        op.only_selected_bones = scene.bake_only_selected



# -------------------------------------------------------------
#UI PANEL FOR HAND TRACKING
# -------------------------------------------------------------
class HandTrackingPanel(bpy.types.Panel):
    bl_label = "Hand Tracking"
    bl_idname = "Hand_Tracking_Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Open Mocap"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        scene = context.scene
        layout = self.layout
        layout.prop(scene, "realtime_tracking")
        if scene.realtime_tracking:
            layout.label(text="Realtime Hand-tracking")
            layout.prop(scene, "cam_index", text="Choose a camera")
            layout.prop(scene, "num_hands", text="Number of Hands")
            layout.operator("object.animatehand", text="Start RealTime Hand Tracking", icon='PLAY').mode = "realtime"
            layout.operator("object.stop_tracking", text="Stop Hand Tracking", icon='PAUSE').mode = "realtime"
        layout.separator()
        layout.label(text="Offline Hand-tracking")
        layout.prop(scene, "multi_view_tracking")

        #Front Video
        if scene.multi_view_tracking:
            layout.label(text="Front Video")
        if gvar.hand_front_video_path:
            layout.label(text = gvar.hand_front_video_path, icon = 'FILE_MOVIE')
        if scene.multi_view_tracking:
            layout.operator("object.open_mocap_filebrowser", text="Select Front Video", icon='FILEBROWSER').video = "front_video_hand"
        else:
            layout.operator("object.open_mocap_filebrowser", text="Select Video", icon='FILEBROWSER').video = "front_video_hand"
        
        layout.operator("object.start_tracking", text="Start Hand Tracking", icon='PLAY').track = "front_hand"
        layout.operator("object.clear_video_path", text="Delete Video", icon='X').video = "front_video_hand"

        #Side Video
        if scene.multi_view_tracking:
            layout.separator()
            layout.label(text="Side Video")
            if gvar.hand_side_video_path:
                layout.label(text = gvar.hand_side_video_path, icon = 'FILE_MOVIE')
            layout.operator("object.open_mocap_filebrowser", text="Select Side Video", icon='FILEBROWSER').video = "side_video_hand"
            layout.operator("object.start_tracking", text="Start Hand Tracking", icon='PLAY').track = "side_hand"
            layout.operator("object.clear_video_path", text="Delete Video", icon='X').video = "side_video_hand"

        #Settings
        layout.separator()
        layout.label(text="Settings")
        layout.operator("object.stop_tracking", text="Stop Hand Tracking", icon='PAUSE')
        if scene.multi_view_tracking:
            layout.operator("object.combine_data", text="Combine Data", icon='PLUS').mode = "hand"
        layout.operator("object.animatehand", text="Animate", icon='RENDER_ANIMATION').mode = "offline"
        layout.operator("object.clear_mocap_cache", text="Clear Capture Cache", icon='TRASH').cache = "hand"
        layout.operator("object.hide_skeleton", text="Hide/Unhide R_Empties", icon='HIDE_OFF').collection_name = "RightHandEmpties"
        layout.operator("object.hide_skeleton", text="Hide/Unhide R_Skeleton", icon='HIDE_OFF').collection_name = "RightHandSkeleton"
        layout.operator("object.hide_skeleton", text="Hide/Unhide L_Empties", icon='HIDE_OFF').collection_name = "LeftHandEmpties"
        layout.operator("object.hide_skeleton", text="Hide/Unhide L_Skeleton", icon='HIDE_OFF').collection_name = "LeftHandSkeleton"
        layout.separator()
        layout.label(text="Animation Baking")
        layout.prop(scene, "bake_rig", text="Select Rig")
        if scene.bake_rig:
            op = layout.operator("pose.toggle_copy_rotation", text="Toggle Constraints", icon="CONSTRAINT")
            op.target_rig = scene.bake_rig.name
        else:
            layout.label(text="Select a rig to toggle constraints", icon="INFO")
        layout.prop(scene, "bake_frame_start")
        layout.prop(scene, "bake_frame_end")
        op = layout.operator("object.bake_motion", text="Bake Motion", icon="ACTION_TWEAK")
        layout.prop(scene, "bake_only_selected")

        if scene.bake_rig:
            op.target_rig = scene.bake_rig.name
        op.frame_start = scene.bake_frame_start
        op.frame_end = scene.bake_frame_end
        op.only_selected_bones = scene.bake_only_selected



classes = [OpenMocapAddonPreferences, PoseTrackingPanel, HandTrackingPanel]