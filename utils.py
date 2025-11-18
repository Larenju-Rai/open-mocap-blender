import bpy
import numpy as np
from . import globalVariables as gvar



# -------------------------------------------------------------
# IMPORTING EXTERNAL LIBRARIES
# -------------------------------------------------------------
try:
    import cv2
    from cvzone.PoseModule import PoseDetector
    from cvzone.HandTrackingModule import HandDetector
except ModuleNotFoundError:
    cv2 = None
    PoseDetector = None
    HandDetector = None



# -------------------------------------------------------------
# SOME USEFUL MATH UTILITIES
# -------------------------------------------------------------
class MathUtility:
    @staticmethod
    def centroid(list_of_points):
        """
            :param list_of_points: List of points whose centroid is to be calculated.
            :return: Centroid of the points in the list.
        """
        avg_x = sum(p[0] for p in list_of_points) / len(list_of_points)
        avg_y = sum(p[1] for p in list_of_points) / len(list_of_points)
        avg_z = sum(p[2] for p in list_of_points) / len(list_of_points)
        return [avg_x,avg_y,avg_z]
    
    @staticmethod
    def normalize_coordinates(coordinates,height,width,scale):
        """
            :param coordinates: Original [x,y,z] (Unnormalized)
            :param height: Height of the video. 
            :param width: Width of the video.
            :param scale: Scales z to cover up for inaccuracy in z value tracked by the tracker.
            :return: Normalized [x,y,z] 
        """
        x = (coordinates[0] - (width/2))/100 #centre x
        y = (coordinates[1]-height)/100 #translate y up
        z = coordinates[2]/scale
        return [x,y,z]
    
    @staticmethod
    def cv2blender_coordinates(cv_coordinates):
        """
            :param cv_coordinates: [x,y,z] as per Opencv's convention.
            :return: [x,y,z] as per Blender's convention.
        """
        x = cv_coordinates[0]       #blender.x = cv2.x
        y = cv_coordinates[2]       #blender.y = cv2.z
        z = -cv_coordinates[1]      #blender.z = cv2.(-y)
        return [x,y,z]



# -------------------------------------------------------------
# SOME USEFUL BLENDER UTILITIES
# -------------------------------------------------------------
class BlenderUtility:   
    @staticmethod
    def create_collection(context,Name):
        collection_name = Name
        """
            Creates collections, with a given name, in the Blender's Outliner.
            :param collection_name: Name of the collection.
        """
        if collection_name in bpy.data.collections:
            named_collection = bpy.data.collections[collection_name]
        else:
            named_collection = bpy.data.collections.new(collection_name)
            context.scene.collection.children.link(named_collection)
        return named_collection
    


