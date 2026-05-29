bl_info = {
    "name": "Wano's Render Farm",
    "author": "Wano",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Output Properties > Wano's Render Farm",
    "description": "Submit renders to Wano's Render Farm",
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
