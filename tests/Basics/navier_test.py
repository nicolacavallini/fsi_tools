#! /bin/env python

#import matplotlib.pyplot as plt
import numpy as np
import gc
import scipy.sparse.linalg as sp_la
from scipy import sparse
import time
import sys

sys.path.append('../../modules')
import assemble
import basis_func as shp
import la_utils
import lin_tri_mesh as lin_t3
#from preconditioner import BlockPreconditioner
import quadrature
#import viewers

def analytical_u(t, x, y):
    analytical_x =  (4*np.sin(t)+5) * x**2 * (1-x)**2 * (2*y - 6*y**2 + 4*y**3)
    analytical_y = -(4*np.sin(t)+5) * (2*x - 6*x**2 + 4*x**3) * y**2 * (1-y)**2
    analytical = np.reshape(np.append(analytical_x, analytical_y), (2*len(x), 1))
    return analytical

def analytical_p(t, x_p, y_p):
    p_1 = x_p - 0.5
    p_0 = np.zeros(topo_p.shape[0])
    return np.reshape(np.append(p_1, p_0), (ndofs_p, 1))

def analytical(t, x_u, y_u, x_p, y_p):
    return sparse.vstack([analytical_u(t, x_u, y_u), analytical_p(t, x_p, y_p),0])

def f(t):
    f_x = analytical_f_1(t, x_u, y_u)
    f_y = analytical_f_2(t, x_u, y_u)
    f_stacked = np.reshape(np.append(f_x, f_y), (2*ndofs_u, 1))
    return f_stacked

def analytical_f_1(t, x, y):
    ndofs = x.shape[0]
    ## time derivative
    f_x =  (4*np.cos(t)) * x**2 * (1-x)**2 * (2*y - 6*y**2 + 4*y**3)
    ## convection term
    f_x +=  (4*np.sin(t)+5)**2 * x**2 * (1-x)**2 * (2*y - 6*y**2 + 4*y**3)**2 * (2*x - 6*x**2 + 4*x**3)
    f_x += -(4*np.sin(t)+5)**2 * (2*x - 6*x**2 + 4*x**3) * y**2 * (1-y)**2 * y**2 * (1-x)**2 * (2 - 12*y + 12*y**2)
    ## diffusion term
    f_x += -(4*np.sin(t)+5) * ((2 - 12*x + 12*x**2) * (2*y - 6*y**2 + 4*y**3) + x**2 * (1-x)**2 * (-12 + 24*y))
    ## pressure gradient
    f_x +=  -1
    return f_x

def analytical_f_2(t, x, y):
    dofs = x.shape[0]
    ## time derivative
    f_y = -(4*np.cos(t)) * (2*x - 6*x**2 + 4*x**3) * y**2 * (1-y)**2
    ## convection term
    f_y += -(4*np.sin(t)+5)**2 * x**2 * (1-x)**2 * (2*y - 6*y**2 + 4*y**3) * (2 - 12*x + 12*x**2) * y**2 * (1-y)**2
    f_y +=  (4*np.sin(t)+5)**2 * (2*x - 6*x**2 + 4*x**3)**2 * y**2 * (1-y)**2 * (2*y - 6*y**2 + 4*y**3)
    ## diffusion term
    f_y += -(4*np.sin(t)+5) * (-(-12 + 24*x) * y**2 * (1-y)**2 - (2*x - 6*x**2 + 4*x**3) * (2 - 12*y + 12*y**2))
    ## pressure gradient
    f_y +=  0
    return f_y

def assemble_blockwise_force_BDF1(t, dt, u_BDF1):
    g_1 = lambda x,y: analytical_f_1(t, x, y)
    g_2 = lambda x,y: analytical_f_2(t, x, y)
    g_1_rhs = quadrature.fem_rhs(g_1, x_u, y_u, topo_u)
    g_2_rhs = quadrature.fem_rhs(g_2, x_u, y_u, topo_u)

    f_rhs_x = M.dot(u_BDF1[0:ndofs_u]) + dt*np.reshape(g_1_rhs, (ndofs_u, 1)) 
    f_rhs_y = M.dot(u_BDF1[ndofs_u:2*ndofs_u]) + dt*np.reshape(g_2_rhs, (ndofs_u, 1)) 

    return apply_rhs_bc(f_rhs_x, f_rhs_y)