# -------------------------------------------------------------
# SOME CUSTOM UTILITIES
# -------------------------------------------------------------
class VideoPlaneManager:
    plane_obj = None
    image = None
    """
        Creates a plane object in Blender scene to display reatime tracking video.
        :param plane_obj: The plane object created for displaying.
        :param image: Frame from the video to be displayed in the plane.
    """

    @classmethod
    def create_plane(cls, context, width=640, height=480):
        cls.width, cls.height = width, height
        aspect_ratio = width / height

        """
            :param width: Width of the video stream. (Default = 640)
            :param height: Height of the video stream. (Default = 480)
        """

        # Remove old plane if exists
        if cls.plane_obj and cls.plane_obj.name in bpy.data.objects:
            bpy.data.objects.remove(cls.plane_obj, do_unlink=True)
            cls.plane_obj = None

        # Remove old image if exists
        if "CameraFeed" in bpy.data.images:
            bpy.data.images.remove(bpy.data.images["CameraFeed"], do_unlink=True)

        cls.image = bpy.data.images.new(
            "CameraFeed", width=width, height=height, alpha=True, float_buffer=False
        )

        # Create material with image texture
        mat = bpy.data.materials.new("CameraFeed_Mat")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        for n in list(nodes):
            nodes.remove(n)

        tex_image = nodes.new("ShaderNodeTexImage")
        tex_image.image = cls.image
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        output = nodes.new("ShaderNodeOutputMaterial")
        links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
        links.new(tex_image.outputs["Color"], bsdf.inputs["Base Color"])


        # Create plane and apply material
        bpy.ops.mesh.primitive_plane_add(size=4)
        cls.plane_obj = context.active_object
        cls.plane_obj.name = "VideoPlane"
        cls.plane_obj.data.materials.append(mat)
        cls.plane_obj.scale.x = aspect_ratio * 2
        cls.plane_obj.scale.y = 2
        cls.plane_obj.location.z += 2
        cls.plane_obj.location.y += 6
        #cls.plane_obj.location.x += 6
        cls.plane_obj.scale *= 0.5
        cls.plane_obj.rotation_euler[0] = np.radians(90)

        # Set 3D view to Material mode
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces[0].shading.type = 'MATERIAL'

        # Setup scene view transform and look
        bpy.context.scene.view_settings.view_transform = 'Standard'
        bpy.context.scene.view_settings.look = 'Medium High Contrast'
        
        print("Video plane ready for realtime feed.")
        return cls.plane_obj
    
    @classmethod
    def remove_plane(cls):
        """Cleanly remove the video plane and image."""
        if cls.plane_obj and cls.plane_obj.name in bpy.data.objects:
            bpy.data.objects.remove(cls.plane_obj, do_unlink=True)
            cls.plane_obj = None

        if "CameraFeed" in bpy.data.images:
            bpy.data.images.remove(bpy.data.images["CameraFeed"], do_unlink=True)

        print("Video plane removed.")

    @classmethod
    def update_frame(cls, frame):
        """:param image: Frame from the video to be displayed in the plane."""

        if cv2 is None:
            print("OpenCV is not installed. Cannot update video plane.")
            return
        
        if cls.image is None:
            return
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb = np.flipud(frame_rgb)

        h, w, _ = frame_rgb.shape
        rgba = np.concatenate(
            [frame_rgb, np.ones((h, w, 1), dtype=np.uint8) * 255], axis=2
        ).astype(np.float32).ravel() / 255.0

        if cls.image.size[0] != w or cls.image.size[1] != h:
            cls.image.scale(w, h)

        cls.image.pixels.foreach_set(rgba)
        cls.image.update()



