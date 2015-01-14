"""The Laplacian, the finite elements playground. 

.. moduleauthor:: Nicola Cavallini

"""

import numpy as np
import scipy.sparse.linalg as sp_la
import matplotlib.pyplot as pl

import lin_tri_mesh as lin_t3
import basis_func as shp
import assemble
import la_utils
import viewers

if __name__== '__main__':

    nx = 32
    delta_x = 1./nx
    ny = nx
    delta_y = 1./ny
    (topo,x,y) = lin_t3.grid_t3(nx,ny,delta_x,delta_y)
    
    ndofs = (nx+1)*(ny+1)
    
    A = assemble.gradu_gradv_p1(topo,x,y)
    
    rhs = np.zeros((ndofs,1))
    
    x_l = x[topo[0]]
    y_l = y[topo[0]]
    eval_points = np.zeros((0,2))
    (phi_dx,phi_dy,phi,omega) = shp.tri_p1(x_l,y_l,eval_points)
    
    for row in topo:
        local_rhs = 1./3. * np.ones((3,1)) * omega
        rhs[row] = rhs[row] + local_rhs
    
    bc_id = np.where( y < delta_x/10)
    A = la_utils.set_diag(A,bc_id)
    rhs[bc_id] = 0
    
    bc_id = np.where( y > 1-delta_x/10)
    A = la_utils.set_diag(A,bc_id)
    rhs[bc_id] = 0
    
    bc_id = np.where( x > 1-delta_x/10)
    A = la_utils.set_diag(A,bc_id)
    rhs[bc_id] = 0
    
    bc_id = np.where( x < delta_x/10)
    A = la_utils.set_diag(A,bc_id)
    rhs[bc_id] = 0
        
    pl.spy(A)
    pl.show        
    
    sol = sp_la.spsolve(A,rhs)
    
    viewers.plot_sol_p1(x,y,sol,topo)