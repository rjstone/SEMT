# Space Engineers Mod Tools Addon for Blender 2.71
# by NimrodX
# 9/20/2014
# This is a work in progress. Please do not redistribute. This will be distributed as a proper blender
# addon module once I receive some feedback and more testing is done.

import bpy, os, subprocess
from bpy import ops
from bpy.props import *
from bpy.types import PropertyGroup

import export_fbx_patch


def update_export_fbx_patch(self, context):
    if context.scene.world.semt.patch_fbx:
        export_fbx_patch.patch()
    else:
        export_fbx_patch.unpatch()

def update_use_trackball(self, context):
    if context.scene.world.semt.use_trackball:
        context.user_preferences.inputs.ndof_view_rotate_method = 'TRACKBALL'
    else:
        context.user_preferences.inputs.ndof_view_rotate_method = 'TURNTABLE'

class SE_Props(PropertyGroup):
    se_dir = StringProperty(name="Game Path",
                description="Space Engineers Base Directory: This is used to find MWMBUILDER.exe",
                subtype="DIR_PATH")
    mod_dir = StringProperty(name="Mod Path",
                description="Base directory for your entire mod, not the models subdirectory!",
                subtype="DIR_PATH")
    axis_switch = BoolProperty(name="Attempt Blender to game axis conversion",
                description="Please leave this disabled unless you know what you're doing and have read the discussion on it.")
    save_xml = BoolProperty(name="Autosave MWM XML files before building",
                description="Automatically save all text blocks with filenames ending in '.xml' before running mwmbuilder. SBC files will NOT be saved.")
    batch_dirs = BoolProperty(name="Export one directory per model",
                description="Save each model in its own subdirectory of Models. Otherwise they will all be saved directly to the Models directory.")
    patch_fbx = BoolProperty(name="Apply FBX Exporter Fixes/Modifications",
                description="Activate code patches to customize FBX export for the game. Don't disable this unless you're troubleshooting.",
                update=update_export_fbx_patch)
    use_trackball = BoolProperty(name='Use "Trackball" rotation in 3D editor',
                description="Use trackball-style rotation in the 3D editor instead of turntable-style."
                            "  This is better for the non-standard axis orientation."
                            "  If you set this here, it doesn't need to be saved to your global user preferences.",
                            update=update_use_trackball)
    status = StringProperty(name="Last result",
                description="Result of last operation attempt (success, fail, etc).")


# stuff for eventually adding a "new from template" File menu item
# bpy.ops.wm.read_homefile(filepath="", load_ui=True)
# bpy.types.INFO_MT_file.prepend()
# bpy.types.INFO_MT_file.append()


class SE_FBX_Export(bpy.types.Operator):
    bl_idname = "world.se_fbx_export"
    bl_label = "Space Engineers FBX Export"
    bl_description = "Export FBX files for Space Engineers (KSH VRAGE)"
    
    def execute(self, context):
        self.report({'INFO'}, "Exporting all object groups as FBX files...")
        semt = context.scene.world.semt
        mod_dir = bpy.path.abspath(context.scene.world.semt.mod_dir)
        modelspath = os.path.join(mod_dir, "Models") + os.sep
        if not os.path.exists(modelspath):
            os.makedirs(modelspath)
        self.report({'DEBUG'}, "Exporting to " + modelspath)

        semt.status = "FBX export FAILED."   

        # I don't fully understand what's going on here yet, but Nilat says -X forward seems to work for
        # some reason, at least in 2.71.        
        if semt.axis_switch:
            self.report({'DEBUG'}, "Using Y up -X forward workaround (which seems to actually make -Z forward).")
            axis_forward='-X'
            axis_up='Y'
        else:
            self.report({'DEBUG'}, "Using Z up Y forward (Blender default).")
            axis_forward='Y'
            axis_up='Z'

        bpy.ops.export_scene.fbx(
                filepath=modelspath,
                batch_mode='GROUP',
                use_batch_own_dir=semt.batch_dirs,
                version='ASCII6100',
                use_selection=False,
                object_types={'EMPTY', 'ARMATURE', 'MESH'},
                axis_forward=axis_forward,
                axis_up=axis_up,
                # was previously scaling by 100, but this is not really needed if you set up Havok right
                global_scale=1
                )

        semt.status = "FBX export completed."
        self.report({'INFO'}, "FBX export completed.")              
        return {'FINISHED'}


