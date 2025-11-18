"""
    All the necessary operators for the addon are here.
    The operators in order are as follows:
    1) Main operators:
    StartTracking, StopTracking, CombineMotionData, AnimatePose, AnimateHand, BakeMotion
    2) Helper operators:
    ClearMoCapCache, VideoSelect,  ClearVideoPath, ToggleCopyRotationConstraints, HideSkeleton
"""

import bpy
import math
from . import utils
from mathutils import Vector
from . import globalVariables as gvar

# -------------------------------------------------------------
# MAIN OPERATORS
# -------------------------------------------------------------
class StartTracking(bpy.types.Operator):
    bl_idname = "object.start_tracking"
    bl_label = "Start Motion Tracking"
    bl_description = "Starts motion tracking."

    track: bpy.props.StringProperty()
    """
        It starts tracking the video from a file or realtime video stream from camera.
        :param track: Helps in deciding whether tracking pose or hand, 
                        whether tracking offline or realtime 
                        and whether tracking from front view or from side view
    """


    def execute(self, context):
        if self.track == "front_pose":
            gvar.pose_tracker = utils.PoseTracking("front_pose")

        elif self.track == "side_pose":
            gvar.pose_tracker = utils.PoseTracking("side_pose")

        elif self.track == "rt_pose":
            #realtime tracking
            gvar.pose_tracker = utils.PoseTracking("rt_pose")

        elif self.track == "front_hand":
            num_hands = context.scene.num_hands
            gvar.hand_tracker = utils.HandTracking(num_hands=num_hands, mode="front_hand")

        elif self.track == "side_hand":
            num_hands = context.scene.num_hands
            gvar.hand_tracker = utils.HandTracking(num_hands=num_hands, mode="side_hand")

        else:
            #realtime tracking
            num_hands = context.scene.num_hands
            gvar.hand_tracker = utils.HandTracking(num_hands=num_hands, mode="rt_hand")

        return {'FINISHED'}



class StopTracking(bpy.types.Operator):
    bl_idname = "object.stop_tracking"
    bl_label = "Stop Motion Tracking"
    bl_description = "Stops motion tracking."

    mode: bpy.props.StringProperty()
    """
        It stops motion tracking (all types).
        :param mode: Tells if it is a realtime tracker.
                    If so, then Video plane and its textures must be deleted from Blender scene.
    """

    def execute(self, context):
        if self.mode == "realtime":
            utils.VideoPlaneManager.remove_plane()

        #stop playing animation    
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        #stop pose tracker if running
        if gvar.pose_tracker is not None:
            gvar.pose_tracker.stop()
            gvar.pose_tracker = None

        #stop hand tracker if running
        elif gvar.hand_tracker is not None:
            gvar.hand_tracker.stop()
            gvar.hand_tracker = None

        else:
            self.report({'WARNING'}, "No tracking running")

        return {'FINISHED'}
    


class CombineMotionData(bpy.types.Operator):
    bl_idname = "object.combine_data"
    bl_label = "Combine Motion Data"
    bl_description = "Synchronously combines the mocap data from two different cameras views."

    mode: bpy.props.StringProperty()
    """
        It replaces the inaccurate z coordinate of a tracked point from front view
          with accurate x coordinate of a tracked point from side view. 
          This reduces inaccuracy of motion tracking.
        :param mode: Tells whether pose data is combined or hand tracking data is combined.
    """

    def combine_lists(self, front_list, side_list, num_points):
        """
            Combine front and side lists into new list with updated Z values.
            :param front_list: Motion data from front view.
            :param side_list: Motion data from side view.
            :param num_points: If tracking pose, each video frame will have 40 points.
                                If tracking hand, each frame will have 21 points per hand.
            :return combined: The new combined motion data with improved tracking accuracy.
        """
        combined = []
        min_frames = min(len(front_list), len(side_list))

        for f in range(min_frames):
            frame_front = front_list[f].copy()  # copy to avoid modifying original
            frame_side = side_list[f]

            for i in range(num_points):
                frame_front[3 * i + 2] = -frame_side[3 * i + 0]  # z = -x (side)
            combined.append(frame_front)

        return combined
    
    def execute(self, context):

        if self.mode == "pose":
            gvar.positionList = self.combine_lists(gvar.positionList, gvar.zlist, 40)

        elif self.mode == "hand":
            # Right hand
            if gvar.R_hand_positionList and gvar.R_hand_zlist:
                gvar.R_hand_positionList = self.combine_lists(gvar.R_hand_positionList, gvar.R_hand_zlist, 21)

            # Left hand
            if gvar.L_hand_positionList and gvar.L_hand_zlist:
                gvar.L_hand_positionList = self.combine_lists(gvar.L_hand_positionList, gvar.L_hand_zlist, 21)

        else:
            self.report({'WARNING'}, f"Unknown mode: {self.mode}")

        return {'FINISHED'}