def assemble_blockwise_matrix_BDF1(dt, ux_n1, uy_n1):
    S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
    D11 = M + dt*K + dt*S11
    D22 = M + dt*K + dt*S11
    S12 = sparse.csc_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csc_matrix((ndofs_u, ndofs_u))

    (D11, D22) = apply_mat_bc(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -dt*BT1, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -dt*BT2, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([-B, sparse.csc_matrix((ndofs_p,ndofs_p)), mean_p.transpose()]),
        sparse.hstack([sparse.csc_matrix((1, 2*ndofs_u)), mean_p, sparse.csc_matrix((1,1))])
    ], "csc")
    return mat

def assemble_blockwise_force_BDF2(t, dt, u_BDF2, u_BDF2_old):
    g_1 = lambda x,y: analytical_f_1(t, x, y)
    g_2 = lambda x,y: analytical_f_2(t, x, y)
    g_1_rhs = quadrature.fem_rhs(g_1, x_u, y_u, topo_u)
    g_2_rhs = quadrature.fem_rhs(g_2, x_u, y_u, topo_u)

    f_rhs_x = M.dot(2*u_BDF2[0:ndofs_u] - 0.5*u_BDF2_old[0:ndofs_u]) + np.reshape(dt*g_1_rhs, (ndofs_u, 1)) 
    f_rhs_y = M.dot(2*u_BDF2[ndofs_u:2*ndofs_u] - 0.5*u_BDF2_old[ndofs_u:2*ndofs_u]) + np.reshape(dt*g_2_rhs, (ndofs_u, 1)) 

    return apply_rhs_bc(f_rhs_x, f_rhs_y)

def assemble_blockwise_matrix_BDF2(dt, ux_n1, uy_n1):
    S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
    D11 = 1.5*M + dt*K + dt*S11
    D22 = 1.5*M + dt*K + dt*S11
    S12 = sparse.csc_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csc_matrix((ndofs_u, ndofs_u))

    (D11, D22) = apply_mat_bc(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -dt*BT1, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -dt*BT2, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([-B, sparse.csc_matrix((ndofs_p,ndofs_p)), mean_p.transpose()]),
        sparse.hstack([sparse.csc_matrix((1, 2*ndofs_u)), mean_p, sparse.csc_matrix((1,1))])
    ], "csc")
    return mat

def assemble_blockwise_force_CN(t, dt, S11, T11, u_CN):
    g_1 = lambda x,y: analytical_f_1(t-0.5*dt, x, y)
    g_2 = lambda x,y: analytical_f_2(t-0.5*dt, x, y)
    g_1_rhs = quadrature.fem_rhs(g_1, x_u, y_u, topo_u)
    g_2_rhs = quadrature.fem_rhs(g_2, x_u, y_u, topo_u)

    f_rhs_x = M.dot(u_CN[0:ndofs_u]) - dt*0.5*K.dot(u_CN[0:ndofs_u])
    f_rhs_x += - dt*0.25*(S11+T11).dot(u_CN[0:ndofs_u])
    f_rhs_x += np.reshape(dt*(g_1_rhs), (ndofs_u, 1)) 

    f_rhs_y = M.dot(u_CN[ndofs_u:2*ndofs_u]) - dt*0.5*K.dot(u_CN[ndofs_u:2*ndofs_u])
    f_rhs_y += - dt*0.25*(S11+T11).dot(u_CN[ndofs_u:2*ndofs_u])
    f_rhs_y += np.reshape(dt*(g_2_rhs), (ndofs_u, 1)) 

    return apply_rhs_bc(f_rhs_x, f_rhs_y)

def assemble_blockwise_matrix_CN(dt, S11, T11):

    D11 = M + dt*0.5*K + dt*0.25*(S11+T11)
    D22 = M + dt*0.5*K + dt*0.25*(S11+T11)
    S12 = sparse.csc_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csc_matrix((ndofs_u, ndofs_u))

    (D11, D22) = apply_mat_bc(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -dt*BT1, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -dt*BT2, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([-dt*B, sparse.csc_matrix((ndofs_p,ndofs_p)), mean_p.transpose()]),
        sparse.hstack([sparse.csc_matrix((1, 2*ndofs_u)), mean_p, sparse.csc_matrix((1,1))])
    ], "csc")
    return mat

