bl_info = {
    "name": "RenderFarm",
    "author": "RenderFarm",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Output Properties > RenderFarm",
    "description": "Submit renders to the RenderFarm server",
    "category": "Render",
}


def register():
    from . import preferences
    from . import operators
    from . import panel

    preferences.register()
    operators.register()
    panel.register()


def unregister():
    from . import preferences
    from . import operators
    from . import panel

    preferences.unregister()
    operators.unregister()
    panel.unregister()
