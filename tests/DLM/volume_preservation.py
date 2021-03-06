#! /usr/bin/env python

import math
import matplotlib.pyplot as plt
import numpy as np
import os
from scipy import sparse
from shapely.geometry import Polygon
import sys
sys.path.append('/usr/local/lib64/python3.7/site-packages/vtkmodules')
import vtk

sys.path.append('../../modules')
import assemble

def read_area(k):
    reader = vtk.vtkXMLUnstructuredGridReader()
    filename = '../../../ans-ifem/ans-ifem/out/Cavity-solid-'+str(k).zfill(5)+'.vtu'
    if not os.path.exists(filename):
        return 0.2**2*np.pi
    reader.SetFileName(filename)
    reader.Update() # Needed because of GetScalarRange

    unstrGrid = reader.GetOutput()

    numcells = unstrGrid.GetNumberOfCells()
    area = 0
    for j in range(numcells):
        p_0 = (unstrGrid.GetCell(j).GetPoints().GetPoint(0)[0], unstrGrid.GetCell(j).GetPoints().GetPoint(0)[1])
        p_1 = (unstrGrid.GetCell(j).GetPoints().GetPoint(1)[0], unstrGrid.GetCell(j).GetPoints().GetPoint(1)[1])
        p_2 = (unstrGrid.GetCell(j).GetPoints().GetPoint(2)[0], unstrGrid.GetCell(j).GetPoints().GetPoint(2)[1])
        p_3 = (unstrGrid.GetCell(j).GetPoints().GetPoint(3)[0], unstrGrid.GetCell(j).GetPoints().GetPoint(3)[1])


        poly = Polygon([p_0, p_1, p_2, p_3])
        area += poly.area
    return area


def eval_str_area(k):
    input_name = results_dir+'cn_time_'+str(k).zfill(3)
    f = open(input_name,"rb")
    u = np.load(f)
    p = np.load(f)
    x_s = np.load(f)
    y_s = np.load(f)
    f.close()
    area_BDF1 = 0
    for row in topo_s:
        eval_p = np.zeros((3,2))
        eval_p[:,0] = x_s[row]
        eval_p[:,1] = y_s[row]
        poly = Polygon(tuple(eval_p.tolist()))
        area_BDF1+= poly.area

    input_name = input_name.replace('BDF1', 'BDF2')
    f = open(input_name,"rb")
    u = np.load(f)
    p = np.load(f)
    x_s = np.load(f)
    y_s = np.load(f)
    f.close()
    area_BDF2 = 0
    for row in topo_s:
        eval_p = np.zeros((3,2))
        eval_p[:,0] = x_s[row]
        eval_p[:,1] = y_s[row]
        poly = Polygon(tuple(eval_p.tolist()))
        area_BDF2 += poly.area

    input_name = input_name.replace('BDF2', 'Theta')
    f = open(input_name,"rb")
    u = np.load(f)
    p = np.load(f)
    x_s = np.load(f)
    y_s = np.load(f)
    f.close()
    area_Theta = 0
    for row in topo_s:
        eval_p = np.zeros((3,2))
        eval_p[:,0] = x_s[row]
        eval_p[:,1] = y_s[row]
        poly = Polygon(tuple(eval_p.tolist()))
        area_Theta += poly.area
    return area_BDF1, area_BDF2, area_Theta

def l2_norm(M,g):
    l2_g = M.dot(g)
    l2_g = np.dot(l2_g.transpose(),g)
    l2_g = math.sqrt(l2_g)
    return l2_g

if len(sys.argv) > 2:
    results_dir = sys.argv[1]
    n = int(sys.argv[2])
else:
    n = 800

filename = results_dir+'mesh'
f = open(filename,"rb")
topo_p = np.load(f)
x_p = np.load(f)
y_p = np.load(f)
topo_u = np.load(f)
x_u = np.load(f)
y_u = np.load(f)
c2f = np.load(f)
topo_s = np.load(f)
x_s = np.load(f)
y_s = np.load(f)
s_lgr = np.load(f)
t_lgr = np.load(f)
f.close()