def assemble_blockwise_force_TR(t, dt, S11, T11, u_CN):
    g_1 = lambda x,y: analytical_f_1(t, x, y) + analytical_f_1(t - dt, x, y)
    g_2 = lambda x,y: analytical_f_2(t, x, y) + analytical_f_2(t - dt, x, y)
    g_1_rhs = 0.5*quadrature.fem_rhs(g_1, x_u, y_u, topo_u)
    g_2_rhs = 0.5*quadrature.fem_rhs(g_2, x_u, y_u, topo_u)

    f_rhs_x = M.dot(u_CN[0:ndofs_u]) - dt*0.5*K.dot(u_CN[0:ndofs_u])
    f_rhs_x += - dt*0.5*(T11).dot(u_CN[0:ndofs_u])
    f_rhs_x += np.reshape(dt*(g_1_rhs), (ndofs_u, 1))

    f_rhs_y = M.dot(u_CN[ndofs_u:2*ndofs_u]) - dt*0.5*K.dot(u_CN[ndofs_u:2*ndofs_u])
    f_rhs_y += - dt*0.5*(T11).dot(u_CN[ndofs_u:2*ndofs_u])
    f_rhs_y += np.reshape(dt*(g_2_rhs), (ndofs_u, 1))

    return apply_rhs_bc(f_rhs_x, f_rhs_y)

