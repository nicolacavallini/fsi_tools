#! /usr/bin/env python

import time
import os
import sys
import numpy as np
from scipy import sparse
import scipy.sparse.linalg as sp_la
import matplotlib.pyplot as plt
import math as mth
import json

# nicola modules
import lin_tri_mesh as lin_t3
import basis_func as shp
import assemble
import la_utils
import viewers
import geom_utils as geom
from shapely.geometry import Polygon

from preconditioner import BlockPreconditioner
from parameters_handler import ParametersHandler

x_left = 0.
x_right = 10.
y_bottom = 0.
y_top = 1.64

hole_x_left = 0.6
hole_x_right = 1.
hole_y_bottom = 0.6
hole_y_top = 1.

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
    f.close()
    return

def apply_bc_rhs(f_rhs_x, f_rhs_y):
    #upper boundary
    bc_id = np.where(y_u > y_top-delta_x/10)
    f_rhs_x[bc_id,:] = 0.
    f_rhs_y[bc_id,:] = 0.

    #lower boundary
    bc_id = np.where(y_u < y_bottom+delta_x/10)
    f_rhs_x[bc_id,:] = 0
    f_rhs_y[bc_id,:] = 0

    #right boundary

    #left boundary
    bc_id = np.where(x_u < x_left+delta_x/10)
    f_rhs_x[bc_id,:] = np.reshape(np.multiply(-1*(y_u[bc_id]-y_top), (y_u[bc_id] - y_bottom)), f_rhs_x[bc_id,:].shape)
    f_rhs_y[bc_id,:] = 0.

    #hole upper boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_top-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_right+delta_x/10]
        ),axis=0))
    f_rhs_x[bc_id,:] = 0.
    f_rhs_y[bc_id,:] = 0.

    #hole lower boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_bottom+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_right+delta_x/10]
        ),axis=0))
    f_rhs_x[bc_id,:] = 0
    f_rhs_y[bc_id,:] = 0

    #hole right boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_right-delta_x/10, x_u<hole_x_right+delta_x/10]
        ),axis=0))
    f_rhs_x[bc_id,:] = 0.
    f_rhs_y[bc_id,:] = 0.

    #hole left boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_left+delta_x/10]
        ),axis=0))
    f_rhs_x[bc_id,:] = 0.
    f_rhs_y[bc_id,:] = 0.

    return f_rhs_x, f_rhs_y

def apply_bc_mat(D11, D22):
    #upper boundary
    bc_id = np.where(y_u > y_top-delta_x/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #lower boundary
    bc_id = np.where(y_u < y_bottom+delta_x/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #right boundary
    bc_id = np.where(x_u > x_right-delta_x/10)
    # D11 = la_utils.set_diag(D11, bc_id)
    # D22 = la_utils.set_diag(D22, bc_id)

    #left boundary
    bc_id = np.where(x_u < x_left+delta_x/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #hole upper boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_top-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_right+delta_x/10]
        ),axis=0))
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #hole lower boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_bottom+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_right+delta_x/10]
        ),axis=0))
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #hole right boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_right-delta_x/10, x_u<hole_x_right+delta_x/10]
        ),axis=0))
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #hole left boundary
    bc_id = np.where(np.all(np.array(
        [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_left+delta_x/10]
        ),axis=0))
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    return D11, D22

def assemble_blockwise_force_BDF1():
    size = 2*ndofs_u+ndofs_p
    rhs = np.zeros((size,1))

    f_rhs_x = ph.rho_fluid/ph.dt*M11.dot(ux_n)
    f_rhs_y = ph.rho_fluid/ph.dt*M22.dot(uy_n)

    f_rhs_x, f_rhs_y = apply_bc_rhs(f_rhs_x, f_rhs_y)

    rhs[0:ndofs_u,:] = f_rhs_x
    rhs[ndofs_u:2*ndofs_u,:] = f_rhs_y

    return np.reshape(rhs, (size))

