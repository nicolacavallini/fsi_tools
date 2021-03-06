#! /usr/bin/env python

import json
import matplotlib.pyplot as plt
import math as mth
import numpy as np
import os
from scipy import sparse
import scipy.sparse.linalg as sp_la
import sys
import time

sys.path.append('../../modules')
import assemble
import basis_func as shp
import geom_utils as geom
import la_utils
import lin_tri_mesh as lin_t3
from parameters_handler import ParametersHandler
from preconditioner import BlockPreconditioner
from shapely.geometry import Polygon
import viewers

###
# Main script for the DLM method with fixpoint iteration as a nonlinear solver
# Cavity and Annulus example work
# Channel and Swingbar are experimental!
# There's still a lot to do ;-)
###

### Does not work yet
# def start_later(cn_time):
#     #load mesh file
#     filename = results_dir+'/mesh'
#     f = open(filename,"rb")
#     topo_p = np.load(f)
#     x_p = np.load(f)
#     y_p = np.load(f)
#     topo_u = np.load(f)
#     x_u = np.load(f)
#     y_u = np.load(f)
#     c2f = np.load(f)
#     topo_s = np.load(f)
#     sx_n = np.load(f)
#     sy_n = np.load(f)
#     s_lgr = np.load(f)
#     t_lgr = np.load(f)
#     f.close()
#
#     global u_n_old
#     global p_n_old
#     global sx_n_old
#     global sy_n_old
#     global l_n_old
#     global ux_n_old
#     global uy_n_old
#     #load previous timestep
#     filename = "./"+results_dir+"/"
#     filename += 'cn_time_'+str(cn_time-1).zfill(ph.time_index_digits)
#     f = open(filename,"rb")
#     u_n_old = np.load(f)
#     p_n_old = np.load(f)
#     sx_n_old = np.load(f)
#     sy_n_old = np.load(f)
#     l_n_old = np.load(f)
#     f.close()
#     ux_n_old = u_n_old[0:ndofs_u]
#     uy_n_old = u_n_old[ndofs_u:2*ndofs_u]
#
#     global u_n
#     global p_n
#     global sx_n
#     global sy_n
#     global l_n
#     global ux_n
#     global uy_n
#     #load current timestep
#     filename = "./"+results_dir+"/"
#     filename += 'cn_time_'+str(cn_time).zfill(ph.time_index_digits)
#     f = open(filename,"rb")
#     u_n = np.load(f)
#     p_n = np.load(f)
#     sx_n = np.load(f)
#     sy_n = np.load(f)
#     l_n = np.load(f)
#     f.close()
#     ux_n = u_n[0:ndofs_u]
#     uy_n = u_n[ndofs_u:2*ndofs_u]
#
#     return

def write_mesh():
    filename = results_dir+'mesh'#'./mesh/'+sim_prefix
    f = open(filename,"wb")
    np.save(f,topo_p)
    np.save(f,x_p)
    np.save(f,y_p)
    np.save(f,topo_u)
    np.save(f,x_u)
    np.save(f,y_u)
    np.save(f,c2f)
    np.save(f,topo_s)
    np.save(f,sx_n)
    np.save(f,sy_n)
    np.save(f,s_lgr)
    np.save(f,t_lgr)
    f.close()
    return

def stack_rhs(f_rhs_x, f_rhs_y, p_rhs, s_rhs_x, s_rhs_y, l_rhs_x, l_rhs_y):
    (f_rhs_x, f_rhs_y) = fluid_rhs_apply_bc(f_rhs_x, f_rhs_y)
    #(s_rhs_x, s_rhs_y) = structure_rhs_apply_bc(s_rhs_x, s_rhs_y)

    rhs = np.append(f_rhs_x, f_rhs_y)
    rhs = np.append(rhs, p_rhs)
    rhs = np.append(rhs, s_rhs_x)
    rhs = np.append(rhs, s_rhs_y)
    rhs = np.append(rhs, l_rhs_x)
    rhs = np.append(rhs, l_rhs_y)
    rhs = np.append(rhs, np.zeros(1))

    return rhs

