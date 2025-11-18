bl_info = {
    "name": "Open Mocap",
    "author": "Larenju Rai",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Tools",
    "doc_url": "https://github.com/Larenju-Rai/open-mocap-blender",
    "category": "Animation",
}



import bpy
from . import PackageInstaller, operators, panels

classes = PackageInstaller.classes + operators.classes + panels.classes



def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.num_hands = bpy.props.IntProperty(
        name="Number of Hands",
        description="Set number of hands to track (1 or 2)",
        default=2,
        min=1,
        max=2
    )
    bpy.types.Scene.cam_index = bpy.props.IntProperty(
        name="Camera Index",
        description="Choose a camera. Index 0 means primary webcam.",
        default=0,
        min=0,
        max=5
    )
    bpy.types.Scene.bake_rig = bpy.props.PointerProperty(
        name="Rig",
        type=bpy.types.Object,
        description="Choose the armature to bake",
        poll=lambda self, obj: obj.type == 'ARMATURE'
    )
    bpy.types.Scene.bake_frame_start = bpy.props.IntProperty(name="Start Frame", default=1, min = 1)
    bpy.types.Scene.bake_frame_end = bpy.props.IntProperty(name="End Frame", default=250, min = 1)
    bpy.types.Scene.bake_only_selected = bpy.props.BoolProperty(name="Only Selected Bones", default=False)
    bpy.types.Scene.multi_view_tracking = bpy.props.BoolProperty(name="Multi View Tracking", default=False)
    bpy.types.Scene.realtime_tracking = bpy.props.BoolProperty(name="Realtime Tracking", default=False)



def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.num_hands
    del bpy.types.Scene.cam_index
    del bpy.types.Scene.bake_rig
    del bpy.types.Scene.bake_frame_start
    del bpy.types.Scene.bake_frame_end
    del bpy.types.Scene.bake_only_selected
    del bpy.types.Scene.multi_view_tracking
    del bpy.types.Scene.realtime_tracking



if __name__ == "__main__":
    register()
