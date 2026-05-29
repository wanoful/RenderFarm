import bpy


class RenderFarmPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    server_url: bpy.props.StringProperty(
        name="Server URL",
        description="RenderFarm server URL",
        default="http://127.0.0.1:8000",
    )
    username: bpy.props.StringProperty(
        name="Username",
        description="Your RenderFarm username",
        default="",
    )
    password: bpy.props.StringProperty(
        name="Password",
        description="Your RenderFarm password",
        default="",
        subtype="PASSWORD",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "server_url")
        layout.prop(self, "username")
        layout.prop(self, "password")


def register():
    bpy.utils.register_class(RenderFarmPreferences)


def unregister():
    bpy.utils.unregister_class(RenderFarmPreferences)