def assemble_blockwise_matrix_TR(dt, S11, T11):

    D11 = M + dt*0.5*K + dt*0.5*(S11)
    D22 = M + dt*0.5*K + dt*0.5*(S11)
    S12 = sparse.csc_matrix((ndofs_u, ndofs_u))
    S21 = sparse.csc_matrix((ndofs_u, ndofs_u))

    (D11, D22) = apply_mat_bc(D11, D22)

    #### assembly of Navier-Stokes system
    mat = sparse.vstack([
        sparse.hstack([D11, S12, -dt*BT1, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([S21, D22, -dt*BT2, sparse.csc_matrix((ndofs_u, 1))]),
        sparse.hstack([-dt*B, sparse.csc_matrix((ndofs_p,ndofs_p)), mean_p.transpose()]),
        sparse.hstack([sparse.csc_matrix((1, 2*ndofs_u)), mean_p, sparse.csc_matrix((1,1))])
    ], "csc")
    return mat


def l2_norm(M, g):
    l2_g = M.dot(g)
    l2_g = np.dot(l2_g.transpose(),g)
    l2_g = np.sqrt(l2_g)
    return l2_g

def apply_rhs_bc(f_rhs_x, f_rhs_y):
    size = 2*ndofs_u+ndofs_p+1
    rhs = np.zeros((size,1))

    #upper boundary
    bc_id = np.where(y_u > 1-dx/10)
    f_rhs_x[bc_id,:] = 0
    f_rhs_y[bc_id,:] = 0

    #lower boundary
    bc_id = np.where(y_u < dx/10)
    f_rhs_x[bc_id,:] = 0
    f_rhs_y[bc_id,:] = 0

    #right boundary
    bc_id = np.where(x_u > 1-dx/10)
    f_rhs_x[bc_id,:] = 0
    f_rhs_y[bc_id,:] = 0

    #left boundary
    bc_id = np.where(x_u < dx/10)
    f_rhs_x[bc_id,:] = 0
    f_rhs_y[bc_id,:] = 0

    rhs[0:ndofs_u,:] = f_rhs_x
    rhs[ndofs_u:2*ndofs_u,:] = f_rhs_y

    return np.reshape(rhs, (size))

def apply_mat_bc(D11, D22):
    #lower boundary
    bc_id = np.where(y_u < dx/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #upper boundary
    bc_id = np.where(y_u > 1-dx/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #left boundary
    bc_id = np.where(x_u < dx/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    #right boundary
    bc_id = np.where(x_u > 1-dx/10)
    D11 = la_utils.set_diag(D11, bc_id)
    D22 = la_utils.set_diag(D22, bc_id)

    return D11, D22

def l2_norm(M,g):
    l2_g = M.dot(g)
    l2_g = np.dot(l2_g.transpose(),g)
    l2_g = np.sqrt(l2_g)
    return l2_g

if len(sys.argv) > 1:
    n = int(sys.argv[1])
else:
    n = 10
dx = 1./n
print('dx = ' + str(dx))

T = 5
CN = 0.5
TOL = 1e-8
max_iter = 10

n_runs = 5

(topo_p,x_p,y_p,topo_u,x_u,y_u,c2f) = lin_t3.mesh_t3_iso_t6(n,n,dx,dx)
(topo_p,x_p,y_p) = lin_t3.mesh_t3_t0(n,n,dx,dx)
print('Mesh generation finished')

K = assemble.gradu_gradv_p1(topo_u,x_u,y_u)
M = assemble.u_v_p1(topo_u,x_u,y_u)
(BT1,BT2) = assemble.divu_p_p1_iso_p2_p1p0(topo_p,x_p,y_p,topo_u,x_u,y_u,c2f)
BT = sparse.vstack([BT1,BT2])
B = BT.transpose()

ndofs_u = BT1.shape[0]
ndofs_p = BT1.shape[1]
print('dofs u = ' + str(2*ndofs_u))
print('dofs p = ' + str(ndofs_p))

bc_id = np.where(y_u > 1-dx/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

bc_id = np.where(y_u < dx/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

bc_id = np.where(x_u > 1-dx/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

bc_id = np.where(x_u < dx/10)
BT1 = la_utils.clear_rows(BT1,bc_id)
BT2 = la_utils.clear_rows(BT2,bc_id)

M_2D = sparse.vstack([
    sparse.hstack([M, sparse.csc_matrix(M.shape)]),
    sparse.hstack([sparse.csc_matrix(M.shape), M])
], "csc")
K_2D = sparse.vstack([
    sparse.hstack([K, sparse.csc_matrix(M.shape)]),
    sparse.hstack([sparse.csc_matrix(M.shape), K])
], "csc")

mean_p = np.zeros((1,ndofs_p))
x_l = x_p[topo_p[0,0:3]]
y_l = y_p[topo_p[0,0:3]]
eval_p = np.zeros((0,2))
(phi_dx,phi_dy,phi,omega) = shp.tri_p1(x_l,y_l,eval_p)

for row in topo_p:
    mean_p[0,row] += omega * np.array([1./3.,1./3.,1./3., 1.])

nodes_p = x_p.shape[0]
cells_p = topo_p.shape[0]
MP = sparse.vstack([
    sparse.hstack([assemble.u_v_p1(topo_p[:,0:3],x_p,y_p), sparse.csr_matrix((nodes_p, cells_p))]),
    sparse.hstack([sparse.csr_matrix((cells_p, nodes_p)), omega*sparse.eye(cells_p)])
    ])

big_mass_matrix = sparse.vstack([
    sparse.hstack([M_2D, sparse.csr_matrix((2*ndofs_u, ndofs_p + 1))]),
    sparse.hstack([sparse.csr_matrix((ndofs_p, 2*ndofs_u)), MP, sparse.csr_matrix((ndofs_p, 1))]),
    sparse.hstack([sparse.csr_matrix((1, 2*ndofs_u+ndofs_p)), sparse.eye(1)])
])

print('Assembled mass, stiffness and pressure matrix')

err_BDF1 = np.zeros((n_runs))
err_BDF2 = np.zeros((n_runs))
err_CN = np.zeros((n_runs))
err_TR = np.zeros((n_runs))
err_BDF1_ref = np.zeros((n_runs))
err_BDF2_ref = np.zeros((n_runs))
err_CN_ref = np.zeros((n_runs))
err_TR_ref = np.zeros((n_runs))
BDF1 = np.zeros((2*ndofs_u, n_runs))
BDF2 = np.zeros((2*ndofs_u, n_runs))
CN = np.zeros((2*ndofs_u, n_runs))
TR = np.zeros((2*ndofs_u, n_runs))
ref = np.zeros((2*ndofs_u))

nonlin_conv_ind = np.zeros((4, n_runs))

### calculate reference solution
dt_ref = 0.01
# dt = dt_ref
# N = int(np.round(T/dt+1))
# print('Calculate reference solution')
# print('dt = ' + str(dt) + ', ' + str(N) + ' time steps to solve')
#
# u_0 = analytical(0, x_u, y_u, x_p, y_p)
# u_1 = analytical(dt, x_u, y_u, x_p, y_p)
#
# u_CN = u_1.toarray()
#
# ### start time loop for reference solution
# for k in range(2,N):
#     print('t = ' + str(k*dt))
#
#     f_x = lambda x, y: analytical_u(k*dt, x, y)[0:len(x)]
#     f_y = lambda x, y: analytical_u(k*dt, x, y)[len(x):2*len(x)]
#
#     t0_CN = time.time()
#     ux_n1 = np.reshape(u_CN[0:ndofs_u], (ndofs_u, 1))
#     uy_n1 = np.reshape(u_CN[ndofs_u:2*ndofs_u], (ndofs_u, 1))
#     assemble_t0 = time.time()
#     rhs_CN = assemble_blockwise_force_CN(k*dt)
#     M_CN = assemble_blockwise_matrix_CN()
#     assemble_t1 = time.time()
#     ### Start nonlinear solver for CN
#     for nonlin_ind in range(max_iter):
#         precond_t0 = time.time()
#         spilu = sp_la.spilu(M_CN, fill_factor=300, drop_tol=1e-6)
#         M_x = lambda x: spilu.solve(x)
#         precond = sp_la.LinearOperator((2*ndofs_u+ndofs_p+1, 2*ndofs_u+ndofs_p+1), M_x)
#         precond_t1 = time.time()
#         sol_t0 = time.time()
#         sol = sp_la.bicgstab(M_CN, rhs_CN, M=precond, tol=1e-8)[0]
#         sol_t1 = time.time()
#         ux_n1 = np.reshape(sol[0:ndofs_u], (ndofs_u, 1))
#         uy_n1 = np.reshape(sol[ndofs_u:2*ndofs_u], (ndofs_u, 1))
#         res_t0 = time.time()
#         M_CN = assemble_blockwise_matrix_CN()
#         res = l2_norm(big_mass_matrix, M_CN.dot(sol) - rhs_CN)
#         res_t1 = time.time()
#         print('reference, res = ' + str(res))
#         if res < TOL:
#             break
#         ### End of nonlinear solver
#     u_CN = np.reshape(sol, (2*ndofs_u + ndofs_p + 1, 1))
#
#     ### End of time loop
#
# ref = u_CN
ref = np.zeros((2*ndofs_u + ndofs_p + 1, 1))

### End of computation of reference solution



### start loop over different time steps
for t_ind in range(0, n_runs):
    dt = 0.5*T*2**(-t_ind)
    N = int(np.round(T/dt+1))
    print('dt = ' + str(dt) + ', ' + str(N) + ' time steps to solve')

    u_0 = analytical(0, x_u, y_u, x_p, y_p)
    u_1 = analytical(dt, x_u, y_u, x_p, y_p)

    u_BDF1 = u_1.toarray()
    u_BDF2 = u_1.toarray()
    u_BDF2_old = u_0.toarray()
    u_CN = u_1.toarray()
    u_TR = u_1.toarray()

    ### start time loop for dt
    for k in range(2,N):
        print('t = ' + str(k*dt))

        f_x = lambda x, y: analytical_u(k*dt, x, y)[0:len(x)]
        f_y = lambda x, y: analytical_u(k*dt, x, y)[len(x):2*len(x)]

        ### BDF1/Backward Euler
        ux_n1 = np.reshape(u_BDF1[0:ndofs_u], (ndofs_u, 1))
        uy_n1 = np.reshape(u_BDF1[ndofs_u:2*ndofs_u], (ndofs_u, 1))
        rhs_BDF1 = assemble_blockwise_force_BDF1(k*dt, dt, u_BDF1)
        M_BDF1 = assemble_blockwise_matrix_BDF1(dt, ux_n1, uy_n1).tocsc()
        ### start nonlinear solver for BDF1
        for nonlin_ind in range(max_iter):
            spilu = sp_la.spilu(M_BDF1, fill_factor=300, drop_tol=1e-6)
            M_x = lambda x: spilu.solve(x)
            precond = sp_la.LinearOperator((2*ndofs_u+ndofs_p+1, 2*ndofs_u+ndofs_p+1), M_x)
            sol = sp_la.bicgstab(M_BDF1, rhs_BDF1, M=precond, tol=TOL)[0]
            ux_n1 = np.reshape(sol[0:ndofs_u], (ndofs_u, 1))
            uy_n1 = np.reshape(sol[ndofs_u:2*ndofs_u], (ndofs_u, 1))
            M_BDF1 = assemble_blockwise_matrix_BDF1(dt, ux_n1, uy_n1)
            res = l2_norm(big_mass_matrix, M_BDF1.dot(sol) - rhs_BDF1)
            print('BDF1, res = ' + str(res))
            if res < TOL:
                # store the maximum number of nonlinear iterations
                nonlin_conv_ind[0,t_ind] = np.maximum(nonlin_ind+1, nonlin_conv_ind[0,t_ind])
                break
            if(nonlin_ind == max_iter-1):
                # nonlinear iterator did not converge
                nonlin_conv_ind[0,t_ind] = -1
        u_BDF1 = np.reshape(sol, (2*ndofs_u + ndofs_p + 1, 1))
        gc.collect()

        ### BDF2
        ux_n1 = np.reshape(u_BDF2[0:ndofs_u], (ndofs_u, 1))
        uy_n1 = np.reshape(u_BDF2[ndofs_u:2*ndofs_u], (ndofs_u, 1))
        rhs_BDF2 = assemble_blockwise_force_BDF2(k*dt, dt, u_BDF2, u_BDF2_old)
        M_BDF2 = assemble_blockwise_matrix_BDF2(dt, ux_n1, uy_n1)
        for nonlin_ind in range(max_iter):
            spilu = sp_la.spilu(M_BDF2, fill_factor=300, drop_tol=1e-6)
            M_x = lambda x: spilu.solve(x)
            precond = sp_la.LinearOperator((2*ndofs_u+ndofs_p+1, 2*ndofs_u+ndofs_p+1), M_x)
            sol = sp_la.bicgstab(M_BDF2, rhs_BDF2, M=precond, tol=TOL)[0]
            ux_n1 = np.reshape(sol[0:ndofs_u], (ndofs_u, 1))
            uy_n1 = np.reshape(sol[ndofs_u:2*ndofs_u], (ndofs_u, 1))
            M_BDF2 = assemble_blockwise_matrix_BDF2(dt, ux_n1, uy_n1)
            res = l2_norm(big_mass_matrix, M_BDF2.dot(sol) - rhs_BDF2)
            print('BDF2, res = ' + str(res))
            if res < TOL:
                # store the maximum number of nonlinear iterations
                nonlin_conv_ind[1,t_ind] = np.maximum(nonlin_ind+1, nonlin_conv_ind[1,t_ind])
                break
            if(nonlin_ind == max_iter-1):
                # nonlinear iterator did not converge
                nonlin_conv_ind[1,t_ind] = -1
        u_BDF2_old = u_BDF2
        u_BDF2 = np.reshape(sol, (2*ndofs_u + ndofs_p + 1, 1))
        gc.collect()

        ### CN
        ux_n1 = np.reshape(u_CN[0:ndofs_u], (ndofs_u, 1))
        uy_n1 = np.reshape(u_CN[ndofs_u:2*ndofs_u], (ndofs_u, 1))
        ux_n = ux_n1
        uy_n = uy_n1
        S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
        T11 = S11
        rhs_CN = assemble_blockwise_force_CN(k*dt, dt, S11, T11, u_CN)
        M_CN = assemble_blockwise_matrix_CN(dt, S11, T11)
        for nonlin_ind in range(max_iter):
            spilu = sp_la.spilu(M_CN, fill_factor=300, drop_tol=1e-6)
            M_x = lambda x: spilu.solve(x)
            precond = sp_la.LinearOperator((2*ndofs_u+ndofs_p+1, 2*ndofs_u+ndofs_p+1), M_x)
            sol = sp_la.bicgstab(M_CN, rhs_CN, M=precond, tol=TOL)[0]
            ux_n1 = np.reshape(sol[0:ndofs_u], (ndofs_u, 1))
            uy_n1 = np.reshape(sol[ndofs_u:2*ndofs_u], (ndofs_u, 1))
            S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
            M_CN = assemble_blockwise_matrix_CN(dt, S11, T11)
            rhs_CN = assemble_blockwise_force_CN(k*dt, dt, S11, T11, u_CN)
            res = l2_norm(big_mass_matrix, M_CN.dot(sol) - rhs_CN)
            print('CN, res = ' + str(res))
            if res < TOL:
                # store the maximum number of nonlinear iterations
                nonlin_conv_ind[2,t_ind] = np.maximum(nonlin_ind+1, nonlin_conv_ind[2,t_ind])
                break
            if(nonlin_ind == max_iter-1):
                # nonlinear iterator did not converge
                nonlin_conv_ind[2,t_ind] = -1
        u_CN = np.reshape(sol, (2*ndofs_u + ndofs_p + 1, 1))
        gc.collect()

        ### TR
        ux_n1 = np.reshape(u_TR[0:ndofs_u], (ndofs_u, 1))
        uy_n1 = np.reshape(u_TR[ndofs_u:2*ndofs_u], (ndofs_u, 1))
        ux_n = ux_n1
        uy_n = uy_n1
        S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
        T11 = S11
        rhs_TR = assemble_blockwise_force_TR(k*dt, dt, S11, T11, u_TR)
        M_TR = assemble_blockwise_matrix_TR(dt, S11, T11)
        for nonlin_ind in range(max_iter):
            spilu = sp_la.spilu(M_TR, fill_factor=300, drop_tol=1e-6)
            M_x = lambda x: spilu.solve(x)
            precond = sp_la.LinearOperator((2*ndofs_u+ndofs_p+1, 2*ndofs_u+ndofs_p+1), M_x)
            sol = sp_la.bicgstab(M_TR, rhs_TR, M=precond, tol=TOL)[0]
            ux_n1 = np.reshape(sol[0:ndofs_u], (ndofs_u, 1))
            uy_n1 = np.reshape(sol[ndofs_u:2*ndofs_u], (ndofs_u, 1))
            S11 = assemble.u_gradv_w_p1(topo_u, x_u, y_u, ux_n1, uy_n1)
            M_TR = assemble_blockwise_matrix_TR(dt, S11, T11)
            res = l2_norm(big_mass_matrix, M_TR.dot(sol) - rhs_TR)
            print('TR, res = ' + str(res))
            if res < TOL:
                # store the maximum number of nonlinear iterations
                nonlin_conv_ind[3,t_ind] = np.maximum(nonlin_ind+1, nonlin_conv_ind[2,t_ind])
                break
            if(nonlin_ind == max_iter-1):
                # nonlinear iterator did not converge
                nonlin_conv_ind[3,t_ind] = -1
        u_TR = np.reshape(sol, (2*ndofs_u + ndofs_p + 1, 1))
        gc.collect()

        ### End of time loop

    ###Compute a lot of errors
    BDF1[:,t_ind] = u_BDF1[0:2*ndofs_u].ravel()
    BDF2[:,t_ind] = u_BDF2[0:2*ndofs_u].ravel()
    CN[:,t_ind] = u_CN[0:2*ndofs_u].ravel()
    TR[:,t_ind] = u_TR[0:2*ndofs_u].ravel()
    f_x = lambda x, y: analytical_u(T, x, y)[0:len(x)]
    f_y = lambda x, y: analytical_u(T, x, y)[len(x):2*len(x)]
    zero_fun = lambda x, y: np.zeros(x.shape)
    e_x = quadrature.l2error_on_mesh(u_BDF1[0:ndofs_u], f_x, x_u, y_u, topo_u, 6)
    e_y = quadrature.l2error_on_mesh(u_BDF1[ndofs_u:2*ndofs_u], f_y, x_u, y_u, topo_u, 6)
    err_BDF1[t_ind] = np.sqrt(e_x**2 + e_y**2)
    # e_x = quadrature.l2error_on_mesh(u_BDF1[0:ndofs_u] - ref[0:ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # e_y = quadrature.l2error_on_mesh(u_BDF1[ndofs_u:2*ndofs_u] - ref[ndofs_u:2*ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # err_BDF1_ref[t_ind] = np.sqrt(e_x**2 + e_y**2)
    e_x = quadrature.l2error_on_mesh(u_BDF2[0:ndofs_u], f_x, x_u, y_u, topo_u, 6)
    e_y = quadrature.l2error_on_mesh(u_BDF2[ndofs_u:2*ndofs_u], f_y, x_u, y_u, topo_u, 6)
    err_BDF2[t_ind] = np.sqrt(e_x**2 + e_y**2)
    # e_x = quadrature.l2error_on_mesh(u_BDF2[0:ndofs_u] - ref[0:ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # e_y = quadrature.l2error_on_mesh(u_BDF2[ndofs_u:2*ndofs_u] - ref[ndofs_u:2*ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # err_BDF2_ref[t_ind] = np.sqrt(e_x**2 + e_y**2)
    e_x = quadrature.l2error_on_mesh(u_CN[0:ndofs_u], f_x, x_u, y_u, topo_u, 6)
    e_y = quadrature.l2error_on_mesh(u_CN[ndofs_u:2*ndofs_u], f_y, x_u, y_u, topo_u, 6)
    err_CN[t_ind] = np.sqrt(e_x**2 + e_y**2)
    # e_x = quadrature.l2error_on_mesh(u_CN[0:ndofs_u] - ref[0:ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # e_y = quadrature.l2error_on_mesh(u_CN[ndofs_u:2*ndofs_u] - ref[ndofs_u:2*ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # err_CN_ref[t_ind] = np.sqrt(e_x**2 + e_y**2)
    e_x = quadrature.l2error_on_mesh(u_TR[0:ndofs_u], f_x, x_u, y_u, topo_u, 6)
    e_y = quadrature.l2error_on_mesh(u_TR[ndofs_u:2*ndofs_u], f_y, x_u, y_u, topo_u, 6)
    err_TR[t_ind] = np.sqrt(e_x**2 + e_y**2)
    # e_x = quadrature.l2error_on_mesh(u_TR[0:ndofs_u] - ref[0:ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # e_y = quadrature.l2error_on_mesh(u_TR[ndofs_u:2*ndofs_u] - ref[ndofs_u:2*ndofs_u], zero_fun, x_u, y_u, topo_u, 6)
    # err_TR_ref[t_ind] = np.sqrt(e_x**2 + e_y**2)

    ### End of loop over timesteps


f_x = lambda x, y: analytical_u(T, x, y)[0:len(x)]
f_y = lambda x, y: analytical_u(T, x, y)[len(x):2*len(x)]
norm_u_x = quadrature.l2error_on_mesh(np.zeros(u_BDF1.shape), f_x, x_u, y_u, topo_u, 6)
norm_u_y = quadrature.l2error_on_mesh(np.zeros(u_BDF1.shape), f_y, x_u, y_u, topo_u, 6)
norm_u = np.sqrt(norm_u_x**2  + norm_u_y**2)

print()
print('------')
print('dx = ' + str(dx))
print('dt = ' + str(0.5*T*np.power(2., -np.arange(0,n_runs))))
print('dt_ref = ' + str(dt_ref))
print('------')

print('error comparted to analytical solution')
print('abs. error BDF1: ' + str(err_BDF1))
print('abs. error BDF2: ' + str(err_BDF2))
print('abs. error CN:   ' + str(err_CN))
print('abs. error TR:   ' + str(err_TR))
print('rel. error BDF1: ' + str(np.divide(err_BDF1, norm_u)))
print('rel. error BDF2: ' + str(np.divide(err_BDF2, norm_u)))
print('rel. error CN:   ' + str(np.divide(err_CN, norm_u)))
print('rel. error TR:   ' + str(np.divide(err_TR, norm_u)))
print('Error decay BDF1: ' + str(np.divide(err_BDF1[0:n_runs-1], err_BDF1[1:n_runs])))
print('Error decay BDF2: ' + str(np.divide(err_BDF2[0:n_runs-1], err_BDF2[1:n_runs])))
print('Error decay CN:   ' + str(np.divide(err_CN[0:n_runs-1], err_CN[1:n_runs])))
print('Error decay TR:   ' + str(np.divide(err_TR[0:n_runs-1], err_TR[1:n_runs])))

print('')

print('error compared to reference solution')
print('abs. error BDF1: ' + str(err_BDF1_ref))
print('abs. error BDF2: ' + str(err_BDF2_ref))
print('abs. error CN:   ' + str(err_CN_ref))
print('abs. error TR:   ' + str(err_TR_ref))
print('rel. error BDF1: ' + str(np.divide(err_BDF1_ref, norm_u)))
print('rel. error BDF2: ' + str(np.divide(err_BDF2_ref, norm_u)))
print('rel. error CN:   ' + str(np.divide(err_CN_ref, norm_u)))
print('rel. error TR: ' + str(np.divide(err_TR_ref, norm_u)))
print('Error decay BDF1: ' + str(np.divide(err_BDF1_ref[0:n_runs-1], err_BDF1_ref[1:n_runs])))
print('Error decay BDF2: ' + str(np.divide(err_BDF2_ref[0:n_runs-1], err_BDF2_ref[1:n_runs])))
print('Error decay CN:   ' + str(np.divide(err_CN_ref[0:n_runs-1], err_CN_ref[1:n_runs])))
print('Error decay TR:   ' + str(np.divide(err_TR_ref[0:n_runs-1], err_TR_ref[1:n_runs])))

print('')

rate_u_BDF1 = np.zeros(n_runs-2)
rate_u_BDF2 = np.zeros(n_runs-2)
rate_u_CN = np.zeros(n_runs-2)
rate_u_TR = np.zeros(n_runs-2)
for k in range(0,n_runs-2):
    rate_u_BDF1[k] = np.log2(l2_norm(M_2D, BDF1[:,k] - BDF1[:,k+1]) / l2_norm(M_2D, BDF1[:,k+1] - BDF1[:,k+2]))
    rate_u_BDF2[k] = np.log2(l2_norm(M_2D, BDF2[:,k] - BDF2[:,k+1]) / l2_norm(M_2D, BDF2[:,k+1] - BDF2[:,k+2]))
    rate_u_CN[k] = np.log2(l2_norm(M_2D, CN[:,k] - CN[:,k+1]) / l2_norm(M_2D, CN[:,k+1] - CN[:,k+2]))
    rate_u_TR[k] = np.log2(l2_norm(M_2D, TR[:,k] - TR[:,k+1]) / l2_norm(M_2D, TR[:,k+1] - TR[:,k+2]))
print('Empirical rate BDF1: ' + str(rate_u_BDF1))
print('Empirical rate BDF2: ' + str(rate_u_BDF2))
print('Empirical rate CN:   ' + str(rate_u_CN))
print('Empirical rate TR:   ' + str(rate_u_TR))

print('')

print('Max iterations of the fixpoint iterations:')
print(nonlin_conv_ind)

filename = 'dx='+str(dx)
f = open(filename,"wb")
np.save(f,dx)
np.save(f,0.5*T*np.power(2., -np.arange(0,n_runs)))
np.save(f,dt_ref)
np.save(f,BDF1)
np.save(f,BDF2)
np.save(f,CN)
np.save(f,ref)
f.close()
