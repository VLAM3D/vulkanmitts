import numpy

def get_xyzw_uv_cube_coords():
    return numpy.array([ [-1.0, -1.0, -1.0, 1.0, 0.0, 0.0],
                         [-1.0,  1.0,  1.0, 1.0, 1.0, 1.0],
                         [-1.0, -1.0,  1.0, 1.0, 1.0, 0.0],
                         [-1.0,  1.0,  1.0, 1.0, 1.0, 1.0],
                         [-1.0, -1.0, -1.0, 1.0, 0.0, 0.0],
                         [-1.0,  1.0, -1.0, 1.0, 0.0, 1.0],
                         #################################
                         [-1.0, -1.0, -1.0, 1.0, 1.0, 0.0],
                         [ 1.0, -1.0, -1.0, 1.0, 0.0, 0.0],
                         [ 1.0,  1.0, -1.0, 1.0, 0.0, 1.0],
                         [-1.0, -1.0, -1.0, 1.0, 1.0, 0.0],
                         [ 1.0,  1.0, -1.0, 1.0, 0.0, 1.0],
                         [-1.0,  1.0, -1.0, 1.0, 1.0, 1.0],
                         #################################
                         [-1.0, -1.0, -1.0, 1.0, 1.0, 1.0],
                         [ 1.0, -1.0,  1.0, 1.0, 0.0, 0.0],
                         [ 1.0, -1.0, -1.0, 1.0, 1.0, 0.0],
                         [-1.0, -1.0, -1.0, 1.0, 1.0, 1.0],
                         [-1.0, -1.0,  1.0, 1.0, 0.0, 1.0],
                         [ 1.0, -1.0,  1.0, 1.0, 0.0, 0.0],
                         #################################
                         [-1.0,  1.0, -1.0, 1.0, 1.0, 1.0],
                         [ 1.0,  1.0,  1.0, 1.0, 0.0, 0.0],
                         [-1.0,  1.0,  1.0, 1.0, 0.0, 1.0],
                         [-1.0,  1.0, -1.0, 1.0, 1.0, 1.0],
                         [ 1.0,  1.0, -1.0, 1.0, 1.0, 0.0],
                         [ 1.0,  1.0,  1.0, 1.0, 0.0, 0.0],
                         #################################
                         [ 1.0,  1.0, -1.0, 1.0, 1.0, 1.0],
                         [ 1.0, -1.0,  1.0, 1.0, 0.0, 0.0],
                         [ 1.0,  1.0,  1.0, 1.0, 0.0, 1.0],
                         [ 1.0, -1.0,  1.0, 1.0, 0.0, 0.0],
                         [ 1.0,  1.0, -1.0, 1.0, 1.0, 1.0],
                         [ 1.0, -1.0, -1.0, 1.0, 1.0, 0.0],
                         #################################
                         [-1.0,  1.0,  1.0, 1.0, 0.0, 1.0],
                         [ 1.0,  1.0,  1.0, 1.0, 1.0, 1.0],
                         [-1.0, -1.0,  1.0, 1.0, 0.0, 0.0],
                         [-1.0, -1.0,  1.0, 1.0, 0.0, 0.0],
                         [ 1.0,  1.0,  1.0, 1.0, 1.0, 1.0],
                         [ 1.0, -1.0,  1.0, 1.0, 1.0, 0.0]], dtype=numpy.single)
