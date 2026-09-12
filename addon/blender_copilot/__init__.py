bl_info = {
    "name": "Blender Copilot Bridge",
    "author": "Momin Aldahdouh",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > Copilot",
    "description": "Exposes Blender to AI copilots over a local MCP bridge",
    "category": "Development",
}

import bpy

from . import executor, server


class COPILOT_PT_panel(bpy.types.Panel):
    bl_label = "Copilot Bridge"
    bl_idname = "COPILOT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Copilot"

    def draw(self, context):
        layout = self.layout
        running = server._server is not None
        row = layout.row()
        row.label(text="Running" if running else "Stopped",
                  icon="PLAY" if running else "PAUSE")
        if running:
            layout.label(text=f"{server.HOST}:{server.PORT}")
            layout.operator("copilot.stop", icon="X")
        else:
            layout.operator("copilot.start", icon="PLAY")


class COPILOT_OT_start(bpy.types.Operator):
    bl_idname = "copilot.start"
    bl_label = "Start Bridge"

    def execute(self, context):
        server.start()
        return {"FINISHED"}


class COPILOT_OT_stop(bpy.types.Operator):
    bl_idname = "copilot.stop"
    bl_label = "Stop Bridge"

    def execute(self, context):
        server.stop()
        return {"FINISHED"}


_classes = (COPILOT_PT_panel, COPILOT_OT_start, COPILOT_OT_stop)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    server.start()


def unregister():
    server.stop()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
