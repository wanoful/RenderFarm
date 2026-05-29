import base64
import json
import os
import tempfile
import zipfile
from pathlib import Path
from urllib import request, error

import bpy


def _auth_header() -> str:
    prefs = bpy.context.preferences.addons[__package__].preferences
    creds = f"{prefs.username}:{prefs.password}"
    encoded = base64.b64encode(creds.encode()).decode()
    return f"Basic {encoded}"


def _server() -> str:
    prefs = bpy.context.preferences.addons[__package__].preferences
    return prefs.server_url.rstrip("/")


def _call(method: str, path: str, body=None, files=None, timeout=120):
    url = f"{_server()}{path}"
    req = request.Request(url, method=method)
    req.add_header("Authorization", _auth_header())

    if method in ("GET", "DELETE"):
        pass
    elif files:
        boundary = "----RenderFarmBoundary"
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        body_bytes = bytearray()
        for key, val in body.items():
            body_bytes += f"--{boundary}\r\n".encode()
            body_bytes += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            body_bytes += val.encode()
            body_bytes += b"\r\n"
        for key, (filename, data) in files.items():
            body_bytes += f"--{boundary}\r\n".encode()
            body_bytes += (
                f'Content-Disposition: form-data; name="{key}"; '
                f'filename="{filename}"\r\n\r\n'
            ).encode()
            body_bytes += data
            body_bytes += b"\r\n"
        body_bytes += f"--{boundary}--\r\n".encode()
        req.data = body_bytes
    elif body:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()

    resp = request.urlopen(req, timeout=timeout)
    data = resp.read().decode()
    return resp.status, data


def _active_job_id(scene) -> str:
    idx = scene.renderfarm_job_index
    if 0 <= idx < len(scene.renderfarm_job_items):
        return scene.renderfarm_job_items[idx].uid
    return ""


class RENDERFARM_OT_submit(bpy.types.Operator):
    bl_idname = "renderfarm.submit"
    bl_label = "Submit to Wano's Render Farm"
    bl_description = "Pack and submit the current file to the render farm"
    bl_options = {"REGISTER"}

    job_name: bpy.props.StringProperty(name="Job Name", default="")

    def invoke(self, context, event):
        if not context.blend_data.filepath:
            self.report({"ERROR"}, "Save your .blend file first")
            return {"CANCELLED"}
        self.job_name = Path(context.blend_data.filepath).stem
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "job_name")
        scene = context.scene
        layout.prop(scene, "frame_start")
        layout.prop(scene, "frame_end")

    def execute(self, context):
        scene = context.scene
        filepath = context.blend_data.filepath
        if not filepath:
            self.report({"ERROR"}, "Save your .blend file first")
            return {"CANCELLED"}

        tmp_path = tempfile.mktemp(suffix=".blend")
        try:
            bpy.ops.wm.save_as_mainfile(filepath=tmp_path, copy=True)
        except Exception as e:
            self.report({"ERROR"}, f"Failed to save: {e}")
            return {"CANCELLED"}

        settings = {
            "name": self.job_name or Path(filepath).stem,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "chunk_size": scene.renderfarm_chunk_size,
            "output_format": scene.render.image_settings.file_format,
        }

        with open(tmp_path, "rb") as f:
            blend_data = f.read()
        os.unlink(tmp_path)

        try:
            status, data = _call(
                "POST",
                "/api/jobs",
                body={"settings": json.dumps(settings)},
                files={"file": (f"{self.job_name}.blend", blend_data)},
            )
        except error.HTTPError as e:
            self.report({"ERROR"}, f"Server error: {e.code}")
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Cannot reach server: {e}")
            return {"CANCELLED"}

        if status == 200:
            self.report({"INFO"}, f"Job '{self.job_name}' submitted")
            bpy.ops.renderfarm.refresh()
        else:
            self.report({"ERROR"}, f"Server error: {status}")

        return {"FINISHED"}


class RENDERFARM_OT_refresh(bpy.types.Operator):
    bl_idname = "renderfarm.refresh"
    bl_label = "Refresh Jobs"
    bl_description = "Refresh the job list from the server"

    def execute(self, context):
        try:
            status, data = _call("GET", "/api/jobs")
        except error.HTTPError as e:
            self.report({"ERROR"}, f"Server error: {e.code}")
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Cannot reach server: {e}")
            return {"CANCELLED"}

        if status == 200:
            context.scene.renderfarm_jobs_json = data
        else:
            self.report({"ERROR"}, f"Server error: {status}")

        return {"FINISHED"}


class RENDERFARM_OT_download(bpy.types.Operator):
    bl_idname = "renderfarm.download"
    bl_label = "Download Output"
    bl_description = "Download rendered output for selected job"

    @classmethod
    def poll(cls, context):
        return len(context.scene.renderfarm_job_items) > 0

    def execute(self, context):
        job_id = _active_job_id(context.scene)
        if not job_id:
            return {"CANCELLED"}

        try:
            url = f"{_server()}/api/jobs/{job_id}/output"
            req = request.Request(url, method="GET")
            req.add_header("Authorization", _auth_header())
            resp = request.urlopen(req, timeout=120)
            data = resp.read()
        except error.HTTPError as e:
            self.report({"ERROR"}, f"No output yet ({e.code})")
            return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Cannot reach server: {e}")
            return {"CANCELLED"}

        out_dir = Path(bpy.path.abspath("//")) / "renderfarm_output" / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = tempfile.mktemp(suffix=".zip")
        with open(tmp_path, "wb") as f:
            f.write(data)

        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(out_dir)
        os.unlink(tmp_path)

        self.report({"INFO"}, f"Saved to {out_dir}")
        return {"FINISHED"}


class RENDERFARM_OT_delete_job(bpy.types.Operator):
    bl_idname = "renderfarm.delete_job"
    bl_label = "Delete Job"
    bl_description = "Cancel (if running) or delete (if finished) the selected job"

    @classmethod
    def poll(cls, context):
        return len(context.scene.renderfarm_job_items) > 0

    def execute(self, context):
        job_id = _active_job_id(context.scene)
        if not job_id:
            return {"CANCELLED"}

        try:
            status, data = _call("DELETE", f"/api/jobs/{job_id}")
        except Exception as e:
            self.report({"ERROR"}, f"Cannot reach server: {e}")
            return {"CANCELLED"}

        if 200 <= status < 300:
            result = json.loads(data)
            self.report({"INFO"}, f"Job {result['status']}")
            bpy.ops.renderfarm.refresh()
        else:
            self.report({"ERROR"}, f"Error: {status}")

        return {"FINISHED"}


_classes = (
    RENDERFARM_OT_submit,
    RENDERFARM_OT_refresh,
    RENDERFARM_OT_download,
    RENDERFARM_OT_delete_job,
)


def register():
    bpy.types.Scene.renderfarm_chunk_size = bpy.props.IntProperty(
        name="Chunk Size", default=3, min=1, max=1000,
    )
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in _classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.renderfarm_chunk_size