def assemble_blockwise_matrix_BDF1():
    S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
    D11 = ph.rho_fluid/ph.dt*M11 + ph.nu*A11 + ph.rho_fluid*S11
    D22 = ph.rho_fluid/ph.dt*M11 + ph.nu*A11 + ph.rho_fluid*S11
    S12 = sparse.csr_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csr_matrix((ndofs_u, ndofs_u))
    D33 = sparse.csr_matrix((ndofs_p, ndofs_p))

    (D11, D22) = apply_bc_mat(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -BT1]),# sparse.csr_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -BT2]),# sparse.csr_matrix((ndofs_u, 1))]),
        sparse.hstack([ -B,       D33])#,  mean_p.transpose()]),
        # sparse.hstack([sparse.csr_matrix((1, 2*ndofs_u)), mean_p, sparse.csr_matrix((1,1))])
    ], "csr")
    return mat

def assemble_blockwise_force_BDF2():
    size = 2*ndofs_u+ndofs_p
    rhs = np.zeros((size,1))

    f_rhs_x = ph.rho_fluid/ph.dt*M11.dot(2*ux_n - 0.5*ux_n_old)
    f_rhs_y = ph.rho_fluid/ph.dt*M22.dot(2*uy_n - 0.5*uy_n_old)

    (f_rhs_x, f_rhs_y) = apply_bc_rhs(f_rhs_x, f_rhs_y)

    rhs[0:ndofs_u,:] = f_rhs_x
    rhs[ndofs_u:2*ndofs_u,:] = f_rhs_y

    return np.reshape(rhs, (size))

def assemble_blockwise_matrix_BDF2():
    S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
    D11 = 1.5*ph.rho_fluid/ph.dt*M11 + ph.nu*A11 + ph.rho_fluid*S11
    D22 = 1.5*ph.rho_fluid/ph.dt*M11 + ph.nu*A11 + ph.rho_fluid*S11
    S12 = sparse.csr_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csr_matrix((ndofs_u, ndofs_u))

    (D11, D22) = apply_bc_mat(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -BT1]),#, sparse.csr_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -BT2]),#, sparse.csr_matrix((ndofs_u, 1))]),
        sparse.hstack([-B, sparse.csr_matrix((ndofs_p,ndofs_p))])#, mean_p.transpose()]),
        # sparse.hstack([sparse.csr_matrix((1, 2*ndofs_u)), mean_p, sparse.csr_matrix((1,1))])
    ], "csr")
    return mat

def assemble_blockwise_force_Theta(S11):
    size = 2*ndofs_u+ndofs_p
    rhs = np.zeros((size,1))

    f_rhs_x = ph.rho_fluid/ph.dt*M11.dot(ux_n) - ph.nu*0.5*A11.dot(ux_n) \
        - 0.5*ph.rho_fluid*S11.dot(ux_n) + 0.5*BT1.dot(p_n)
    f_rhs_y = ph.rho_fluid/ph.dt*M11.dot(uy_n) - ph.nu*0.5*A11.dot(uy_n) \
        - 0.5*ph.rho_fluid*S11.dot(uy_n) + 0.5*BT2.dot(p_n)

    (f_rhs_x, f_rhs_y) = apply_bc_rhs(f_rhs_x, f_rhs_y)

    rhs[0:ndofs_u,:] = f_rhs_x
    rhs[ndofs_u:2*ndofs_u,:] = f_rhs_y

    return np.reshape(rhs, (size))

def assemble_blockwise_matrix_Theta(S11):
    D11 = ph.rho_fluid/ph.dt*M11 + 0.5*ph.nu*A11 + 0.5*ph.rho_fluid*S11
    D22 = ph.rho_fluid/ph.dt*M11 + 0.5*ph.nu*A11 + 0.5*ph.rho_fluid*S11
    S12 = sparse.csr_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csr_matrix((ndofs_u, ndofs_u))

    (D11, D22) = apply_bc_mat(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -0.5*BT1]),# sparse.csr_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -0.5*BT2]),# sparse.csr_matrix((ndofs_u, 1))]),
        sparse.hstack([-B, sparse.csr_matrix((ndofs_p,ndofs_p))])#, mean_p.transpose()]),
        # sparse.hstack([sparse.csr_matrix((1, 2*ndofs_u)), mean_p, sparse.csr_matrix((1,1))])
    ], "csr")
    return mat

