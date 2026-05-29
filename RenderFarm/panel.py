import json

import bpy


def _get_jobs(context) -> list[dict]:
    try:
        return json.loads(context.scene.renderfarm_jobs_json)
    except (json.JSONDecodeError, Exception):
        return []


STATUS_ICONS = {
    "pending": "TIME",
    "running": "PLAY",
    "completed": "CHECKMARK",
    "failed": "ERROR",
    "cancelled": "X",
}


class RENDERFARM_UL_jobs(bpy.types.UIList):
    bl_idname = "RENDERFARM_UL_jobs"

    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            pct = ""
            total = item.frames_total
            done = item.frames_done
            if total:
                pct = f" {100 * done // total}%"
            icon = STATUS_ICONS.get(item.state, "QUESTION")
            layout.label(
                text=f"{item.label} [{item.state}{pct}]",
                icon=icon,
            )


class RenderFarmJobItem(bpy.types.PropertyGroup):
    uid: bpy.props.StringProperty()
    label: bpy.props.StringProperty()
    state: bpy.props.StringProperty()
    frames_total: bpy.props.IntProperty()
    frames_done: bpy.props.IntProperty()


class RENDERFARM_PT_main(bpy.types.Panel):
    bl_label = "Wano's Render Farm"
    bl_idname = "RENDERFARM_PT_main"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        prefs = context.preferences.addons[__package__].preferences

        box = layout.box()
        row = box.row()
        row.label(text="Server:", icon="URL")
        row.label(text=prefs.server_url or "Not configured")

        row = layout.row(align=True)
        row.scale_y = 1.5
        op = row.operator("renderfarm.submit", icon="EXPORT", text="Submit to Wano's Farm")
        row.operator("renderfarm.refresh", icon="FILE_REFRESH", text="")

        layout.separator()

        jobs = _get_jobs(context)
        if not jobs:
            layout.label(text="No jobs submitted yet", icon="INFO")
            return

        layout.label(text=f"Jobs ({len(jobs)})", icon="RENDER_RESULT")

        row = layout.row()
        row.template_list(
            "RENDERFARM_UL_jobs", "",
            scene, "renderfarm_job_items",
            scene, "renderfarm_job_index",
            rows=6,
        )

        layout.separator()

        row = layout.row(align=True)
        row.operator("renderfarm.download", icon="IMPORT")
        row.operator("renderfarm.open_output_dir", icon="FILE_FOLDER")
        row.operator("renderfarm.delete_job", icon="TRASH")


def _sync_job_items(scene):
    jobs = json.loads(scene.renderfarm_jobs_json)
    items = scene.renderfarm_job_items
    items.clear()
    for job in jobs:
        item = items.add()
        item.uid = job["id"]
        item.label = job["name"]
        item.state = job["status"]
        item.frames_total = job.get("total_frames", 0)
        item.frames_done = job.get("rendered_frames", 0)


def _on_jobs_json_update(self, context):
    _sync_job_items(context.scene)


_classes = (RENDERFARM_UL_jobs, RenderFarmJobItem, RENDERFARM_PT_main)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.renderfarm_job_items = bpy.props.CollectionProperty(
        type=RenderFarmJobItem,
    )
    bpy.types.Scene.renderfarm_job_index = bpy.props.IntProperty(
        default=0,
    )
    bpy.types.Scene.renderfarm_jobs_json = bpy.props.StringProperty(
        name="Jobs JSON",
        default="[]",
        update=_on_jobs_json_update,
    )


def unregister():
    for cls in _classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.renderfarm_job_items
    del bpy.types.Scene.renderfarm_job_index
    del bpy.types.Scene.renderfarm_jobs_json
