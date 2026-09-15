# -------------------------------------------------------------
#  Geneva Mechanism Generator
# -------------------------------------------------------------
import bpy
import bmesh
import math


def _link_mesh_object(context, name, bm):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(obj)
    return obj


def _add_cylinder(context, name, radius, depth, segments, location=(0.0, 0.0, 0.0)):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius,
        radius2=radius,
        depth=depth,
    )
    obj = _link_mesh_object(context, name, bm)
    obj.location = location
    return obj


def _add_cube(context, name, size, location=(0.0, 0.0, 0.0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    obj = _link_mesh_object(context, name, bm)
    obj.location = location
    return obj


def _resolve_solver(name):
    """The Boolean modifier's 'FAST' solver was renamed to 'FLOAT' in
    newer Blender versions. Resolve to whichever name the running
    Blender actually supports."""
    items = bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
    if name in items:
        return name
    if name == 'FAST' and 'FLOAT' in items:
        return 'FLOAT'
    return 'EXACT'


def _apply_boolean(context, target, other, operation, solver):
    """Boolean target with other and bake the result into target's mesh,
    without relying on bpy.ops.object.modifier_add/apply."""
    mod = target.modifiers.new(name="Boolean", type='BOOLEAN')
    mod.operation = operation
    mod.solver = _resolve_solver(solver)
    mod.object = other

    depsgraph = context.evaluated_depsgraph_get()
    eval_obj = target.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(eval_obj)

    old_mesh = target.data
    target.modifiers.remove(mod)
    target.data = new_mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)


def _remove_object(obj):
    if obj is None:
        return
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


# ----------------------------------------------------------------
#  Operator — supplies parameters and runs the script
# ----------------------------------------------------------------
class MESH_OT_geneva_wrapper(bpy.types.Operator):
    bl_idname = "mesh.geneva_mechanism"
    bl_label = "Geneva Mechanism"
    bl_options = {'REGISTER', 'UNDO'}

    # parameters (defaults are the same as in the original code)
    genevaHeight: bpy.props.FloatProperty(default=0.4, name="Height")
    genevaWheelRadius: bpy.props.FloatProperty(default=3.0, name="Wheel Radius")
    genevaWheelSlotQuantity: bpy.props.IntProperty(default=6, name="Wheel Slot Quantity", min=3)
    genevaCrankPinRadius: bpy.props.FloatProperty(default=0.125, name="Crank-Pin Radius")
    allowedClearance: bpy.props.FloatProperty(default=0.05, name="Slot Clearance")
    pinTolerence: bpy.props.FloatProperty(default=0.05, name="Pin Tol.")
    stopDiscTolerence: bpy.props.FloatProperty(default=0.05, name="Stop-Disc Tol.")
    stopDiscCutoutTolerence: bpy.props.FloatProperty(default=0.05, name="Stop-Cutout Tol.")
    baseTolerence: bpy.props.FloatProperty(default=0.05, name="Base Tol.")
    wheelHoleSize: bpy.props.FloatProperty(default=0.25, name="Wheel Hole Radius")
    crankHoleSize: bpy.props.FloatProperty(default=0.25, name="Crank Hole Radius")
    holeTolerence: bpy.props.FloatProperty(default=0.05, name="Hole Tol.")
    vertices: bpy.props.IntProperty(default=128, name="Cylinder Verts", min=3, max=512)

    # ------------------------------------------------------------
    def execute(self, context):
        # remove objects created by a previous run of this operator
        prev_names = context.scene.get("geneva_objects", [])
        for name in prev_names:
            _remove_object(bpy.data.objects.get(name))

        before = set(bpy.data.objects)

        genevaHeight = self.genevaHeight
        genevaWheelRadius = self.genevaWheelRadius
        genevaWheelSlotQuantity = self.genevaWheelSlotQuantity
        genevaCrankPinRadius = self.genevaCrankPinRadius
        allowedClearance = self.allowedClearance
        pinTolerence = self.pinTolerence
        stopDiscTolerence = self.stopDiscTolerence
        stopDiscCutoutTolerence = self.stopDiscCutoutTolerence
        baseTolerence = self.baseTolerence
        wheelHoleSize = self.wheelHoleSize
        crankHoleSize = self.crankHoleSize
        holeTolerence = self.holeTolerence
        vertices = self.vertices

        genevaCrankPinDiameter = genevaCrankPinRadius * 2
        centerDistance = genevaWheelRadius / math.cos(math.pi / genevaWheelSlotQuantity)
        genevaCrankRadius = math.sqrt(centerDistance ** 2 - genevaWheelRadius ** 2)
        slotWidth = genevaCrankPinDiameter + allowedClearance  # noqa: F841 (kept for parity with original parameters)
        stopArcRadius = genevaCrankRadius - (genevaCrankPinDiameter * 1.5)
        stopDiscRadius = stopArcRadius - allowedClearance

        rotateAmount = 2 * math.pi / genevaWheelSlotQuantity

        root_boi = _add_cylinder(context, "GenevaWheel", genevaWheelRadius, genevaHeight / 2, vertices, (0, 0, 0))
        bee_helper = _add_cylinder(context, "GenevaSlotCutter", stopDiscRadius, genevaHeight, vertices, (centerDistance, 0, 0))

        for _ in range(genevaWheelSlotQuantity):
            _apply_boolean(context, root_boi, bee_helper, 'DIFFERENCE', 'FAST')
            root_boi.rotation_euler.z += rotateAmount

        root_boi.rotation_euler.z += rotateAmount / 2

        slotPos = centerDistance - genevaCrankRadius
        little_poky = _add_cylinder(context, "GenevaPinCutter", genevaCrankPinDiameter / 2, genevaHeight, vertices, (slotPos, 0, 0))
        helper_long_cube = _add_cube(context, "GenevaPinCutterExtension", genevaCrankPinDiameter, (slotPos + centerDistance, 0, 0))
        helper_long_cube.scale.x = centerDistance / genevaCrankPinDiameter * 2

        _apply_boolean(context, little_poky, helper_long_cube, 'UNION', 'EXACT')

        for _ in range(genevaWheelSlotQuantity + 1):
            _apply_boolean(context, root_boi, little_poky, 'DIFFERENCE', 'EXACT')
            root_boi.rotation_euler.z += rotateAmount

        _remove_object(helper_long_cube)
        _remove_object(little_poky)
        _remove_object(bee_helper)

        little_poky = _add_cylinder(context, "GenevaPin", genevaCrankPinDiameter / 2 - pinTolerence, genevaHeight / 2, vertices, (slotPos, 0, 0))
        bee_helper = _add_cylinder(context, "GenevaStopDisc", stopDiscRadius - stopDiscTolerence, genevaHeight / 2, vertices, (centerDistance, 0, 0))
        stop_disc_cutout = _add_cylinder(context, "GenevaStopDiscCutter", genevaWheelRadius + stopDiscCutoutTolerence, genevaHeight, vertices, (0, 0, 0))

        _apply_boolean(context, bee_helper, stop_disc_cutout, 'DIFFERENCE', 'EXACT')
        _remove_object(stop_disc_cutout)

        slottyBoiBaseRadius = centerDistance - slotPos + genevaCrankPinDiameter / 2 - pinTolerence
        slotty_boi_base = _add_cylinder(context, "GenevaCrank", slottyBoiBaseRadius, genevaHeight / 2, vertices, (centerDistance, 0, -genevaHeight / 2))

        spokyBoiBaseRadius = centerDistance - slottyBoiBaseRadius - baseTolerence
        spoky_boi_base = _add_cylinder(context, "GenevaWheelBase", spokyBoiBaseRadius, genevaHeight / 2, vertices, (0, 0, -genevaHeight / 2))

        _apply_boolean(context, root_boi, spoky_boi_base, 'UNION', 'EXACT')
        _remove_object(spoky_boi_base)

        wheel_cutout = _add_cylinder(context, "GenevaWheelHoleCutter", wheelHoleSize, genevaHeight * 2, vertices, (0, 0, 0))
        _apply_boolean(context, root_boi, wheel_cutout, 'DIFFERENCE', 'EXACT')
        _remove_object(wheel_cutout)

        _apply_boolean(context, slotty_boi_base, little_poky, 'UNION', 'EXACT')
        _remove_object(little_poky)

        _apply_boolean(context, slotty_boi_base, bee_helper, 'UNION', 'EXACT')
        _remove_object(bee_helper)

        crank_cutout = _add_cylinder(context, "GenevaCrankHoleCutter", crankHoleSize, genevaHeight * 2, vertices, (centerDistance, 0, 0))
        _apply_boolean(context, slotty_boi_base, crank_cutout, 'DIFFERENCE', 'EXACT')
        _remove_object(crank_cutout)

        after = set(bpy.data.objects)
        new_objs = [obj.name for obj in (after - before)]
        # --------------------------------------------------------
        # Store the new list on the scene so we can delete them
        # next time the operator is called.
        # --------------------------------------------------------
        context.scene["geneva_objects"] = new_objs

        return {'FINISHED'}


# ----------------------------------------------------------------
#  Add-menu entry
# ----------------------------------------------------------------
def menu_func(self, ctx):
    self.layout.operator(MESH_OT_geneva_wrapper.bl_idname, icon='MESH_CYLINDER')


# ----------------------------------------------------------------
#  Registration
# ----------------------------------------------------------------
classes = (MESH_OT_geneva_wrapper,)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