class AnimatePose(bpy.types.Operator):
    bl_idname = "object.animate_obj"
    bl_label = "Animate Pose"
    bl_description = "Animates a skeleton with the tracked pose motion data."

    """
        Creates 40 empty objects to copy motion data of 40 pose landmarks.
        Creates a root empty and parent all 40 empties to this.
        Creates a skeleton with these 40 empties and adds keyframes for 40 empties with the motion data.
        This animates the skeleton automatically.
    """

    def execute(self, context):
        gvar.bones_list.clear()
        gvar.object_list.clear()
        # --- Get or create collection ---
        pose_empties_collection = utils.BlenderUtility.create_collection(context,"PoseEmpties")
        root_collection = utils.BlenderUtility.create_collection(context,"RootEmpties")

        # --- Create root empty ---
        root = bpy.data.objects.new("RigRoot", None)
        root.empty_display_type = 'SPHERE'
        root.empty_display_size = 1
        root_collection.objects.link(root)
        gvar.root = root

        # --- Create empties ---
        for i in range(40):
            empty = bpy.data.objects.new(name=str(i), object_data=None)
            empty.empty_display_size = 0.1
            empty.empty_display_type = 'SPHERE'
            pose_empties_collection.objects.link(empty)
            empty.parent = gvar.root
            gvar.object_list.append(empty)

        # --- Define bone pairs ---
        bone_pairs = [
            (7,8), (11,12), (23,24), (16,35), (15,36),
            (11,13), (13,15), (33,34), (38,39),
            (12,14), (14,16), (34,37),
            (24,26), (26,28), (28,32),
            (23,25), (25,27), (27,31)
        ]

        # --- Create skeleton (with default Y tracking) ---
        bones_created = utils.Skeleton.create_skeleton(context, bone_pairs, "pose")
        # --- Apply configuration-specific adjustments ---
        # --- These adjustments help in smooth motion retargeting for specific bones---
        track_x_pairs = {(7,8), (11,12), (23,24)}
        rotate_y_pairs = {(12,14),(11,13),(13,15),(14,16), (16,35), (15,36),}
        for a, b, obj in bones_created:
            #Adjust tracking axis for specific pairs
            if (a, b) in track_x_pairs:
                for constraint in obj.constraints:
                    if constraint.type == 'DAMPED_TRACK':
                        constraint.track_axis = 'TRACK_NEGATIVE_X'
                        break
            # Rotate if needed
            if (a, b) in rotate_y_pairs:
                obj.rotation_euler.rotate_axis('Y', math.radians(180))

        # --- Keyframe insertion ---
        num_frames = len(gvar.positionList)
        context.scene.frame_start = 1
        context.scene.frame_end = num_frames
        context.scene.render.fps = int(gvar.fps)

        for frame_index, frame in enumerate(gvar.positionList, start=1):
            context.scene.frame_set(frame_index)

            for i in range(40):
                location = utils.MathUtility.cv2blender_coordinates([frame[0 + (i * 3)],frame[1 + (i * 3)],frame[2 + (i * 3)]])
                obj = gvar.object_list[i]
                local_pos = Vector(location) - gvar.root.location
                obj.location = local_pos
                obj.keyframe_insert(data_path="location", frame=frame_index)

        bpy.ops.screen.animation_play()
        return {'FINISHED'}