# -------------------------------------------------------------
# POSE TRACKING UTILITY
# -------------------------------------------------------------
class PoseTracking:
    def __init__(self, mode):
        self.detector = None
        self.mode = mode
        self.running = False
        """
            It uses cvzone.PoseModule (uses mediapipe) to do pose tracking.
        """
        if cv2 is None:
            print("OpenCV (cv2) is not installed! Install via the Addon Preferences first.")
            return

        # Determine video path or realtime mode
        if self.mode == "front_pose":
            self.path = gvar.front_video_path
        elif self.mode == "side_pose":
            self.path = gvar.side_video_path
        else:
            self.path = "" 

        # --- Handle realtime webcam tracking ---
        if self.mode == "rt_pose":
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("Failed to open camera.")
                return

            gvar.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not gvar.fps or gvar.fps <= 0:
                gvar.fps = 30
            gvar.delay = 1.0 / gvar.fps

            # Create video plane for live feed
            width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            VideoPlaneManager.create_plane(bpy.context, width=width, height=height)

            # Start playback
            if not bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()

            self.running = True
            bpy.app.timers.register(self.update_frame, first_interval=0.0)
            print("Realtime pose tracking started.")
            return

        # --- Handle video-based tracking ---
        if self.path:
            self.cap = cv2.VideoCapture(self.path)
            gvar.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not gvar.fps or gvar.fps <= 0:
                gvar.fps = 30
            gvar.delay = 1.0 / gvar.fps

            # Create OpenCV window
            cv2.namedWindow("Pose Tracking", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Pose Tracking", 640, 480)
            cv2.moveWindow("Pose Tracking", 0, 0)

            self.running = True
            bpy.app.timers.register(self.update_frame, first_interval=0.0)
            print("Pose tracking started.")

    def detect_pose(self, img):
        """
            :param img: Image on which pose dectection is to be performed.
            :return: Image with pose landmarks and lines connecting the landmarks drawn on it.
        """
        if PoseDetector is None:
            print("cvzone.PoseModule not installed. Install via the Addon Preferences first. Skipping pose detection.")
            return img
        
        if self.detector is None:
            self.detector = PoseDetector()

        img = self.detector.findPose(img)
        height, width = img.shape[:2]
        landmarksList, boundingBoxInfo = self.detector.findPosition(img)

        if not boundingBoxInfo:
            return img

        # --- Calculate custom points (centroids) ---
        point_pairs = [
            (23, 24),  # hips           (point 32)
            (11, 12),  # shoulders      (point 33)
            (18, 20),  # right hand     (point 34)
            (17, 19),  # left hand      (point 35)
            (7, 8),    # ears           (point 36)
            (9, 10),   # mouth          (point 37)
            (1, 4)     # eyes           (point 38)
        ]

        extra_points = []
        for a, b in point_pairs:
            centroid = MathUtility.centroid([landmarksList[a], landmarksList[b]])
            normalized = MathUtility.normalize_coordinates(centroid, height, width, 400)
            extra_points.append(normalized)

        # --- Handle mode: front, side, or realtime ---
        if self.mode in ["front_pose", "rt_pose"]:
            listOf32Landmarks = []
            for landmark in landmarksList:
                normalized = MathUtility.normalize_coordinates(landmark, height, width, 400)
                listOf32Landmarks.extend(normalized)

            for point in extra_points:
                listOf32Landmarks.extend(point)

            gvar.positionList.append(listOf32Landmarks)

        elif self.mode == "side_pose" and gvar.positionList:
            zframe = []
            for landmark in landmarksList:
                normalized = MathUtility.normalize_coordinates(landmark, height, width, 400)
                zframe.extend(normalized)

            for point in extra_points:
                zframe.extend(point)

            gvar.zlist.append(zframe)

        return img

    def update_frame(self):
        """Updates the image in the CV window or Plane in the Blender Scene."""

        if cv2 is None:
            print("OpenCV (cv2) is not installed! Install via the Addon Preferences first.")
            return
        
        if not self.running or not self.cap.isOpened():
            self.stop()
            return None

        # Stop if the window was closed (for non-realtime)
        if self.mode != "rt_pose":
            if cv2.getWindowProperty("Pose Tracking", cv2.WND_PROP_VISIBLE) < 1:
                self.stop()
                return None

        success, img = self.cap.read()
        if not success:
            self.stop()
            return None

        img = self.detect_pose(img)

        # --- Realtime: show on video plane ---
        if self.mode == "rt_pose":
            VideoPlaneManager.update_frame(img)
        else:
            # --- Video file: show in OpenCV window ---
            cv2.imshow("Pose Tracking", img)
            cv2.waitKey(1)

        return gvar.delay

    def stop(self):
        """Stops pose tracking."""
        if self.running:
            print("Pose tracking stopped.")
        self.running = False

        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

        if self.mode == "rt_pose":
            VideoPlaneManager.remove_plane()
        else:
            try:
                cv2.destroyWindow("Pose Tracking")
            except:
                pass

        # Stop animation playback if running
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()

        return None



# -------------------------------------------------------------
# HAND TRACKING UTILITY
# -------------------------------------------------------------
class HandTracking:
    def __init__(self, num_hands, mode):
        self.detector = None
        self.num_hands = num_hands
        self.mode = mode
        self.running = False
        """
            It uses cvzone.HandTrackingModule (uses mediapipe) to do hand tracking.
            :param num_hands: Numbers of hands to track (1 or 2).
            :param mode: Different modes like realtime, offline: (front view / side view).
        """

        if cv2 is None:
            print("OpenCV (cv2) is not installed! Install via the Addon Preferences first.")
            return

        # ---- Realtime Hand Tracking Mode ----
        if self.mode == "rt_hand":
            self.cap = cv2.VideoCapture(bpy.context.scene.cam_index)
            if not self.cap.isOpened():
                print("Camera failed to open.")
                return
            gvar.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not gvar.fps or gvar.fps <= 0:
                gvar.fps = 30
            gvar.delay = 1.0 / gvar.fps
            self.running = True
            # Create video plane for live feed
            width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            VideoPlaneManager.create_plane(bpy.context, width=width, height=height)

        # ---- Offline Video Modes (front_hand / side_hand) ----
        if self.mode == "front_hand":
            self.path = gvar.hand_front_video_path
        elif self.mode == "side_hand":
            self.path = gvar.hand_side_video_path
        else:
            self.path = ""

        if self.path:
            self.cap = cv2.VideoCapture(self.path)
            gvar.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not gvar.fps or gvar.fps <= 0:
                gvar.fps = 30
            gvar.delay = 1.0 / gvar.fps
            cv2.namedWindow("Hand Tracking", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Hand Tracking", 640, 480)
            cv2.moveWindow("Hand Tracking", 0, 0)
            self.running = True
            bpy.app.timers.register(self.update_frame, first_interval=0.0)

    def detect_hand(self, img):
        """
            :param img: Image on which hand dectection is to be performed.
            :return: Image with hand landmarks and lines connecting the landmarks drawn on it.
        """
        
        if HandDetector is None:
            print("cvzone.HandTrackingModule not installed. Install via the Addon Preferences first. Skipping hand detection.")
            return img
        
        if self.detector is None:
            self.detector = HandDetector(maxHands=self.num_hands, detectionCon=0.8)

        height, width = img.shape[:2]
        hands, img = self.detector.findHands(img)
        if not hands:
            return img

        for hand in hands:
            handType = hand['type']  # 'Right' or 'Left'
            landmarksList = hand['lmList']
            if handType == "Right":
                position_list = gvar.R_hand_positionList
                z_list = gvar.R_hand_zlist
                rt_hand_lmlist = gvar.rt_hand_lmlist_R

            else:
                position_list = gvar.L_hand_positionList
                z_list = gvar.L_hand_zlist
                rt_hand_lmlist = gvar.rt_hand_lmlist_L

            normalized_landmarks = []
            for landmark in landmarksList:
                normalized = MathUtility.normalize_coordinates(landmark, height, width, 40)
                normalized_landmarks.append(normalized)

            if self.mode in ["front_hand", "rt_hand"]:
                flat_list = []
                rt_hand_lmlist.clear()
                for normalized in normalized_landmarks:
                    rt_hand_lmlist.append(normalized)
                    flat_list.extend(normalized)
                position_list.append(flat_list)

            elif self.mode == "side_hand" and position_list:
                zframe = []
                for normalized in normalized_landmarks:
                    zframe.extend(normalized)
                z_list.append(zframe)

        return img

    def update_frame(self):
        """Updates the image in the CV window."""

        if cv2 is None:
            print("OpenCV (cv2) is not installed! Install via the Addon Preferences first.")
            return

        if not self.running or not self.cap.isOpened():
            self.stop()
            return None

        # Stop if CV window closed
        if self.mode != "rt_hand":
            if cv2.getWindowProperty("Hand Tracking", cv2.WND_PROP_VISIBLE) < 1:
                self.stop()
                return None

        success, img = self.cap.read()
        if not success:
            self.stop()
            return None

        img = self.detect_hand(img)

        cv2.imshow("Hand Tracking", img)
        cv2.waitKey(1)
        return gvar.delay

    def stop(self):
        """Stops hand tracking."""
        if self.running:
            print("Hand tracking stopped.")
        self.running = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        if self.mode != "rt_hand":
            try:
                cv2.destroyWindow("Hand Tracking")
            except:
                pass
        return None



# -----------------------------------------------------------------------
# A CUSTOM UTILITY TO CREATE A VIRTUAL SKELETON FROM TRACKED MOTION DATA
# Custom method developed by the author (Larenju Rai)
# Commonly referred to as "Larenju's Algorithm"
# -----------------------------------------------------------------------
class Skeleton:
    @staticmethod
    def create_skeleton(context, bone_pairs, mode):
        """
        Creates bones.
        Bone = Line (with skin modifier) between specified pair of empties 'empty_a' and 'empty_b'.
        Each bone has a DAMPED_TRACK constraint to its target 'empty_b' with default Y-axis tracking. This is head of the bone.
        Each bone is paranted to other empty: 'empty_a'. This is tail of the bone.
        :param bone_pairs: It is a list of tuples (a,b) where a and b are index of 'empty_a' and 'empty_b'.
        :return: A list of (a, b, obj) tuples for further configuration. obj is the bone object.
        """
        bones_created = []

        for a, b in bone_pairs:
            if mode == "pose":
                empty_a = gvar.object_list[a]
                empty_b = gvar.object_list[b]
                bone_list = gvar.bones_list
                # --- Get or create collection ---
                skeleton_collection = BlenderUtility.create_collection(context,"PoseSkeleton")
            elif mode == "R_hand":
                empty_a = gvar.R_hand_object_list[a]
                empty_b = gvar.R_hand_object_list[b]
                bone_list = gvar.R_hand_bones_list
                # --- Get or create collection ---
                skeleton_collection = BlenderUtility.create_collection(context,"RightHandSkeleton")
            else:
                empty_a = gvar.L_hand_object_list[a]
                empty_b = gvar.L_hand_object_list[b]
                bone_list = gvar.L_hand_bones_list
                # --- Get or create collection ---
                skeleton_collection = BlenderUtility.create_collection(context,"LeftHandSkeleton")
            loc_a = empty_a.matrix_world.translation
            loc_b = empty_b.matrix_world.translation

            # --- Create cube and extrude towards target ---
            bpy.ops.mesh.primitive_cube_add(size=1, location=loc_a)
            obj = context.active_object
            skeleton_collection.objects.link(obj)
            obj.name = f"hand_bone_{a}_{b}"

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.merge(type='CENTER')

            dir_vec = loc_b - loc_a
            bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": dir_vec})
            bpy.ops.object.mode_set(mode='OBJECT')

            # --- Hook tip vertex to target empty ---
            mesh = obj.data
            verts = [v.co.copy() for v in mesh.vertices]
            tip_index = max(range(len(verts)), key=lambda i: (verts[i] - loc_a).length)

            obj.parent = empty_a
            hook = obj.modifiers.new("HookToB", 'HOOK')
            hook.object = empty_b
            hook.vertex_indices_set([tip_index])

            # --- Add modifiers ---
            skin = obj.modifiers.new("Skin", 'SKIN')
            skin.use_smooth_shade = True
            subsurf = obj.modifiers.new("Subdivision", 'SUBSURF')
            subsurf.levels = 2

            # Resize skin
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.transform.skin_resize(value=(0.3, 0.3, 0.3))
            bpy.ops.object.mode_set(mode='OBJECT')

            # --- Add default DAMPED_TRACK constraint (Y-axis) ---
            constraint = obj.constraints.new('DAMPED_TRACK')
            constraint.target = empty_b
            constraint.track_axis = 'TRACK_Y'

            # Record
            bone_list.append(obj)
            bones_created.append((a, b, obj))

        return bones_created
