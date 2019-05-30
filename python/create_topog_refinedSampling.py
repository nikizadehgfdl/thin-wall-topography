#!/usr/bin/env python

import sys, getopt
import datetime, os, subprocess
import GMesh
import imp
import netCDF4
import numpy as np

def break_array_to_blocks(a,xb=4,yb=1):
    a_win = []
    if(xb == 4 and yb ==1):
        i1 = a.shape[1]//xb
        i2 = 2*i1
        i3 = 3*i1
        i4 = a.shape[1]
        
        j1 = a.shape[0]//yb
        a_win.append(a[0:j1,0:i1])
        a_win.append(a[0:j1,i1:i2])
        a_win.append(a[0:j1,i2:i3])
        a_win.append(a[0:j1,i3:i4])
        return a_win
    else:    
        raise Exception('This rotuine can only make 2x2 blocks!')
        ##Niki: Implement a better algo and lift this restriction

def undo_break_array_to_blocks(a,xb=4,yb=1):    
    if(xb == 4 and yb ==1):        
        ao = np.append(a[0],a[1],axis=1)
        ao = np.append(ao,a[2],axis=1)
        ao = np.append(ao,a[3],axis=1)
        return ao
    else:    
        raise Exception('This rotuine can only make 2x2 blocks!')
        ##Niki: Implement a better algo and lift this restriction

def write_topog(h,hstd,hmin,hmax,xx,yy,fnam=None,format='NETCDF3_CLASSIC',description=None,history=None,source=None,no_changing_meta=None):
    import netCDF4 as nc

    if fnam is None:
      fnam='topog.nc'
    fout=nc.Dataset(fnam,'w',format=format)

    ny=h.shape[0]; nx=h.shape[1]
    print ('Writing netcdf file with ny,nx= ',ny,nx)

    ny=fout.createDimension('ny',ny)
    nx=fout.createDimension('nx',nx)
    string=fout.createDimension('string',255)    
    tile=fout.createVariable('tile','S1',('string'))
    height=fout.createVariable('height','f8',('ny','nx'))
    height.units='meters'
    height[:]=h
    h_std=fout.createVariable('h_std','f8',('ny','nx'))
    h_std.units='meters'
    h_std[:]=hstd
    h_min=fout.createVariable('h_min','f8',('ny','nx'))
    h_min.units='meters'
    h_min[:]=hmin
    h_max=fout.createVariable('h_max','f8',('ny','nx'))
    h_max.units='meters'
    h_max[:]=hmax
    x=fout.createVariable('x','f8',('ny','nx'))
    x.units='meters'
    x[:]=xx
    y=fout.createVariable('y','f8',('ny','nx'))
    y.units='meters'
    y[:]=yy
    #global attributes
    if(not no_changing_meta):
    	fout.history = history
    	fout.description = description
    	fout.source =  source

    fout.sync()
    fout.close()

def plot():
    pl.clf()
    display.clear_output(wait=True)
    plt.figure(figsize=(10,10))
    lonc = (lon[0,0]+lon[0,-1])/2
    latc = 90
    ax = plt.subplot(111, projection=cartopy.crs.NearsidePerspective(central_longitude=lonc, central_latitude=latc))
    ax.set_global()
    ax.stock_img()
    ax.coastlines()
    ax.gridlines()
    target_mesh.plot(ax,subsample=100, transform=cartopy.crs.Geodetic())
    plt.show(block=False)
    plt.pause(1)
    display.display(pl.gcf())