e_f = []
d_f = []
for row in topo_p:
    x_l = x_p[row[0:3]]
    y_l = y_p[row[0:3]]
    eval_p = np.zeros((3,2))
    eval_p[:,0] = x_l
    eval_p[:,1] = y_l
    poly = Polygon(tuple(eval_p.tolist()))
    a = poly.area
    l = np.sqrt((x_l-np.roll(x_l,1))**2 + (y_l - np.roll(y_l,1))**2)
    e_f.append(np.max(l))
    d_f.append(0.25*np.prod(l)/a)
print('maximum fluid edge' + str(np.max(e_f)))
print('maximum fluid diam' + str(np.max(d_f)))

e_s = []
d_s = []
for row in topo_s:
    x_l = s_lgr[row]
    y_l = t_lgr[row]
    eval_p = np.zeros((3,2))
    eval_p[:,0] = x_l
    eval_p[:,1] = y_l
    poly = Polygon(tuple(eval_p.tolist()))
    a = poly.area
    l = np.sqrt((x_l-np.roll(x_l,1))**2 + (y_l - np.roll(y_l,1))**2)
    e_s.append(np.max(l))
    d_s.append(0.25*np.prod(l)/a)
print('maximum solid edge' + str(np.max(e_s)))
print('maximum solid diam' + str(np.max(d_s)))





# ie_s = np.arange(0,s_lgr.shape[0])
# KS11 = assemble.gradu_gradv_p1_ieq(topo_s,s_lgr,t_lgr,ie_s)
# MF11 = assemble.u_v_p1(topo_u,x_u,y_u)
# KS = sparse.vstack([
#     sparse.hstack([KS11, sparse.csr_matrix(KS11.shape)]),
#     sparse.hstack([sparse.csr_matrix(KS11.shape), KS11])
# ])
# MF = sparse.vstack([
#     sparse.hstack([MF11, sparse.csr_matrix(MF11.shape)]),
#     sparse.hstack([sparse.csr_matrix(MF11.shape), MF11])
# ])



diffusion = np.zeros((4, n))
energy = np.zeros((n))

str_area_zero = eval_str_area(0)
print(str_area_zero)
print(0.2**2*np.pi)
deal_area_zero = read_area(0)
print(deal_area_zero)
# dx_n = sx_n - s_lgr
# dy_n = sy_n - t_lgr
#energy[0] =(l2_norm(KS,np.append(dx_n, dy_n)))**2 + (l2_norm(MF,u))**2
for cn_time in range(1, n):
    str_area = eval_str_area(cn_time)
    diffusion[0:3, cn_time] = (np.divide(str_area,str_area_zero)-1.)*100
    deal_area = read_area(cn_time)
    diffusion[3, cn_time] = (deal_area/deal_area_zero - 1.)*100
    # dx_n = sx_n - s_lgr
    # dy_n = sy_n - t_lgr
    #energy[cn_time] =(l2_norm(KS,np.append(dx_n, dy_n)))**2 + (l2_norm(MF,u))**2
    print(diffusion[:,cn_time])
plt.plot(np.arange(0,n)*4./n, diffusion[0,:], label='BE')
plt.plot(np.arange(0,n)*4./n, diffusion[1,:], label='BDF2')
plt.plot(np.arange(0,n)*4./n, diffusion[2,:], label='Theta')
plt.xlabel('time (s)')
plt.ylabel('volume change (%)')
plt.title('Volume preservation for the disk example (DLM), coarse time step')
plt.grid(True)
plt.legend()
plt.show()

plt.plot(np.arange(0,n)*0.01    , diffusion[3,:])
plt.xlabel('time (s)')
plt.ylabel('volume change (%)')
plt.title('Volume preservation for the disk example (Deal.II)')
plt.grid(True)
plt.show()

# plt.plot(np.arange(0,n), energy)
# plt.xlabel('time (s)')
# plt.ylabel('energy')
# plt.title('Energy preservation for the disk example (BDF1)')
# plt.grid(True)
# plt.show()
