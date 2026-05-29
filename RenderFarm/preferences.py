import bpy


class RenderFarmPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    server_url: bpy.props.StringProperty(
        name="Server URL",
        description="Wano's Render Farm server URL",
        default="http://127.0.0.1:8000",
    )
    username: bpy.props.StringProperty(
        name="Username",
        description="Your Wano's Render Farm username",
        default="",
    )
    password: bpy.props.StringProperty(
        name="Password",
        description="Your Wano's Render Farm password",
        default="",
        subtype="PASSWORD",
    )
    output_dir: bpy.props.StringProperty(
        name="Output Directory",
        description="Directory to save downloaded renders (blank = next to .blend file)",
        default="",
        subtype="DIR_PATH",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "server_url")
        layout.prop(self, "username")
        layout.prop(self, "password")
        layout.prop(self, "output_dir")


def register():
    bpy.utils.register_class(RenderFarmPreferences)


def unregister():
    bpy.utils.unregister_class(RenderFarmPreferences)
