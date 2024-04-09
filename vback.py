import os

stride92 = '''stride: 92
topology: trianglelist
format: DXGI_FORMAT_R32_UINT
element[0]:
  SemanticName: POSITION
  SemanticIndex: 0
  Format: R32G32B32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 0
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[1]:
  SemanticName: NORMAL
  SemanticIndex: 0
  Format: R32G32B32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 12
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[2]:
  SemanticName: TANGENT
  SemanticIndex: 0
  Format: R32G32B32A32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 24
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[3]:
  SemanticName: BLENDWEIGHT
  SemanticIndex: 0
  Format: R32G32B32A32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 40
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[4]:
  SemanticName: BLENDINDICES
  SemanticIndex: 0
  Format: R32G32B32A32_SINT
  InputSlot: 0
  AlignedByteOffset: 56
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[5]:
  SemanticName: COLOR
  SemanticIndex: 0
  Format: R8G8B8A8_UNORM
  InputSlot: 0
  AlignedByteOffset: 72
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[6]:
  SemanticName: TEXCOORD
  SemanticIndex: 0
  Format: R32G32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 76
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[7]:
  SemanticName: TEXCOORD
  SemanticIndex: 1
  Format: R32G32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 84
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
'''

stride84 = '''stride: 84
topology: trianglelist
format: DXGI_FORMAT_R32_UINT
element[0]:
  SemanticName: POSITION
  SemanticIndex: 0
  Format: R32G32B32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 0
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[1]:
  SemanticName: NORMAL
  SemanticIndex: 0
  Format: R32G32B32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 12
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[2]:
  SemanticName: TANGENT
  SemanticIndex: 0
  Format: R32G32B32A32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 24
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[3]:
  SemanticName: BLENDWEIGHT
  SemanticIndex: 0
  Format: R32G32B32A32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 40
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[4]:
  SemanticName: BLENDINDICES
  SemanticIndex: 0
  Format: R32G32B32A32_SINT
  InputSlot: 0
  AlignedByteOffset: 56
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[5]:
  SemanticName: COLOR
  SemanticIndex: 0
  Format: R8G8B8A8_UNORM
  InputSlot: 0
  AlignedByteOffset: 72
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
element[6]:
  SemanticName: TEXCOORD
  SemanticIndex: 0
  Format: R32G32_FLOAT
  InputSlot: 0
  AlignedByteOffset: 76
  InputSlotClass: per-vertex
  InstanceDataStepRate: 0
'''

if __name__ == "__main__":
    path = "~\\Documents\\create\\mod\\own\\LumineThrone\\9KukiShinobuToplessNoPanNoMaskNoBelt"

    ini_file_name = [x for x in os.listdir(path) if ".ini" in x][0]
    name = ini_file_name[8 if ini_file_name.startswith("DISABLED") else 0:-4]
    classifications = []  # Ex.: Head, Body, Dress
    text_coord_stride = 12  # always either 12 or 20
    with open(os.path.join(path, ini_file_name), "r") as ini:
        for x in ini:
            if x.startswith("filename = ") and x.endswith(".ib\n"):
                classifications.append(x[11+len(name):-4])
            if x == "stride = 20\n":
                text_coord_stride = 20
    with open(os.path.join(path, f"{name}Position.buf"), "rb") as p, \
            open(os.path.join(path, f"{name}Blend.buf"), "rb") as b, \
            open(os.path.join(path, f"{name}Texcoord.buf"), "rb") as t:
        position, blend, texCoord = bytearray(p.read()), bytearray(b.read()), bytearray(t.read())
        vertex_count = len(position) // 40
        print(f"name={name}, vertex_count={vertex_count}, text_coord_stride={text_coord_stride}, classifications={classifications}")
        for c in classifications:
            with open(os.path.join(path, f"{name}{c}.vb"), "wb") as vb:
                for i in range(0, vertex_count):
                    ip, ib, it = i*40, i*32, i*text_coord_stride
                    vb.write(position[ip:ip+40])
                    vb.write(blend[ib:ib+32])
                    vb.write(texCoord[it:it+text_coord_stride])
            with open(os.path.join(path, f"{name}{c}.fmt"), "w") as fmt:
                fmt.write(stride92 if text_coord_stride == 20 else stride84)
