import io
import re
from array import array
import struct
import numpy
import itertools
import collections
import os
from glob import glob
import json
import textwrap
import shutil
import logging

# import vendor.bpy as bpy
# from vendor.bpy_extras.io_utils import unpack_list, ImportHelper, ExportHelper, axis_conversion, orientation_helper
# from vendor.bpy.props import BoolProperty, StringProperty, CollectionProperty
# from vendor.mathutils import Matrix, Vector
import bpy
from bpy_extras.io_utils import unpack_list, ImportHelper, ExportHelper, axis_conversion
from bpy.props import BoolProperty, StringProperty, CollectionProperty
from bpy_extras.image_utils import load_image
from mathutils import Matrix, Vector

bl_info = {
    "name": "Li3DM",
    "blender": (3, 6, 0),
    "author": "Lioh",
    "location": "File > Import-Export",
    "description": "Refactor of 3DMigoto's addon",
    "category": "Import-Export",
    "tracker_url": "https://github.com/SilentNightSound/GI-Model-Importer",
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

IOOBJOrientationHelper = type('DummyIOOBJOrientationHelper', (object,), {})

class Fatal(Exception): pass

def log(data):
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'CONSOLE':
                override = {'window': window, 'screen': screen, 'area': area}
                bpy.ops.console.scrollback_append(override, text=str(data), type="OUTPUT")

# https://theduckcow.com/2019/update-addons-both-blender-28-and-27-support/
def make_annotations(cls):
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls

vb_elem_pattern = re.compile(r'''vb\d+\[\d*]\+\d+ (?P<semantic>[^:]+): (?P<data>.*)$''')

def import_mesh_from_frame_analysis(context, ib_file, vb_file):
    mesh = bpy.data.meshes.new(vb_file.name)
    obj = bpy.data.objects.new(mesh.name, mesh)
    # obj.matrix_world = axis_conversion().to_4x4()
    obj['3DMigoto:IBFormat'] = "DXGI_FORMAT_R32_UINT"
    next(ib_file)  # byte offset
    obj['3DMigoto:FirstIndex'] = int(next(ib_file)[13:-1])  # len["first index: "]
    for i in range(4): next(ib_file)  # index count, topology, format, ""
    faces = [map(int, line.split()) for line in ib_file]
    # import_faces_from_ib(mesh, ib)
    face_count = len(faces)
    mesh.loops.add(face_count * 3)
    mesh.loops.foreach_set('vertex_index', unpack_list(faces))
    mesh.polygons.add(face_count)
    mesh.polygons.foreach_set('loop_start', [x * 3 for x in range(face_count)])
    mesh.polygons.foreach_set('loop_total', [3] * face_count)

    vertices = []
    layout = {}
    for line in vb_file:
        if line.startswith('stride:'):
            obj['3DMigoto:VBStride'] = int(line[8:])
        if line.startswith('first vertex:'):
            obj['3DMigoto:FirstVertex'] = int(line[14:])
        if line.startswith("element["):
            name = next(vb_file)[16:-1]  # [len("  SemanticName: "):]
            layout[name] = {}
            layout[name]['index'] = int(next(vb_file)[17:-1])  # [len("  SemanticIndex: "):]
            layout[name]['format'] = next(vb_file)[10:-1]  # [len("  Format: "):]
            layout[name]['slot'] = int(next(vb_file)[13:-1])  # [len("  InputSlot: "):]
            layout[name]['offset'] = int(next(vb_file)[21:-1])  # [len("  AlignedByteOffset: "):]
            next(vb_file)  # InputSlotClass: per-vertex
            next(vb_file)  # InstanceDataStepRate: 0
        if line.startswith("vertex-data:"):
            log(json.dumps(layout))
            next(vb_file)  # empy line
            vertex = {}
            for line2 in vb_file:
                if line2 == '':
                    log(f"append {json.dumps(vertex)}")
                    vertices.append(vertex)
                else:
                    match = vb_elem_pattern.match(line2)
                    fn = int if layout[match.group('semantic')]['format'].endswith("INT") else float
                    vertex[match.group('semantic')] = tuple(map(fn, match.group('data').split(",")))

    obj['3DMigoto:VBLayout'] = json.dumps(layout) # Attach the vertex buffer layout to the object for later exporting.
    # (blend_indices, blend_weights, texcoords, vertex_layers, use_normals) = import_vertices(mesh, vb)
    mesh.vertices.add(len(vertices))
    mesh.vertices.foreach_set('co', unpack_list([(x[0], x[1], x[2]) for x in tuple(x['POSITION'] for x in vertices)]))

    seen_offsets = set()
    texcoords = {}
    for key, elem in layout.items():
        # Discard elements that reuse offsets in the vertex buffer,
        # e.g. COLOR and some TEXCOORDs may be aliases of POSITION:
        if (elem['slot'], elem['offset']) in seen_offsets:
            assert (key != 'POSITION')
            continue
        seen_offsets.add((elem['slot'], elem['offset']))

        data = tuple(x[key] for x in vertices)
        if key.startswith('COLOR'):
            mesh.vertex_colors.new(name=key)
            color_layer = mesh.vertex_colors[key].data
            for l in mesh.loops:
                log(vertices[0])
                log(f"vertices_len:{len(vertices)}, index:{l.index}, vertex_index:{l.vertex_index}")
                key_ = vertices[l.vertex_index][key]
                l_index_ = color_layer[l.index]
                l_index_.color = list(key_)
        elif key.startswith('TEXCOORD'):
            texcoords[elem['index']] = data

    # import_uv_layers
    cmap = {'x': 0, 'y': 1, 'z': 2, 'w': 3}
    for (texcoord, data) in sorted(texcoords.items()):
        # TEXCOORDS can have up to four components, but UVs can only have two dimensions.
        # For now, split the TEXCOORD into two sets of UV coordinates:
        dim = len(data[0])
        if dim != 2 and dim != 4:
            raise Fatal('Unhandled TEXCOORD dimension: %i' % dim)
        for components in ('xy', 'zw') if dim == 4 else ('xy',):
            uv = mesh.uv_layers.new(name=('TEXCOORD%s.%s' % (texcoord and texcoord or '', components)))
            uvs = [[d[cmap[c]] for c in components] for d in data]
            for l in mesh.loops:
                uv.data[l.index].uv = uvs[l.vertex_index]

    # We will need to make sure we re-export the same blend indices later - that they haven't been renumbered.
    if vertices[0]['BLENDINDICES']:
        group_count = max(itertools.chain(*(tuple(x['BLENDINDICES'] for x in vertices))))
        for i in range(group_count + 1):
            obj.vertex_groups.new(name=str(i))
        for vertex in mesh.vertices:
            for i, w in zip(vertex['BLENDINDICES'], vertex['BLENDWEIGHT']):
                if w != 0.0:
                    obj.vertex_groups[i].add((vertex.index,), w, 'REPLACE')

    # Validate closes the loops, so they don't disappear after edit mode and probably other important things:
    mesh.validate(verbose=False, clean_customdata=False)  # *Very* important to not remove lnors here!
    # Not actually sure update is necessary. It seems to update the vertex normals, not sure what else:
    mesh.update()
    mesh.calc_normals()

    context.scene.collection.objects.link(obj)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    return obj


class ImportFrameAnalysis(bpy.types.Operator, ImportHelper, IOOBJOrientationHelper):
    bl_idname = "import_meshes.frame_analysis"
    bl_label = "Import Frame Analysis Dump"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = '.txt'
    filter_glob : StringProperty(default='*.txt', options={'HIDDEN'},)
    files : CollectionProperty(name="File Path", type=bpy.types.OperatorFileListElement,)

    def execute(self, context):
        try:
            dirname = os.path.dirname(self.filepath)
            for ib_file in [f for f in self.files if "-ib=" in f.name]:
                logging.info(f"importing {ib_file.name}...")
                logger.info(f"importing {ib_file.name}....")
                log(f"importing {ib_file.name}... ..")
                vb_file = [f for f in self.files if "-vb0=" in f.name and f.name.startswith(ib_file.name.split("-")[0])][0]
                import_mesh_from_frame_analysis(context, open(os.path.join(dirname, ib_file.name), 'r'),
                                                open(os.path.join(dirname, vb_file.name), 'r'))
        except Fatal as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}

def menu_func_import_fa(self, context):
    self.layout.operator(ImportFrameAnalysis.bl_idname, text="3DM dump (vb.txt + ib.txt)")

register_classes = (ImportFrameAnalysis,)

def register():
    for cls in register_classes:
        make_annotations(cls)
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_fa)

def unregister():
    for cls in reversed(register_classes):
        bpy.utils.unregister_class(cls)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_fa)

if __name__ == "__main__":
    register()