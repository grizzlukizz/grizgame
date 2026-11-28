"""Rebuild the original low-poly meshes with Blender in background mode."""
import math
from pathlib import Path

import bpy

OUT = Path(__file__).resolve().parent / "Assets" / "Resources" / "Models"

def finish(name, vertices, faces, bevel=0):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    part = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(part)
    bpy.context.view_layer.objects.active = part
    part.select_set(True)
    if bevel:
        mod = part.modifiers.new("Chamfer", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        normals = part.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
        normals.keep_sharp = True
    bpy.ops.wm.obj_export(filepath=str(OUT/f"{name}.obj"), export_selected_objects=True,
                          export_materials=False, forward_axis="NEGATIVE_Z", up_axis="Y")

def rings(name, sections, sides=8, bevel=.025):
    verts = [(rx*math.cos(2*math.pi*i/sides + math.pi/8), ry*math.sin(2*math.pi*i/sides + math.pi/8), z)
             for z,rx,ry in sections for i in range(sides)]
    faces = [tuple(reversed(range(sides)))]
    for ring in range(len(sections)-1):
        for i in range(sides):
            a,b = ring*sides+i,ring*sides+(i+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(range(len(verts)-sides,len(verts))))
    finish(name,verts,faces,bevel)

finish("panel", [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                 (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],
       [(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)], .15)
rings("torso", [(-1,.66,.78),(-.55,.86,.87),(.51,1,.93),(.8,.74,.77)])
rings("limb", [(-1,.68,.69),(-.70,.81,.83),(.67,1,1),(1,.78,.81)])
rings("helmet", [(-1,.78,.8),(-.67,1,1),(.24,1,.98),(.72,.81,.86),(1,.44,.49)], 12)
rings("head", [(-1,.58,.68),(-.53,.85,.92),(.46,1,1),(.83,.78,.84),(1,.48,.51)], 9)
rings("barrel", [(-1,.85,.85),(-.84,1,1),(.88,1,1),(1,.85,.85)], 10)
rings("bush", [(-1,.28,.37),(-.44,.83,.84),(.24,1,.9),(.72,.63,.77),(1,.25,.31)], 7, 0)