class AnimateHand(bpy.types.Operator):
    bl_idname = "object.animatehand"
    bl_label = "Animate Hand"
    bl_description = "Animates a skeleton with the tracked hand motion data."
    mode: bpy.props.StringProperty()
    """ Creates left/right hand(s) and animates them (realtime/offline)"""

    def create_hand(self, context, prefix):
        """
            Creates 21 empty objects to copy motion data of 21 hand landmarks.
            Creates a root empty and parent all 21 empties to this.
            Creates a skeleton with these 21 empties.
            :param prefix: R for right hand and L for left hand
        """
        if prefix == "R":
            hand_name = "Right"
            gvar.R_hand_bones_list = []
            gvar.R_hand_object_list = []
            object_list = gvar.R_hand_object_list
        else:
            hand_name = "Left"
            gvar.L_hand_bones_list = []
            gvar.L_hand_object_list = []
            gvar.L_hand_object_list.clear()
            object_list = gvar.L_hand_object_list

        root_collection = utils.BlenderUtility.create_collection(context,"RootEmpties")
        hand_empties_collection = utils.BlenderUtility.create_collection(context, f"{hand_name}HandEmpties")

        bone_pairs = [
            (0,1),(1,2),(2,3),(3,4),
            (5,6),(6,7),(7,8),
            (9,10),(10,11),(11,12),
            (13,14),(14,15),(15,16),
            (17,18),(18,19),(19,20),
            (0,5),(0,9),(0,13),(0,17),
            (5,9),(9,13),(13,17),(1,5)
        ]

        # ---------------Create Empty Root------------------
        root = bpy.data.objects.new(f"{hand_name}HandRoot", None)
        root.empty_display_type = 'SPHERE'
        root.empty_display_size = 0.5
        root_collection.objects.link(root)
        if prefix == "R":
            gvar.R_hand_root = root
        else:
            gvar.L_hand_root = root
            
        # ---------------Create 21 Empties------------------
        for i in range(21):
            empty = bpy.data.objects.new(name=f"{prefix}_h{i}", object_data=None)
            empty.empty_display_size = 0.1
            empty.empty_display_type = 'SPHERE'
            hand_empties_collection.objects.link(empty)
            empty.parent = root
            object_list.append(empty)

        if prefix == "R":
            utils.Skeleton.create_skeleton(context, bone_pairs, "R_hand")
        else:
            utils.Skeleton.create_skeleton(context, bone_pairs, "L_hand")


    def hand_exists(self, prefix):
        """
        Check if the hand already exists by checking:
        - 21 empties exist (R_h0 ... R_h20 OR L_h0 ... L_h20)
        - root empty exists (RightHandRoot or LeftHandRoot)
        """
        hand_name = "Right" if prefix == "R" else "Left"
        root_name = f"{hand_name}HandRoot"

        # Check root
        if root_name not in bpy.data.objects:
            return False

        # Check 21 empties
        for i in range(21):
            obj_name = f"{prefix}_h{i}"
            if obj_name not in bpy.data.objects:
                return False

        return True


    def execute(self, context):
        if self.mode == "realtime":
            num_hands = context.scene.num_hands
            gvar.hand_tracker = utils.HandTracking(num_hands,"rt_hand")

            # --- Create Right Hand ---
            if not self.hand_exists("R"):
                self.create_hand(context, "R")

            # --- Create Left Hand ---
            if not self.hand_exists("L"):
                self.create_hand(bpy.context, "L")

            bpy.app.timers.register(self.animate_realtime, first_interval=0.0)
            bpy.ops.screen.animation_play()

        else:
            # --- Create Right Hand ---
            if not self.hand_exists("R"):
                self.create_hand(context, "R")

            # --- Create Left Hand ---
            if not self.hand_exists("L"):
                self.create_hand(bpy.context, "L")

            # --- Determine total frame range ---
            num_frames_R = len(gvar.R_hand_positionList)
            num_frames_L = len(gvar.L_hand_positionList)
            total_frames = max(num_frames_R, num_frames_L, 1)
            context.scene.frame_start = 1
            context.scene.frame_end = total_frames
            context.scene.render.fps = int(gvar.fps)

            # --- Animate Right Hand ---
            if gvar.R_hand_object_list and num_frames_R > 0:
                for frame_index, frame in enumerate(gvar.R_hand_positionList, start=1):
                    context.scene.frame_set(frame_index)
                    for i in range(21):
                        loc = utils.MathUtility.cv2blender_coordinates([
                            frame[i*3], frame[i*3+1], frame[i*3+2]
                        ])
                        obj = gvar.R_hand_object_list[i]
                        obj.location = Vector(loc) - gvar.R_hand_root.location
                        obj.keyframe_insert(data_path="location", frame=frame_index)

            # --- Animate Left Hand ---
            if gvar.L_hand_object_list and num_frames_L > 0:
                for frame_index, frame in enumerate(gvar.L_hand_positionList, start=1):
                    context.scene.frame_set(frame_index)
                    for i in range(21):
                        loc = utils.MathUtility.cv2blender_coordinates([
                            frame[i*3], frame[i*3+1], frame[i*3+2]
                        ])
                        obj = gvar.L_hand_object_list[i]
                        obj.location = Vector(loc) - gvar.L_hand_root.location
                        obj.keyframe_insert(data_path="location", frame=frame_index)

            # --- Playback ---
            tracked_R = bool(gvar.R_hand_positionList)
            tracked_L = bool(gvar.L_hand_positionList)
            self.report({'INFO'}, f"Hand animation complete. (Right: {tracked_R}, Left: {tracked_L})")
            bpy.ops.screen.animation_play()
        return {'FINISHED'}
    
    def animate_realtime(self):
        if not gvar.hand_tracker or not gvar.hand_tracker.running:
            print("Stopping timer: tracker stopped.")
            return None
        success, img = gvar.hand_tracker.cap.read()
        if not success:
            print("Stopping timer: failed to read frame.")
            gvar.hand_tracker.stop()
            return None

        img = gvar.hand_tracker.detect_hand(img)


        # --- Animate Right Hand ---
        if gvar.R_hand_object_list and len(gvar.rt_hand_lmlist_R) > 0:
            for i, point in enumerate(gvar.rt_hand_lmlist_R):
                loc = utils.MathUtility.cv2blender_coordinates(point)
                obj = gvar.R_hand_object_list[i]
                obj.location = Vector(loc) - gvar.R_hand_root.location

        # --- Animate Left Hand ---
        if gvar.L_hand_object_list and len(gvar.rt_hand_lmlist_L) > 0:
            for i, point in enumerate(gvar.rt_hand_lmlist_L):
                loc = utils.MathUtility.cv2blender_coordinates(point)
                obj = gvar.L_hand_object_list[i]
                obj.location = Vector(loc) - gvar.L_hand_root.location
        utils.VideoPlaneManager.update_frame(img)
        return gvar.delay