class SE_MWM_Build(bpy.types.Operator):
    bl_idname = "world.se_mwm_build"
    bl_label = "Space Engineers MWM Build"
    bl_description = "Run MWMBuilder.exe on exported FBX files."
    
    def execute(self, context):
        semt = context.scene.world.semt
        se_dir = bpy.path.abspath(semt.se_dir)
        mwmbuilder_path = os.path.join(se_dir, "Tools", "mwmbuilder.exe")
        models_path = os.path.join(semt.mod_dir, "Models")
        
        if semt.save_xml:
            self.report({'INFO'}, "Saving XML text blocks...")
            context_or = bpy.context.copy()
            for text in bpy.data.texts:
                if text.name.endswith(".xml"):
                    context_or['edit_text'] = text
                    bpy.ops.text.save(context_or)                    
        
        self.report({'INFO'}, "Running MWMBuilder on " + models_path)

        logfile = os.path.join(models_path, "mwmbuilder.log")
        mwmbuilder = subprocess.Popen([mwmbuilder_path, "/s:" + models_path, "/f", "/l:" + logfile])
        stdoutdata, stderrdata = mwmbuilder.communicate()
        if stdoutdata: print("stdout\n" + stdoutdata)
        if stderrdata: print("stderr\n" + stderrdata)

        if mwmbuilder.returncode == 0:
            semt.status = "MWMBuilder finished successfully."
            self.report({'INFO'}, "MWMBuilder finished successfully.")
        else:
            semt.status = "MWMBuilder failed. See log file."
            self.report({'ERROR'}, "MWMBuilder failed. See mwmbuilder.log in Models and system console.")
        
        return {'FINISHED'}


class SpaceEngineersExportPanel(bpy.types.Panel):
    """Export and build panel in the Scene properties tab"""
    bl_label = "Space Engineers Export"
    bl_idname = "SCENE_SE_Export_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_default_closed = False
    
    def draw(self, context):
        layout = self.layout
        world = context.scene.world
        semt = world.semt # space engineers properties

        # configuration options area
        row = layout.row(align=True)
        row.prop(semt, "se_dir")
        row = layout.row(align=True)
        row.prop(semt, "mod_dir")
        row = layout.row(align=True)
        row.prop(semt, "use_trackball")

        row = layout.row(align=True)
        row.prop(semt, "axis_switch")
        row = layout.row(align=True)
        row.prop(semt, "save_xml")        
        row = layout.row(align=True)
        row.prop(semt, "batch_dirs")
        row = layout.row()
        row.prop(semt, "patch_fbx")
        # operator execution area
        box = layout.box()
        row = box.row()
        row.label(text="Last result: " + world.semt.status)
        row = box.row(align=True)
        row.operator("world.se_fbx_export", text="Export FBX Files")
        sub = row.row()
        sub.operator("world.se_mwm_build", text="Build MWM Files")


def register():
    register_class = bpy.utils.register_class
    register_class(SE_Props)
    register_class(SE_FBX_Export)
    register_class(SE_MWM_Build)
    register_class(SpaceEngineersExportPanel)

    bpy.types.World.semt = PointerProperty(name="Space Engineers", description="Space Engineers Export Parametrs", type=SE_Props)
    
    update_export_fbx_patch(None, bpy.context)
    update_use_trackball(None, bpy.context)
    
    # There doesn't seem to be a very good way to fix this right now, so I'm just forcing it to hidden
    # in order to avoid confusion.
    bpy.context.user_preferences.view.show_view_name = False
    
    bpy.context.scene.world.semt.status = "Addon loaded and registered."
    
def unregister():
    unregister_class = bpy.utils.unregister_class
    unregister_class(SE_Props)
    unregister_class(SE_FBX_Export)
    unregister_class(SE_MWM_Build)
    unregister_class(SpaceEngineersExportPanel)
    
    export_fbx_patch.unpatch()

    del bpy.types.World.semt
    
#if __name__ == "__main__":
register()
