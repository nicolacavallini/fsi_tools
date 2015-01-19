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
import esatta
import errore2D

if __name__== '__main__':
<<<<<<< HEAD
    n = [4,8,16]
=======
    n = [16,32,64,128]
>>>>>>> 57ef4f185de312fb6004bbf61dee9852688eaf3c
    i=0
    err_l2 = np.zeros((len (n),1))
    for nx in n:
        delta_x = 1./nx
        ny = nx
        delta_y = 1./ny
        (topo,x,y) = lin_t3.grid_t3(nx,ny,delta_x,delta_y)
        ndofs = (nx+1)*(ny+1)
        
        A = assemble.gradu_gradv_p1(topo,x,y)
        
        rhs = np.zeros((ndofs,1))
        
        for row in topo:
            a=x[row]
            b=y[row]
            surf_e = 1./2. * abs( a[0]*b[2] - a[0]*b[1] + a[1]*b[0] - a[1]*b[2] + a[2]*b[1] - a[2]*b[0] )
<<<<<<< HEAD
            tmpload = esatta.load(a,b)
            tmpload = np.reshape ( tmpload, rhs[row].shape)
            local_rhs = 1./3. * tmpload * surf_e
=======
            local_rhs = 1./3. * np.ones((3,1)) * surf_e
>>>>>>> 57ef4f185de312fb6004bbf61dee9852688eaf3c
            rhs[row] = rhs[row] + local_rhs        
#        eval_points = np.zeros((0,2))
#        (phi_dx,phi_dy,phi,omega) = shp.tri_p1(x_l,y_l,eval_points)
         
#        for row in topo:
#			local_rhs = 2./3. * (y[row]*(1-y[row])+x[row]*(1-x[row])) * omega
#			local_rhs = np.reshape(local_rhs,rhs[row].shape)
#			rhs[row] = rhs[row] + local_rhs
#            
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
        
        sol = sp_la.spsolve(A,rhs)
        
        ( err_l2 , er_derx , er_dery ) = errore2D.err_l2(topo,x,y,sol)
#        err=0.
#        for row in topo:    
#            sol_esatta = esatta.sol_esatta(x[row],y[row])
#            local_err_l2 = np.sum(1./3 * ((sol[row]-sol_esatta)**2) * omega)
#            err= err + local_err_l2
#        err_l2 [i] = np.sqrt(err)     
#        i=i+1
        
        #viewers.plot_sol_p1(x,y,sol,topo)
<<<<<<< HEAD
        #print  sol
        #print esatta.sol_esatta(x,y)
        tmpesatta= esatta.sol_esatta(x,y)
        tmpesatta = np.reshape ( tmpesatta, (1,x.shape[0]))
        norma = np.sum((sol-tmpesatta)**2)
        normaes=np.sum(tmpesatta**2)
        norma=np.sqrt(norma)/np.sqrt(normaes)
        print norma
        
=======
>>>>>>> 57ef4f185de312fb6004bbf61dee9852688eaf3c

        print err_l2 , er_derx , er_dery