def write_output():
    filename = results_dir +'cn_time_'+str(cn_time).zfill(ph.time_index_digits)
    f = open(filename,"wb")
    np.save(f,u_n)
    np.save(f,p_n)
    f.close()
    print('--------------------------------------')
    print('results saved to:')
    print(filename)
    print('--------------------------------------')
    return

def l2_norm(M, g):
    l2_g = M.dot(g)
    l2_g = np.dot(l2_g.transpose(),g)
    l2_g = mth.sqrt(l2_g)
    return l2_g

np.set_printoptions(precision=4)
np.set_printoptions(suppress=True)

if len(sys.argv) > 1:
    ph = ParametersHandler(sys.argv[1])
else:
    ph = ParametersHandler('simulation_parameters.json')
ph.simulation_info()

nx_p = ph.n_delta_x
delta_x = 1./nx_p
ny_p = nx_p
delta_y = 1./ny_p

fn = '../mesh_collection/straight_'+str(ph.n_delta_x)+'.msh'
fnr = '../mesh_collection/straight_'+str(ph.n_delta_x)+'_refined.msh'
(topo_p,x_p,y_p,topo_u,x_u,y_u,c2f) = \
        lin_t3.load_t3_iso_t6_file(fn, fnr)

if sum(ph.stampa) !=0:
    results_dir = ph.results_directory+'/'+ph.sim_prefix+'/binary_data/'
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    ph.dump_to_json(ph.results_directory+'/'+ph.sim_prefix+'/simulation_parameters.json')
    write_mesh()

ndofs_u = max(x_u.shape)
ndofs_p = max(x_p.shape) + topo_p.shape[0]

print('ndofs u = ' + str(2*ndofs_u))
print('ndofs p = ' + str(ndofs_p))

u_n = np.zeros((2*ndofs_u,1))
p_n = np.zeros((ndofs_p,1))
ux_n = np.zeros((ndofs_u,1))
uy_n = np.zeros((ndofs_u,1))
ux_n_old = np.zeros((ndofs_u,1))
uy_n_old = np.zeros((ndofs_u,1))

M11 = assemble.u_v_p1(topo_u,x_u,y_u)
A11 = assemble.gradu_gradv_p1(topo_u,x_u,y_u)
M22 = M11

(BT1,BT2) = assemble.divu_p_p1_iso_p2_p1p0(topo_p,x_p,y_p,
           topo_u,x_u,y_u,c2f)
# (BT1,BT2) = assemble.divu_p_p1_iso_p2_p1(topo_p,x_p,y_p,
#            topo_u,x_u,y_u,c2f)
BT = sparse.vstack([BT1,BT2])
B = BT.transpose()

mean_p = np.zeros((1,ndofs_p))
for row in topo_p:
    x_l = x_p[row[0:3]]
    y_l = y_p[row[0:3]]
    eval_p = np.zeros((0,2))
    (phi_dx,phi_dy,phi,omega) = shp.tri_p1(x_l,y_l,eval_p)
    mean_p[0,row] += omega * np.array([1./3.,1./3.,1./3.,1])
    # mean_p[0,row] += omega * np.array([1./3.,1./3.,1./3.])

mean_pT = mean_p.transpose()

