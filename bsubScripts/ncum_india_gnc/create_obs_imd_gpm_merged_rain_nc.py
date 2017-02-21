import os, datetime, subprocess, cdms2, numpy, cdtime

cdms2.setNetcdfShuffleFlag(0) ## where value is either 0 or 1
cdms2.setNetcdfDeflateFlag(0) ## where value is either 0 or 1
cdms2.setNetcdfDeflateLevelFlag(0)
cdms2.setNetcdf4Flag(1)

"""
This script will create observed IMD+GPM merged rainfall grads_nc file using 
grads for the purpose of read-in ArcGIS post subdivision.

Written By : Arulalan.T
Date : 21-02-2017

"""

grads = '/gpfs1/home/Libs/GNU/GRADS/grads-2.1.a2/bin/grads'

outpath = '/gpfs3/home/umfcst/ShortJobs/IndGNC/'
checkpastdays = 30

if os.environ.has_key('UMRIDER_STARTDATE'):
    startdate = os.environ.get('UMRIDER_STARTDATE')
else:
    startdate = '20170220'


ctltemplate = """*        ddmmyy
DSET ^/gpfs4/home/akmitra/tmp/mrgdr/GPM%s.grd
*options byteswapped
TITLE 0.25 degranalyzed normal grids
UNDEF -999.0
XDEF  241  LINEAR  50.0 0.25
YDEF  281  LINEAR  -30.0 0.25
ZDEF   1 linear 1 1
TDEF 1 LINEAR %s 1DY 
VARS  1
arf25 0 99 GRIDDED RAINFALL
ENDVARS"""


def createObsRainfallData(today):
    
    outdir = os.path.join(outpath, today)
    if not os.path.exists(outdir): os.makedirs(outdir)
    os.chdir(outdir)
    cDay = datetime.datetime.strptime(today, "%Y%m%d")
    tDay = cDay.strftime('%d%m%Y')
    mDay = cDay.strftime('%d%b%Y').lower()
    
    infile = '/gpfs4/home/akmitra/tmp/mrgdr/GPM%s.grd' % tDay
    if not os.path.isfile(infile): return
    
    ctlfilename = 'IMDGPM_%s.ctl' % today
    f = open(ctlfilename, 'w')
    f.write(ctltemplate % (tDay, mDay))
    f.close()

    f = cdms2.open(ctlfilename)
    rain = f('arf25', latitude=(5, 40), longitude=(65, 110))
    rain.id = 'rainfall'
    rain.comments = 'IMD GPM Merged Rainfall on ' + today

    tunits = 'seconds since 1970-01-01 00:00:00.0'
    csec = cdtime.comptime(cDay.year, cDay.month, cDay.day, 3).torel(tunits).value
    rtime = cdms2.createAxis(numpy.array([csec]), id='time') #60*24*3 sec for 3hr
    rtime.units = tunits
    rtime.designateTime()
    rain.setAxis(0, rtime)

    rnc = 'rf_%s.nc' % today
    f2 = cdms2.open(rnc, 'w') 
    f2.write(rain)
    f2.close()

    f.close()

    cmd = 'rm ' + ctlfilename
    subprocess.call(cmd, shell=True)

    grads_cmd = """'sdfopen   %s'
    'define rainfall=rainfall'
    'set sdfwrite -3dt -rt RFG_%s.nc'
    'sdfwrite  rainfall'
    'quit'
    """ % (rnc, today)

    f3 = open('rainfall.gs', 'w')
    f3.write(grads_cmd)
    f3.close()

    cmd = grads + ' -blc  rainfall.gs'
    subprocess.call(cmd, shell=True)

    cmd = 'rm   rainfall.gs %s ' % rnc
    subprocess.call(cmd, shell=True)

    cmd = 'mv RFG_%s.nc IMD_GPM_Obs_Rainfall_%s.nc  ' % (today, today)
    subprocess.call(cmd, shell=True)
# end of def createObsRainfallData(today):

if __name__ == '__main__':
    
    
    tDay = datetime.datetime.strptime(startdate, "%Y%m%d")
    lag15 = datetime.timedelta(days=checkpastdays)
    pDay = (tDay - lag15) 
    
    while pDay != tDay:                  
        pastDay = pDay.strftime('%Y%m%d')
        outfile = os.path.join(outpath, *[pastDay, 'IMD_GPM_Obs_Rainfall_%s.nc' % pastDay])
        if not os.path.exists(outfile): createObsRainfallData(pastDay)        
        lag1 = datetime.timedelta(days=1)
        pDay = (pDay + lag1)
    # end of while pastDay != tDay:     
# end of if __name__ == '__main__':