def fluid_rhs_apply_bc(f_rhs_x, f_rhs_y):
    #lower boundary
    bc_id = np.where(y_u < delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'cavity_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'channel_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'swingbar_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.

    #upper boundary
    bc_id = np.where(y_u > 1-delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'cavity_':
        f_rhs_x[bc_id] = 1.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'channel_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'swingbar_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.

    #right boundary
    bc_id = np.where(x_u > 1-delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'cavity_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    # elif ph.mesh_prefix == 'channel_':
    #    f_rhs_x[bc_id] = 4 * y_u[bc_id] * (1-y_u[bc_id])
    #    f_rhs_y[bc_id] = 0
    elif ph.mesh_prefix == 'swingbar_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.

    #left boundary
    bc_id = np.where(x_u < delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        f_rhs_x[bc_id] = 0.
    elif ph.mesh_prefix == 'cavity_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'channel_':
        f_rhs_x[bc_id] = 4 * y_u[bc_id] * (1-y_u[bc_id])
        f_rhs_y[bc_id] = 0.
    elif ph.mesh_prefix == 'swingbar_':
        f_rhs_x[bc_id] = 0.
        f_rhs_y[bc_id] = 0.

    return f_rhs_x, f_rhs_y

def fluid_m_apply_bc(A11, A22, A12 = None, A21 = None):
    if A12 == None:
        A12 = sparse.csc_matrix(A11.shape)
    if A21 == None:
        A21 = sparse.csc_matrix(A11.shape)
    #lower boundary
    bc_id = np.where(y_u < delta_x/10)
    if ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'channel_' or ph.mesh_prefix == 'swingbar_':
        A11 = la_utils.set_diag(A11,bc_id)
        A12 = la_utils.clear_rows(A12, bc_id)
    A22 = la_utils.set_diag(A22,bc_id)
    A21 = la_utils.clear_rows(A21, bc_id)

    #upper boundary
    bc_id = np.where(y_u > 1-delta_x/10)
    A11 = la_utils.set_diag(A11,bc_id)
    A22 = la_utils.set_diag(A22,bc_id)
    A12 = la_utils.clear_rows(A12,bc_id)
    A21 = la_utils.clear_rows(A21,bc_id)

    #right boundary
    bc_id = np.where(x_u > 1-delta_x/10)
    if ph.mesh_prefix == 'annulus_' or ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'swingbar_':
        A11 = la_utils.set_diag(A11,bc_id)
        A22 = la_utils.set_diag(A22,bc_id)
        A12 = la_utils.clear_rows(A12,bc_id)
        A21 = la_utils.clear_rows(A21,bc_id)

    #left boundary
    bc_id = np.where(x_u < delta_x/10)
    A11 = la_utils.set_diag(A11,bc_id)
    A12 = la_utils.clear_rows(A12,bc_id)
    if ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'channel_' or ph.mesh_prefix == 'swingbar_':
        A22 = la_utils.set_diag(A22,bc_id)
        A21 = la_utils.clear_rows(A21,bc_id)
    return A11, A22, A12, A21

def pressure_m_apply_bc(BT1, BT2):
    #lower boundary
    bc_id = np.where(y_u < delta_x/10)
    if ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'channel_' or ph.mesh_prefix == 'swingbar_':
        BT1 = la_utils.clear_rows(BT1,bc_id)
    BT2 = la_utils.clear_rows(BT2,bc_id)

    #upper boundary
    bc_id = np.where(y_u > 1-delta_x/10)
    BT1 = la_utils.clear_rows(BT1,bc_id)
    BT2 = la_utils.clear_rows(BT2,bc_id)

    #right boundary
    bc_id = np.where(x_u > 1-delta_x/10)
    if ph.mesh_prefix == 'annulus_' or ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'swingbar_':
        BT1 = la_utils.clear_rows(BT1,bc_id)
        BT2 = la_utils.clear_rows(BT2,bc_id)

    #left boundary
    bc_id = np.where(x_u < delta_x/10)
    BT1 = la_utils.clear_rows(BT1,bc_id)
    if ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'channel_' or ph.mesh_prefix == 'swingbar_':
        BT2 = la_utils.clear_rows(BT2,bc_id)

    return BT1, BT2

def structure_m_apply_bc(KS11, KS22, MST11, MST22):
    bc_id = np.where(sy_n < delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        KS22 = la_utils.set_diag(KS22,bc_id)
        MST22 = la_utils.clear_rows(MST22,bc_id)

    bc_id = np.where(sx_n < delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        KS11 = la_utils.set_diag(KS11,bc_id)
        MST11 = la_utils.clear_rows(MST11,bc_id)

    return KS11, KS22, MST11, MST22

def structure_rhs_apply_bc(s_rhs_x, s_rhs_y):
    if(ph.time_integration != 'CN'):
        return  s_rhs_x, s_rhs_y

    bc_id = np.where(sy_n < delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        s_rhs_y[bc_id] = 0.

    bc_id = np.where(sx_n < delta_x/10)
    if ph.mesh_prefix == 'annulus_':
        s_rhs_x[bc_id] = 0.

    return s_rhs_x, s_rhs_y

def coupling_apply_bc(GT11, GT22):
    #lower boundary
    bc_id = np.where(y_u < delta_x/10)
    if ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'channel_' or ph.mesh_prefix == 'swingbar_':
        GT11 = la_utils.clear_rows(GT11,bc_id)
    GT22 = la_utils.clear_rows(GT22,bc_id)

    #upper boundary
    bc_id = np.where(y_u > 1-delta_x/10)
    GT11 = la_utils.clear_rows(GT11,bc_id)
    GT22 = la_utils.clear_rows(GT22,bc_id)

    #right boundary
    bc_id = np.where(x_u > 1-delta_x/10)
    if ph.mesh_prefix == 'annulus_' or ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'swingbar_':
        GT11 = la_utils.clear_rows(GT11,bc_id)
        GT22 = la_utils.clear_rows(GT22,bc_id)

    #left boundary
    bc_id = np.where(x_u < delta_x/10)
    GT11 = la_utils.clear_rows(GT11,bc_id)
    if ph.mesh_prefix == 'cavity_' or ph.mesh_prefix == 'channel_' or ph.mesh_prefix == 'swingbar_':
        GT22 = la_utils.clear_rows(GT22,bc_id)

    return GT11, GT22

def assemble_kinematic_coupling(sx_n, sy_n):
    (str_segments,fluid_id) = geom.fluid_intersect_mesh(topo_u,x_u,y_u,
                    topo_s,sx_n,sy_n)
    GT11 = assemble.u_s_p1_thick(x_u,y_u,topo_u,
                    s_lgr,t_lgr,
                    sx_n,sy_n,topo_s,ie_s,
                    str_segments,fluid_id)

    GT22 = GT11
    G11 = GT11.transpose()

    G = sparse.vstack([
            sparse.hstack([G11,sparse.csc_matrix((ndofs_s,ndofs_u))]),
            sparse.hstack([sparse.csc_matrix((ndofs_s,ndofs_u)),G11]) ])

    (GT11, GT22) = coupling_apply_bc(GT11, GT22)

    GT = sparse.vstack([
            sparse.hstack([GT11,sparse.csc_matrix((ndofs_u,ndofs_s))]),
            sparse.hstack([sparse.csc_matrix((ndofs_u,ndofs_s)),GT22]) ])
    return G, GT, GT11, GT22

def assemble_blockwise_force_BDF1(ux_n, uy_n, dx_n, dy_n):
    f_rhs_x = MF11.dot(ux_n)
    f_rhs_y = MF11.dot(uy_n)

    l_rhs_x = -MS11.dot(dx_n)
    l_rhs_y = -MS11.dot(dy_n)

    return stack_rhs(f_rhs_x, f_rhs_y, np.zeros((ndofs_p)),
                     np.zeros((ndofs_s)), np.zeros((ndofs_s)), l_rhs_x, l_rhs_y)

def assemble_blockwise_matrix_BDF1():
    D11 = MF11 + ph.dt*KF11 + ph.dt*S11
    D22 = MF11 + ph.dt*KF11 + ph.dt*S11

    (D11, D22, S12, S21) = fluid_m_apply_bc(D11, D22)

    A = sparse.hstack([
        sparse.vstack([D11, S12]),
        sparse.vstack([S21, D22])
    ])

    mat1 = sparse.hstack([A,
                         -ph.dt*BT,
                         sparse.csc_matrix((ndofs_u*2,ndofs_s*2)),
                         ph.dt*GT,
                         sparse.csc_matrix((ndofs_u*2,1))
    ])

    mat2 = sparse.hstack([-ph.dt*B,
                          sparse.csc_matrix((ndofs_p,ndofs_p)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          mean_p.transpose()
    ])

    mat3 = sparse.hstack([sparse.csc_matrix((ndofs_s*2,ndofs_u*2)),
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          KS,
                          -MST,
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat4 = sparse.hstack([ph.dt*G,
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          -MS,
                          sparse.csc_matrix((ndofs_s*2,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat5 = sparse.hstack([sparse.csc_matrix((1,ndofs_u*2)),
                          mean_p,
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,1))
    ])

    mat = sparse.vstack([mat1,mat2,mat3,mat4,mat5])
    mat = mat.tocsc()
    return mat

def assemble_blockwise_force_BDF2(ux_n, uy_n, ux_n_old, uy_n_old, dx_n, dy_n, dx_n_old, dy_n_old):
    f_rhs_x = (MF11.dot(2*ux_n - 0.5*ux_n_old))
    f_rhs_y = (MF11.dot(2*uy_n - 0.5*uy_n_old))

    l_rhs_x = -(MS11.dot(2*dx_n - 0.5*dx_n_old))
    l_rhs_y = -(MS11.dot(2*dy_n - 0.5*dy_n_old))

    return stack_rhs(f_rhs_x, f_rhs_y, np.zeros((ndofs_p)),
                     np.zeros((ndofs_s)), np.zeros((ndofs_s)), l_rhs_x, l_rhs_y)

def assemble_blockwise_matrix_BDF2():
    D11 = 1.5*MF11 + ph.dt*KF11 + ph.dt*S11
    D22 = 1.5*MF11 + ph.dt*KF11 + ph.dt*S11

    (D11, D22, S12, S21) = fluid_m_apply_bc(D11, D22)

    A = sparse.hstack([
        sparse.vstack([D11, S12]),
        sparse.vstack([S21, D22])
    ])

    mat1 = sparse.hstack([A,
                          -ph.dt*BT,
                          sparse.csc_matrix((ndofs_u*2,ndofs_s*2)),
                          ph.dt*GT,
                          sparse.csc_matrix((ndofs_u*2,1))
    ])

    mat2 = sparse.hstack([-ph.dt*B,
                          sparse.csc_matrix((ndofs_p,ndofs_p)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          mean_p.transpose()
    ])

    mat3 = sparse.hstack([sparse.csc_matrix((ndofs_s*2,ndofs_u*2)),
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          KS,
                          -MST,
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat4 = sparse.hstack([ph.dt*G,
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          -1.5*MS,
                          sparse.csc_matrix((ndofs_s*2,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat5 = sparse.hstack([sparse.csc_matrix((1,ndofs_u*2)),
                          mean_p,
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,1))
    ])

    mat = sparse.vstack([mat1,mat2,mat3,mat4,mat5])
    mat = mat.tocsc()
    return mat

def assemble_blockwise_force_CN(ux_n, uy_n, u_n, p_n, dx_n, dy_n, l_n):
    f_rhs_x = MF11.dot(ux_n) - ph.dt*0.5*KF11.dot(ux_n) - ph.dt*0.25*(S11+T11).dot(ux_n)
    f_rhs_y = MF11.dot(uy_n) - ph.dt*0.5*KF11.dot(uy_n) - ph.dt*0.25*(S11+T11).dot(uy_n)

    p_rhs = np.zeros((ndofs_p, 1))

    s_rhs_x = np.zeros((ndofs_s, 1))
    s_rhs_y = np.zeros((ndofs_s, 1))

    l_rhs_x = -MS11.dot(dx_n) - ph.dt*0.5*GT11.transpose().dot(ux_n)
    l_rhs_y = -MS11.dot(dy_n) - ph.dt*0.5*GT22.transpose().dot(uy_n)

    return stack_rhs(f_rhs_x, f_rhs_y, p_rhs,
                     s_rhs_x, s_rhs_y, l_rhs_x, l_rhs_y)

def assemble_blockwise_matrix_CN():
    D11 = MF11 + ph.dt*0.5*KF11 + ph.dt*0.25*(S11+T11)
    D22 = MF11 + ph.dt*0.5*KF11 + ph.dt*0.25*(S11+T11)

    (D11, D22, S12, S21) = fluid_m_apply_bc(D11, D22)

    A = sparse.hstack([
        sparse.vstack([D11, S12]),
        sparse.vstack([S21, D22])
    ])

    mat1 = sparse.hstack([A,
                          -ph.dt*BT,
                          sparse.csc_matrix((ndofs_u*2,ndofs_s*2)),
                          ph.dt*GT,
                          sparse.csc_matrix((ndofs_u*2,1))
    ])

    mat2 = sparse.hstack([-ph.dt*B,
                          sparse.csc_matrix((ndofs_p,ndofs_p)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          mean_p.transpose()
    ])

    mat3 = sparse.hstack([sparse.csc_matrix((ndofs_s*2,ndofs_u*2)),
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          KS,
                          -MST,
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat4 = sparse.hstack([0.5*ph.dt*G,
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          -MS,
                          sparse.csc_matrix((ndofs_s*2,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat5 = sparse.hstack([sparse.csc_matrix((1,ndofs_u*2)),
                          mean_p,
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,1))
    ])

    mat = sparse.vstack([mat1,mat2,mat3,mat4,mat5])
    mat = mat.tocsc()
    return mat


def assemble_blockwise_force_TR(ux_n, uy_n, u_n, p_n, dx_n, dy_n, l_n):
    f_rhs_x = MF11.dot(ux_n) - ph.dt*0.5*KF11.dot(ux_n) - ph.dt*0.5*T11.dot(ux_n)
    f_rhs_x = f_rhs_x - ph.dt*0.5*HT11.dot(l_n[0:ndofs_s])
    f_rhs_y = MF11.dot(uy_n) - ph.dt*0.5*KF11.dot(uy_n) - ph.dt*0.5*T11.dot(uy_n)
    f_rhs_y = f_rhs_y - ph.dt*0.5*HT22.dot(l_n[ndofs_s:2*ndofs_s])

    p_rhs = np.zeros((ndofs_p, 1))

    s_rhs_x = np.zeros((ndofs_s, 1))
    s_rhs_y = np.zeros((ndofs_s, 1))

    l_rhs_x = -MS11.dot(dx_n) - ph.dt*0.5*HT11.transpose().dot(ux_n)
    l_rhs_y = -MS11.dot(dy_n) - ph.dt*0.5*HT22.transpose().dot(uy_n)

    return stack_rhs(f_rhs_x, f_rhs_y, p_rhs,
                     s_rhs_x, s_rhs_y, l_rhs_x, l_rhs_y)


def assemble_blockwise_matrix_TR():
    D11 = MF11 + ph.dt*0.5*KF11 + ph.dt*0.5*S11
    D22 = MF11 + ph.dt*0.5*KF11 + ph.dt*0.5*S11

    (D11, D22, S12, S21) = fluid_m_apply_bc(D11, D22)

    A = sparse.hstack([
        sparse.vstack([D11, S12]),
        sparse.vstack([S21, D22])
    ])

    mat1 = sparse.hstack([A,
                          -ph.dt*BT,
                          sparse.csc_matrix((ndofs_u*2,ndofs_s*2)),
                          0.5*ph.dt*GT,
                          sparse.csc_matrix((ndofs_u*2,1))
    ])

    mat2 = sparse.hstack([-ph.dt*B,
                          sparse.csc_matrix((ndofs_p,ndofs_p)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_p,ndofs_s*2)),
                          mean_p.transpose()
    ])

    mat3 = sparse.hstack([sparse.csc_matrix((ndofs_s*2,ndofs_u*2)),
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          KS,
                          -MST,
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat4 = sparse.hstack([0.5*ph.dt*G,
                          sparse.csc_matrix((ndofs_s*2,ndofs_p)),
                          -MS,
                          sparse.csc_matrix((ndofs_s*2,ndofs_s*2)),
                          sparse.csc_matrix((ndofs_s*2,1))
    ])

    mat5 = sparse.hstack([sparse.csc_matrix((1,ndofs_u*2)),
                          mean_p,
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,ndofs_s*2)),
                          sparse.csc_matrix((1,1))
    ])

    mat = sparse.vstack([mat1,mat2,mat3,mat4,mat5])
    mat = mat.tocsc()
    return mat

def area_measure(xs,ys):
    area_mes = MS11 * sx_n + MS11 * sy_n
    area_mes = area_mes * np.ones(area_mes.shape)
    area_mes = np.sum(area_mes)
    return area_mes

def l2_norm(M,g):
    l2_g = M.dot(g)
    l2_g = np.dot(l2_g.transpose(),g)
    l2_g = mth.sqrt(l2_g)
    return l2_g

def write_output():
    filename = results_dir +'cn_time_'+str(cn_time).zfill(ph.time_index_digits)
    f = open(filename,"wb")
    np.save(f,u_n)
    np.save(f,p_n)
    np.save(f,sx_n)
    np.save(f,sy_n)
    np.save(f,l_n)
    f.close()
    print('-----')
    print('results saved to:')
    print(filename)
    print('-----')
    return

def write_time():
    filename = results_dir +'time'
    f = open(filename,"wb")
    np.save(f,np.average(step_time))
    np.save(f,np.average(sol_time))
    np.save(f,residuals)
    f.close()

def eval_str_area():
    area = 0
    invertible = True
    for row in topo_s:
        x_l = sx_n[row]
        y_l = sy_n[row]
        eval_p = np.zeros((x_l.shape[0],2))
        eval_p[:,0] = x_l
        eval_p[:,1] = y_l
        poly = Polygon(tuple(eval_p.tolist()))
        invetible = invertible and poly.exterior.is_ccw
        area+= poly.area
    return (area, invertible)

###Start of the script

np.set_printoptions(precision=4)
np.set_printoptions(suppress=True)

if len(sys.argv) > 1:
    ph = ParametersHandler(sys.argv[1])
else:
    ph = ParametersHandler('simulation_parameters.json')
ph.simulation_info()

###Set up the geometry and intial conditions

nx_p = ph.n_delta_x
delta_x = 1./nx_p
ny_p = ph.n_delta_x
delta_y = 1./ny_p
(topo_p,x_p,y_p,
    topo_u,x_u,y_u,
    c2f) = lin_t3.mesh_t3_iso_t6(nx_p,ny_p,delta_x,delta_y)

(topo_p,x_p,y_p) = lin_t3.mesh_t3_t0(nx_p,ny_p,delta_x,delta_y)

filename = '../mesh_collection/' + ph.mesh_prefix+str(ph.n_delta_s)+'.msh'
(topo_s,s_lgr,t_lgr) = lin_t3.load_msh(filename)

sx_n = np.zeros(())
sy_n = np.zeros(())
sx_zero = np.zeros(())
sy_zero = np.zeros(())

if ph.mesh_prefix == 'annulus_':
    R0 = .3
    R1 = .5
    ray = R0 + (s_lgr * (R1-R0))
    s_lgr = ray * np.cos(mth.pi/2 * t_lgr)
    t_lgr = ray * np.sin(mth.pi/2 * t_lgr)
    sx_zero = s_lgr
    sy_zero = t_lgr
    sx_n = 1./1.4*(s_lgr)
    sy_n =    1.4*(t_lgr)
elif ph.mesh_prefix == 'cavity_':
    s_lgr = 0.5 + 0.2*s_lgr
    t_lgr = 0.4 + 0.2*t_lgr
    sx_zero = s_lgr
    sy_zero = t_lgr
    sx_n = (s_lgr)
    sy_n = (t_lgr)
elif ph.mesh_prefix == 'channel_':
    s_lgr = 0.3 + 0.1*s_lgr
    t_lgr = 0.5 + 0.5*t_lgr
    sx_zero = s_lgr
    sy_zero = t_lgr
    sx_n = (s_lgr)
    sy_n = (t_lgr)
elif ph.mesh_prefix == 'swingbar_':
    s_lgr = 0.5*s_lgr
    t_lgr = 0.45 + 0.1*t_lgr
    sx_zero = s_lgr
    sy_zero = t_lgr
    sx_n = (s_lgr)
    sy_n = (t_lgr+s_lgr**2)

ie_s = np.arange(0,s_lgr.shape[0])

if sum(ph.stampa) !=0:
    results_dir = ph.results_directory+'/'+ph.sim_prefix+'/binary_data/'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    ph.dump_to_json(ph.results_directory+'/'+ph.sim_prefix+'/simulation_parameters.json')
    write_mesh()

ndofs_u = max(x_u.shape)
ndofs_p = max(x_p.shape) + topo_p.shape[0]
ndofs_s = max(ie_s)+1

print('DOFs velocity:   ' + str(2*ndofs_u))
print('DOFs pressure:   ' + str(ndofs_p))
print('DOFs structure:  ' + str(2*ndofs_s))
print('DOFs lagrangian: ' + str(2*ndofs_s))

ux_n = np.zeros((ndofs_u))
uy_n = np.zeros((ndofs_u))
u_n = np.zeros((2*ndofs_u))
l_n = np.zeros((2*ndofs_s))
p_n = np.zeros((ndofs_p))

ux_n_old = ux_n
uy_n_old = uy_n
u_n_old = u_n
p_n_old = p_n
sx_n_old = sx_n
sy_n_old = sy_n
l_n_old = l_n

dx_n = sx_n - sx_zero
dy_n = sy_n - sy_zero
dx_n_old = dx_n
dy_n_old = dy_n

###Assemble the 'static' matrices

MS11 = assemble.u_v_p1_periodic(topo_s,s_lgr,t_lgr,ie_s)
KS11 = assemble.gradu_gradv_p1_ieq(topo_s,s_lgr,t_lgr,ie_s)

MS22 = MS11
MST11 = MS11
MST22 = MS11

KS11 = ph.kappa*KS11
KS22 = KS11

rhs = KS11.dot(dx_n)
rhs = np.hstack([rhs, KS22.dot(dy_n)])

MS = sparse.vstack([
    sparse.hstack([MS11,sparse.csc_matrix((ndofs_s,ndofs_s))]),
    sparse.hstack([sparse.csc_matrix((ndofs_s,ndofs_s)),MS22])
    ])

l_n = sp_la.spsolve(MS.tocsc(), rhs)


(KS11, KS22, MST11, MST22) = structure_m_apply_bc(KS11, KS22, MST11, MST22)

KS = sparse.vstack([
    sparse.hstack([KS11,sparse.csc_matrix((ndofs_s,ndofs_s))]),
    sparse.hstack([sparse.csc_matrix((ndofs_s,ndofs_s)),KS22])
])

MST = sparse.vstack([
    sparse.hstack([MST11,sparse.csc_matrix((ndofs_s,ndofs_s))]),
    sparse.hstack([sparse.csc_matrix((ndofs_s,ndofs_s)),MST22])
    ])

MF11 = ph.rho_fluid*assemble.u_v_p1(topo_u,x_u,y_u)
KF11 = ph.nu*assemble.gradu_gradv_p1(topo_u,x_u,y_u)

(BT1,BT2) = assemble.divu_p_p1_iso_p2_p1p0(topo_p,x_p,y_p,
           topo_u,x_u,y_u,c2f)

BT = sparse.vstack([BT1,BT2])
B = BT.transpose()

(BT1, BT2) = pressure_m_apply_bc(BT1, BT2)

MF = sparse.vstack([
    sparse.hstack( [MF11, sparse.csc_matrix((ndofs_u,ndofs_u)) ] ),
    sparse.hstack( [sparse.csc_matrix((ndofs_u,ndofs_u)), MF11] )
    ])

KF = sparse.vstack([
    sparse.hstack( [KF11, sparse.csc_matrix((ndofs_u,ndofs_u)) ] ),
    sparse.hstack( [sparse.csc_matrix((ndofs_u,ndofs_u)), KF11] )
    ])

BT = sparse.vstack([BT1,BT2])

mean_p = np.zeros((1,ndofs_p))
x_l = x_p[topo_p[0,0:3]]
y_l = y_p[topo_p[0,0:3]]
eval_p = np.zeros((0,2))
# assume all triangles have the same shape/area
(phi_dx,phi_dy,phi,omega) = shp.tri_p1(x_l,y_l,eval_p)

for row in topo_p:
    mean_p[0,row] += omega * np.array([1./3.,1./3.,1./3.,1])

nodes_p = x_p.shape[0]
cells_p = topo_p.shape[0]
MP = sparse.vstack([
    sparse.hstack([assemble.u_v_p1(topo_p[:,0:3],x_p,y_p), sparse.csr_matrix((nodes_p, cells_p))]),
    sparse.hstack([sparse.csr_matrix((cells_p, nodes_p)), omega*sparse.eye(cells_p)])
    ])

big_mass_matrix = sparse.vstack([
    sparse.hstack([MF, sparse.csr_matrix((2*ndofs_u, ndofs_p + 4*ndofs_s + 1))]),
    sparse.hstack([sparse.csr_matrix((ndofs_p, 2*ndofs_u)), MP, sparse.csr_matrix((ndofs_p, 4*ndofs_s + 1))]),
    sparse.hstack([sparse.csr_matrix((2*ndofs_s, 2*ndofs_u+ndofs_p)), MS, sparse.csr_matrix((2*ndofs_s, 2*ndofs_s + 1))]),
    sparse.hstack([sparse.csr_matrix((2*ndofs_s, 2*ndofs_u+ndofs_p+2*ndofs_s)), MS, sparse.csr_matrix((2*ndofs_s, 1))]),
    sparse.hstack([sparse.csr_matrix((1, 2*ndofs_u+ndofs_p+4*ndofs_s)), sparse.eye(1)])
])

###Simulation loop

str_area_zero, _ = eval_str_area()

sol_time = np.zeros((len(ph.stampa)))
step_time = np.zeros((len(ph.stampa)))
energy = np.zeros((len(ph.stampa)))

max_iter = 20
residuals = np.zeros((len(ph.stampa), max_iter))

### Save initial condition
cn_time = 0
write_output()

### Start time loop
for cn_time in range(1,len(ph.stampa)+1):
    step_t0 = time.time()
    current_sol_time = 0

    print('-----------------------------------')
    print('cn_time   = ' + str(cn_time))
    print('t         = ' + str(cn_time*ph.dt))
    print('-----')

    # print('assemble system')
    ###Assemble kinematic coupling and nonlinear convection term
    (G, GT, GT11, GT22) = assemble_kinematic_coupling(sx_n, sy_n)
    (H, HT, HT11, HT22) = (G, GT, GT11, GT22)
    ux_n1 = ux_n
    uy_n1 = uy_n
    u_n1 = u_n
    l_n1 = l_n
    if(ph.fluid_behavior == "Navier-Stokes"):
        S11 = ph.rho_fluid*assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
    else:
        S11 = sparse.csc_matrix((ndofs_u, ndofs_u))
    T11 = S11

    ###Assemble linear system and right hand side
    if ph.time_integration == 'BDF1':
        mat = assemble_blockwise_matrix_BDF1()
        force = assemble_blockwise_force_BDF1(ux_n, uy_n, dx_n, dy_n)
    elif ph.time_integration == 'CN':
        mat = assemble_blockwise_matrix_CN()
        force = assemble_blockwise_force_CN(ux_n, uy_n, u_n, p_n, dx_n, dy_n, l_n)
    elif ph.time_integration == 'TR':
        mat = assemble_blockwise_matrix_TR()
        force = assemble_blockwise_force_TR(ux_n, uy_n, u_n, p_n, dx_n, dy_n, l_n)
    elif ph.time_integration == 'BDF2':
        if cn_time == 1:
            mat = assemble_blockwise_matrix_BDF1()
            force = assemble_blockwise_force_BDF1(ux_n, uy_n, dx_n, dy_n)
        else:
            mat = assemble_blockwise_matrix_BDF2()
            force = assemble_blockwise_force_BDF2(ux_n, uy_n, ux_n_old, uy_n_old, dx_n, dy_n, dx_n_old, dy_n_old)

    # Uncomment the following to save some matrices for the evaluation scripts
    # sparse.save_npz('matrix'+str(ph.time_integration), mat)
    # f = open('rhs', 'wb')
    # np.save(f, force)
    # np.save(f, ndofs_u)
    # np.save(f, ndofs_p)
    # np.save(f, ndofs_s)
    # f.close()

    for k in range(0, max_iter):
        ###Solve linear system
        sol_t0 = time.time()

        ### Experimental code for the iterative linear solver
        # print('calculate preconditioner')
        # fill_factor=300
        # spilu = sp_la.spilu(mat, fill_factor=fill_factor, drop_tol=1e-10)
        # M_x = lambda x: spilu.solve(x)
        # precond = sp_la.LinearOperator(mat.shape, M_x)
        # sol_t0 = time.time()
        # print('solve system')
        # (sol, it) = sp_la.bicgstab(mat, force, M=precond, tol=1e-8)
        # print(it)

        print('solve system')
        sol = sp_la.spsolve(mat,force)
        sol_t1 = time.time()
        current_sol_time += sol_t1 - sol_t0

        print('calculate residual')
        ###Extract current iterates
        u_n1 = sol[0:2*ndofs_u]
        ux_n1 = sol[0:ndofs_u]
        uy_n1 = sol[ndofs_u:2*ndofs_u]
        p_n1 = sol[2*ndofs_u:2*ndofs_u+ndofs_p]
        dx_n1 = sol[2*ndofs_u+ndofs_p:2*ndofs_u+ndofs_p+ndofs_s]
        dy_n1 = sol[2*ndofs_u+ndofs_p+ndofs_s:2*ndofs_u+ndofs_p+2*ndofs_s]
        sx_n1 = sx_zero + dx_n1
        sy_n1 = sy_zero + dy_n1
        l_n1 = sol[2*ndofs_u+ndofs_p+2*ndofs_s:2*ndofs_u+ndofs_p+4*ndofs_s]

        ###Assemble the matrices again with the new computed iterates
        if ph.time_integration == "CN":
            (G, GT, GT11, GT22) = assemble_kinematic_coupling(0.5*(sx_n1 + sx_n), 0.5*(sy_n1 + sy_n))
        else:
            (G, GT, GT11, GT22) = assemble_kinematic_coupling(sx_n1, sy_n1)
        if(ph.fluid_behavior == "Navier-Stokes"):
            S11 = ph.rho_fluid*assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
        else:
            S11 = sparse.csc_matrix((ndofs_u, ndofs_u))

        if ph.time_integration == 'BDF1':
            mat = assemble_blockwise_matrix_BDF1()
        elif ph.time_integration == 'CN':
            mat = assemble_blockwise_matrix_CN()
            rhs = assemble_blockwise_force_CN(ux_n, uy_n, u_n, p_n, dx_n, dy_n, l_n)
        elif ph.time_integration == 'TR':
            mat = assemble_blockwise_matrix_TR()
        elif ph.time_integration == 'BDF2':
            if cn_time == 1:
                mat = assemble_blockwise_matrix_BDF1()
            else:
                mat = assemble_blockwise_matrix_BDF2()

        ### Calculate the residual
        res = l2_norm(big_mass_matrix, mat.dot(sol) - force)
        residuals[cn_time-1, k] = res
        print('Nonlinear solver: ' + str(k+1) + 'th iteration, res = ' + '{:.2e}'.format(res))
        ### Decide whether to stop the nonlinear solver
        if(res < ph.tolerance):
            print('Nonlinear solver converged after ' + str(k+1) + ' iterations.')
            print('-----')
            break
    if k == max_iter-1:
        print('Nonlinear solver did not converge in ' + str(max_iter) + ' iterations.')
        #break

    ###Update solution vector
    ux_n_old = ux_n
    uy_n_old = uy_n
    u_n_old = u_n
    p_n_old = p_n
    sx_n_old = sx_n
    sy_n_old = sy_n
    dx_n_old = dx_n
    dy_n_old = dy_n
    l_n_old = l_n

    u_n = u_n1
    ux_n = ux_n1
    uy_n = uy_n1
    p_n = p_n1
    dx_n = dx_n1
    dy_n = dy_n1
    sx_n = sx_zero + dx_n
    sy_n = sy_zero + dy_n
    l_n = l_n1

    ###Do some nice physics related stuff
    (str_area, invertible) = eval_str_area()
    diffusion = str_area/str_area_zero
    p_all_zero = bool(np.all(p_n==0))
    exploded = bool(np.amax(p_n) > 1e+10)

    indices_out_of_domain = np.where(sx_n > 1.+1e-8)
    indices_out_of_domain = np.append(indices_out_of_domain, np.where(sx_n < -1e-8))
    indices_out_of_domain = np.append(indices_out_of_domain, np.where(sy_n > 1.+1e-8))
    indices_out_of_domain = np.append(indices_out_of_domain, np.where(sy_n < -1e-8))

    nrg =(l2_norm(KS,np.append(dx_n, dy_n)))**2 + (l2_norm(MF,np.append(ux_n, uy_n)))**2
    energy[cn_time-1] = nrg

    if (exploded==True or p_all_zero == True):
        diffusion = 999
    print('diffusion            = ' + str(diffusion))
    print('energy               = ' + str(nrg))
    print('pressure == 0        ? ' + str(p_all_zero))
    print('exploded             ? ' + str(exploded))
    print('solid invertible     ? ' + str(invertible))
    print('nodes outside domain = ' + str(len(indices_out_of_domain)))

    if diffusion > 2:
       print('The simulation was aborted, since it produced nonsense!')
       break
    elif diffusion < .8:
       print('The simulation was aborted, since it produced nonsense!')
       break

    if not invertible:
        print('The simulation was aborted, since it produced nonsense!')
        break

    ###Write output
    if ph.stampa[cn_time-1] == True:
        write_output()
    step_t1 = time.time()
    print('step time = ' + str((step_t1-step_t0)))
    print('sol  time = ' + str(current_sol_time))
    print('-----------------------------------')

    step_time[cn_time-1] = step_t1-step_t0
    sol_time[cn_time-1] = current_sol_time

write_time()
print(np.log10(residuals))