def do_block(part,lon,lat,topo_lons,topo_lats,topo_elvs):
    print("  Doing block number ",part)
    print("  Target sub mesh shape: ",lon.shape)

    target_mesh = GMesh.GMesh( lon=lon, lat=lat )

    #plot()

    # Indices in topographic data
    ti,tj = target_mesh.find_nn_uniform_source( topo_lons, topo_lats )

    #Sample every other source points 
    ##Niki: This is only for efficeincy and we want to remove the constraint for the final product.
    ##Niki: But in some cases it may not work!
    tis,tjs = slice(ti.min(), ti.max()+1,2), slice(tj.min(), tj.max()+1,2)
    print('  Slices j,i:', tjs, tis )

    # Read elevation data
    topo_elv = topo_elvs[tjs,tis]
    # Extract appropriate coordinates
    topo_lon = topo_lons[tis]
    topo_lat = topo_lats[tjs]

    print('  Topo shape:', topo_elv.shape)
    print('  topography longitude range:',topo_lon.min(),topo_lon.max())
    print('  topography latitude  range:',topo_lat.min(),topo_lat.max())

    print("  Target     longitude range:", lon.min(),lon.max())
    print("  Target     latitude  range:", lat.min(),lat.max())

    # Refine grid by 2 till all source points are hit 
    print("  Refining the target to hit all source points ...")
    Glist = target_mesh.refine_loop( topo_lon, topo_lat , max_mb=8000);
    hits = Glist[-1].source_hits( topo_lon, topo_lat )
    print("  non-hit ratio: ",hits.size-hits.sum().astype(int)," / ",hits.size)

    # Sample the topography on the refined grid
    print("  Sampling the source points on target mesh ...")
    Glist[-1].sample_source_data_on_target_mesh(topo_lon,topo_lat,topo_elv)
    print("  Sampling finished...")

    # Coarsen back to the original taget grid
    print("  Coarsening back to the original taget grid ...")
    for i in reversed(range(1,len(Glist))):   # 1, makes it stop at element 1 rather than 0
        Glist[i].coarsenby2(Glist[i-1])

    print("")
    #print("Writing ...")
    #filename = 'topog_refsamp_BP.nc'+str(b) 
    #write_topog(Glist[0].height,fnam=filename,no_changing_meta=True)
    #print("haigts shape:", lons[b].shape,Hlist[b].shape)
    return Glist[0].height,Glist[0].h_std,Glist[0].h_min,Glist[0].h_max


def usage(scriptbasename):
    print(scriptbasename + ' --hgridfilename <input_hgrid_filepath> --outputfilename <output_topog_filepath>  [--plot --no_changing_meta]')


def main(argv):
    import socket
    host = str(socket.gethostname())
    scriptpath = sys.argv[0]
    scriptbasename = subprocess.check_output("basename "+ scriptpath,shell=True).decode('ascii').rstrip("\n")
    scriptdirname = subprocess.check_output("dirname "+ scriptpath,shell=True).decode('ascii').rstrip("\n")

    plotem = False
    no_changing_meta = False
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hi:o:",["hgridfilename=","outputfilename=","no_changing_meta"])
    except getopt.GetoptError as err:
        print(err)
        usage(scriptbasename)
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt in ("-i", "--hgridfilename"):
            gridfilename = arg
        elif opt in ("-o", "--outputfilename"):
            outputfilename = arg
        elif opt in ("--plot"):
            plotem = True
        elif opt in ("--no_changing_meta"):
            no_changing_meta = True
        else:
            assert False, "unhandled option"


    print("")
    print("Generatin model topography for target grid ", gridfilename)
    #Information to write in file as metadata
    scriptgithash = subprocess.check_output("cd "+scriptdirname +";git rev-parse HEAD; exit 0",stderr=subprocess.STDOUT,shell=True).decode('ascii').rstrip("\n")
    scriptgitMod  = subprocess.check_output("cd "+scriptdirname +";git status --porcelain "+scriptbasename+" | awk '{print $1}' ; exit 0",stderr=subprocess.STDOUT,shell=True).decode('ascii').rstrip("\n")
    if("M" in str(scriptgitMod)):
        scriptgitMod = " , But was localy Modified!"

    hist = "This file was generated via command " + ' '.join(sys.argv)
    if(not no_changing_meta):
        hist = hist + " on "+ str(datetime.date.today()) + " on platform "+ host

    desc = "This is a model topography file generated by the refine-sampling method from source topography. "
    
    source =""
    if(not no_changing_meta):
        source =  source + scriptpath + " had git hash " + scriptgithash + scriptgitMod 
        source =  source + ". To obtain the grid generating code do: git clone  https://github.com/nikizadehgfdl/thin-wall-topography.git ; cd thin-wall-topography;  git checkout "+scriptgithash

    

    # # Open and read the topographic dataset
    # Open a topography dataset, check that the topography is on a uniform grid.
    # URL of topographic data, names of longitude, latitude and elevation variables
    url,vx,vy,ve = '/net2/nnz/thin-wall-topography/python/workdir/GEBCO_2014_2D.nc','lon','lat','elevation'
    # url,vx,vy,ve = 'http://thredds.socib.es/thredds/dodsC/ancillary_data/bathymetry/MED_GEBCO_30sec.nc','lon','lat','elevation'
    # url,vx,vy,ve = 'http://iridl.ldeo.columbia.edu/SOURCES/.NOAA/.NGDC/.ETOPO1/.z_bedrock/dods','lon','lat','z_bedrock'
    topo_data = netCDF4.Dataset(url)

    # Read coordinates of topography
    topo_lons = np.array( topo_data.variables[vx][:] )
    topo_lats = np.array( topo_data.variables[vy][:] )
    topo_elvs = np.array( topo_data.variables[ve][:,:] )

    #Translate topo data to start at target_mesh.lon[0]
    topo_lons = np.roll(topo_lons,14400,axis=0) #Roll GEBCO longitude to right. 14400 was a lucky guess that checked out!
    topo_lons = np.where(topo_lons>60 , topo_lons-360, topo_lons) #Rename (0,60) as (-300,-180) 
    topo_elvs = np.roll(topo_elvs,14400,axis=1) #Roll GEBCO depth to the right by the same amount.

    print(' topography grid array shapes: ' , topo_lons.shape,topo_lats.shape)
    print(' topography longitude range:',topo_lons.min(),topo_lons.max())
    print(' topography latitude range:',topo_lats.min(),topo_lats.max())
    print(' Is mesh uniform?', GMesh.is_mesh_uniform( topo_lons, topo_lats ) )

    #Read a target grid
    # ## Read in Bipolar Northern cap grid for 1/8 degree model