#upper boundary
bc_id = np.where(y_u > y_top-delta_x/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

#lower boundary
bc_id = np.where(y_u < y_bottom+delta_x/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

#right boundary
bc_id = np.where(x_u > x_right-delta_x/10)
# BT1 = la_utils.clear_rows(BT1,bc_id)
# BT2 = la_utils.clear_rows(BT2,bc_id)

#left boundary
bc_id = np.where(x_u < x_left+delta_x/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

#hole upper boundary
bc_id = np.where(np.all(np.array(
    [y_u>hole_y_top-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_right+delta_x/10]
    ),axis=0))
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

#hole lower boundary
bc_id = np.where(np.all(np.array(
    [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_bottom+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_right+delta_x/10]
    ),axis=0))
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

#hole right boundary
bc_id = np.where(np.all(np.array(
    [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_right-delta_x/10, x_u<hole_x_right+delta_x/10]
    ),axis=0))
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

#hole left boundary
bc_id = np.where(np.all(np.array(
    [y_u>hole_y_bottom-delta_x/10, y_u<hole_y_top+delta_x/10, x_u>hole_x_left-delta_x/10, x_u<hole_x_left+delta_x/10]
    ),axis=0))
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

M = sparse.vstack([
     sparse.hstack( [M11, sparse.csr_matrix((ndofs_u,ndofs_u))] ),
     sparse.hstack( [sparse.csr_matrix((ndofs_u,ndofs_u)), M11] )
     ])

max_iter = 10
residuals = np.zeros((len(ph.stampa), max_iter))
#### start time steppig procedure
for cn_time in range(0,len(ph.stampa)):
    step_t0 = time.time()
    t_sol = 0
    u_n1 = u_n
    ux_n1 = ux_n
    uy_n1 = uy_n
    p_n1 = p_n

    if ph.time_integration == 'BDF1':
        force = assemble_blockwise_force_BDF1()
        mat = assemble_blockwise_matrix_BDF1()
    elif ph.time_integration == 'Theta'  or cn_time == 0:
        S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
        force = assemble_blockwise_force_Theta(S11)
        mat = assemble_blockwise_matrix_Theta(S11)
    else:
        force = assemble_blockwise_force_BDF2()
        mat = assemble_blockwise_matrix_BDF2()

    for k in range(max_iter):
        sol = sp_la.spsolve(mat,force)

        u_n1 = np.reshape(sol[0:2*ndofs_u], u_n.shape)
        p_n1 = np.reshape(sol[2*ndofs_u:2*ndofs_u+ndofs_p], (ndofs_p, 1))
        ux_n1 = np.reshape(u_n1[0      :  ndofs_u], ux_n.shape)
        uy_n1 = np.reshape(u_n1[ndofs_u:2*ndofs_u], uy_n.shape)

        if ph.time_integration == 'BDF1':
            mat = assemble_blockwise_matrix_BDF1()
        elif ph.time_integration == 'Theta' or cn_time == 0:
            S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
            mat = assemble_blockwise_matrix_Theta(S11)
        else:
            mat = assemble_blockwise_matrix_BDF2()

        res = np.linalg.norm(mat.dot(sol) - force)
        residuals[cn_time,k] = res
        print('Nonlinear solver, k = ' + str(k+1).zfill(2) + ', residual = ' + str(res))
        if res < ph.tolerance:
            print('Nonlinear solver converged after ' + str(k+1) + ' steps')
            break

    u_n_old = u_n
    p_n_old = p_n
    ux_n_old = ux_n
    uy_n_old = uy_n

    u_n = np.reshape(sol[0:2*ndofs_u], (2*ndofs_u, 1))
    p_n = np.reshape(sol[2*ndofs_u:2*ndofs_u+ndofs_p], (ndofs_p, 1))
    bc_id = np.where(x_p > 1-delta_x/10)
    p_n[bc_id,0] = 0
    ux_n = np.reshape(u_n[0      :  ndofs_u], (ndofs_u, 1))
    uy_n = np.reshape(u_n[ndofs_u:2*ndofs_u], (ndofs_u, 1))

    if ph.stampa[cn_time] == True:
        write_output()
    step_t1 = time.time()

    print('--------------------------------------')
    print('cn_time   = ' + str(cn_time))
    print('t         = ' + str(cn_time*ph.dt))
    print('l2 norm u = ' + str(l2_norm(M, u_n)))
    print('step time = ' + str((step_t1-step_t0)))
    print('sol  time = ' + str(t_sol))
    print('--------------------------------------')

print(np.log10(residuals))