class BakeMotion(bpy.types.Operator):
    bl_idname = "object.bake_motion"
    bl_label = "Bake Motion"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Bakes animation of selected armature or bones"

    frame_start: bpy.props.IntProperty(name="Start Frame", default=1)
    frame_end: bpy.props.IntProperty(name="End Frame", default=250)
    only_selected_bones: bpy.props.BoolProperty(
        name="Only Selected Bones",
        default=True,
        description="Bake only selected bones in Pose Mode"
    )
    target_rig: bpy.props.StringProperty(name="Target Rig")

    """
        :param frame_start: Starting frame for baking animation.
        :param frame_end: Final frame for baking animation.
        :param only_selected_bones: Bake only selected bones in Pose Mode.
                                    Otherwise bakes animation for all the bones in the armature selected.
        :param target_rig: Armature, whose animation is to be baked.
    """

    def execute(self, context):
        obj = bpy.data.objects.get(self.target_rig)

        if not obj or obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select a valid Armature object")
            return {'CANCELLED'}

        bpy.ops.object.mode_set(mode='POSE')

        # Determine bones to bake
        bones = (
            [b for b in context.selected_pose_bones]
            if self.only_selected_bones and context.selected_pose_bones
            else obj.pose.bones
        )

        if not bones:
            self.report({'ERROR'}, "No bones found to bake")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Baking motion for {len(bones)} bone(s)...")

        # Deselect all bones
        for pb in obj.pose.bones:
            pb.bone.select = False
        for pb in bones:
            pb.bone.select = True

        # Perform bake
        bpy.ops.nla.bake(
            frame_start=self.frame_start,
            frame_end=self.frame_end,
            only_selected=True,
            visual_keying=True,
            clear_constraints=False,
            use_current_action=True,
            bake_types={'POSE'}
        )

        self.report({'INFO'}, "Baking complete.")
        return {'FINISHED'}



# -------------------------------------------------------------
# HELPER OPERATORS
# -------------------------------------------------------------
class ClearMoCapCache(bpy.types.Operator):
    bl_idname = "object.clear_mocap_cache"
    bl_label = "Clear Capture Cache"
    bl_description = "Clears the captured motion data from the temporary cache."

    cache: bpy.props.StringProperty()

    """
        :param cache: If cache = "pose", then all motion data for pose tracked recently will be cleared.
                        Else all motion data for hand tracked recently will be cleared.
    """

    def execute(self,context):
        if self.cache == "pose":
            gvar.positionList.clear()
            gvar.zlist.clear()
            gvar.object_list.clear()
            gvar.bones_list.clear()
            self.report({'INFO'}, "Body Motion Capture data cleared.")
        else:
            gvar.R_hand_positionList.clear()
            gvar.R_hand_zlist.clear()
            gvar.R_hand_object_list.clear()
            gvar.R_hand_bones_list.clear()
            gvar.L_hand_positionList.clear()
            gvar.L_hand_zlist.clear()
            gvar.L_hand_object_list.clear()
            gvar.L_hand_bones_list.clear()
            self.report({'INFO'}, "Hand Motion Capture data cleared.")
        return {'FINISHED'}