#    targ_grid =  netCDF4.Dataset('/net2/nnz/grid_generation/workdir/grid_OM4p125_new/tripolar_disp_res8.ncBP.nc')
    targ_grid =  netCDF4.Dataset(gridfilename)
    targ_lon = np.array(targ_grid.variables['x'])
    targ_lat = np.array(targ_grid.variables['y'])
    #x and y have shape (nyp,nxp). Topog does not need the last col for global grids (period in x). 
    targ_lon = targ_lon[:,:-1]
    targ_lat = targ_lat[:,:-1]
    print(" Target mesh shape: ",targ_lon.shape)
    # ## Partition the Target grid into non-intersecting blocks
    #This works only if the target mesh is "regular"! Niki: Find the mathematical buzzword for "regular"!!
    #Is this a regular mesh?
    # if( .NOT. is_mesh_regular() ) throw

    #Niki: Why 4,1 partition?
    xb=4
    yb=1
    lons=break_array_to_blocks(targ_lon,xb,yb)
    lats=break_array_to_blocks(targ_lat,xb,yb)

    #We must loop over the 4 partitions
    Hlist=[]
    Hstdlist=[]
    Hminlist=[]
    Hmaxlist=[]
    for part in range(0,xb):
        lon = lons[part]
        lat = lats[part]
        h,hstd,hmin,hmax = do_block(part,lon,lat,topo_lons,topo_lats,topo_elvs)
        Hlist.append(h)
        Hstdlist.append(hstd)
        Hminlist.append(hmin)
        Hmaxlist.append(hmax)

    print(" Merging the blocks ...")
    height_refsamp = undo_break_array_to_blocks(Hlist,xb,yb)
    hstd_refsamp = undo_break_array_to_blocks(Hstdlist,xb,yb)
    hmin_refsamp = undo_break_array_to_blocks(Hminlist,xb,yb)
    hmax_refsamp = undo_break_array_to_blocks(Hmaxlist,xb,yb)
    write_topog(height_refsamp,hstd_refsamp,hmin_refsamp,hmax_refsamp,targ_lon,targ_lat,fnam=outputfilename,description=desc,history=hist,source=source,no_changing_meta=no_changing_meta)

    #Niki: Why isn't h periodic in x?  I.e., height_refsamp[:,0] != height_refsamp[:,-1]
    print(" Periodicity test  : ", height_refsamp[0,0] , height_refsamp[0,-1])
    print(" Periodicity break : ", (np.abs(height_refsamp[:,0]- height_refsamp[:,-1])).max() )

    if(plotem):
        import matplotlib.pyplot as plt
        import pylab as pl
        from IPython import display
        import cartopy

        plt.figure(figsize=(10,10))
        ax = plt.subplot(111, projection=cartopy.crs.NearsidePerspective(central_latitude=90))
        ax.set_global()
        ax.stock_img()
        ax.coastlines()
        ax.gridlines()
        im = ax.pcolormesh(targ_lon,targ_lat,height_refsamp, transform=cartopy.crs.PlateCarree())
        plt.colorbar(im,ax=ax);


if __name__ == "__main__":
    main(sys.argv[1:])



#B ny,nx=  118 720 , st ny,nx=  119 721
#M ny,nx=  350 720 , st ny,nx=  351 721
#S ny,nx=   56 720 , st ny,nx=   57 721

#T ny,nx=  524 720