class VideoSelect(bpy.types.Operator):
    bl_idname = "object.open_mocap_filebrowser"
    bl_label = "Open Video File"
    bl_description = "Selects a video file from your disk."

    video: bpy.props.StringProperty()

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    
    filter_glob: bpy.props.StringProperty(
        default="*.mp4;*.avi;*.mov;*.mkv;*.flv;*.wmv",
        options={'HIDDEN'}
    )

    """
        :param video: Tells if video is selected for hand or pose tracking and whether it is front view or side view.
        :param filepath: Stores file path of the selected video.
        :param filter_glob: Allows only common video formats.
    """
    def execute(self, context):
        # Validate the selected file extension
        allowed_exts = (".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv")
        if not self.filepath.lower().endswith(allowed_exts):
            self.report({'ERROR'}, "Please select a valid video file.")
            return {'CANCELLED'}

        if self.video == "front_video_pose":
            gvar.front_video_path = self.filepath
        elif self.video == "side_video_pose":
            gvar.side_video_path = self.filepath
        elif self.video == "front_video_hand":
            gvar.hand_front_video_path = self.filepath
        else:
            gvar.hand_side_video_path = self.filepath

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}



class ClearVideoPath(bpy.types.Operator):
    bl_idname = "object.clear_video_path"
    bl_label = "Clear Video Path"
    bl_description = "Deletes video path."

    video: bpy.props.StringProperty()
    """
        :param video: Tells which video panel's video path to delete.
    """

    def execute(self, context):
        if self.video == "front_video_pose":
            gvar.front_video_path = ""
        elif self.video == "side_video_pose":
            gvar.side_video_path = ""
        elif self.video == "front_video_hand":
            gvar.hand_front_video_path = ""
        else:
            gvar.hand_side_video_path = ""
        return {'FINISHED'}



class ToggleCopyRotationConstraints(bpy.types.Operator):
    bl_idname = "pose.toggle_copy_rotation"
    bl_label = "Toggle Constraints"
    bl_description = "Enable or disable all bone constraints on the selected rig"

    target_rig: bpy.props.StringProperty(name="Target Rig")

    """
        :param target_rig: Toggles bone constraints of all the bones of the target_rig.
    """

    def execute(self, context):
        obj = bpy.data.objects.get(self.target_rig)

        if not obj or obj.type != 'ARMATURE':
            self.report({'WARNING'}, "Please select a valid armature rig.")
            return {'CANCELLED'}

        # Check if at least one constraint is currently active (unmuted)
        any_enabled = any(
            (c.type in {'COPY_ROTATION', 'COPY_LOCATION'}) and not c.mute
            for bone in obj.pose.bones
            for c in bone.constraints
        )

        # Determine target state (True = enable, False = disable)
        enable = not any_enabled
        count = 0

        # Toggle constraints
        for bone in obj.pose.bones:
            for c in bone.constraints:
                if c.type in {'COPY_ROTATION', 'COPY_LOCATION'}:
                    c.mute = not enable
                    count += 1

        state = "enabled" if enable else "disabled"
        self.report({'INFO'}, f"{count} Copy constraints {state}.")
        return {'FINISHED'}
    


class HideSkeleton(bpy.types.Operator):
    bl_idname = "object.hide_skeleton"
    bl_label = "Hide or Unhide Skeleton"
    bl_description = "Hides or Unhides Bones or Empties of Skeleton"

    collection_name: bpy.props.StringProperty()
    #collection_name = "PoseEmpties", "PoseSkeleton", "RightHandEmpties", "RightHandSkeleton", "LeftHandEmpties", "LeftHandSkeleton" 

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection_name)
        if collection:
            for obj in collection.objects:
                obj.hide_set(not obj.hide_get())
        return {'FINISHED'}



classes = [StartTracking, StopTracking, CombineMotionData, AnimatePose, AnimateHand, BakeMotion,
           ClearMoCapCache, VideoSelect,  ClearVideoPath, ToggleCopyRotationConstraints, HideSkeleton]