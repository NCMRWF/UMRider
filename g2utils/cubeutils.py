import numpy, iris  

def cubeAverager(tmpCube, action='mean', dt='1 hour', 
                actionIntervals='6 hour', tpoint='cbound', fpoint='cbound',
                tbounds=True, fbounds=True):
    """
    :param tmpCube:     The temporary cube data (in Iris format) with non-singleton time dimension
    :param action:      mean| sum (accumulated fields are summed and instantaneous are averaged).
    :param dt:   A standard string representing forecast step duration/intervals.
    :param actionIntervals: A non standard string to add inside cell_methods comments section.
    :param tpoint: cbound | lbound | rbound time point 
    :param fpoint: cbound | lbound | rbound forecast period
    :param tbounds: True | False (False removes time bounds)
    :param fbounds: True | False (False removes fcst bounds)
    :return: meanCube:  An Iris formatted cube date containing the resultant data either as
                        averaged or summed.
    Arulalan.T
    16-Nov-2015    
    """

    # extract time points 
    tpoints = tmpCube.coord('forecast_period').points
    # assign first time point data to mean data 
    meanCube = tmpCube.extract(iris.Constraint(forecast_period=tpoints[0]))
    # get the time coord of first time cube and set to mean
    timeAxFirst = meanCube.coords('time')[0]
    # get the fcst time coord of first time cube and set to mean
    fcstAxFirst = meanCube.coords('forecast_period')[0]
    
    # loop through remaining time points 
    for tp in tpoints[1:]:
        # extract remaining time points and add to meanCube
        lastCube = tmpCube.extract(iris.Constraint(forecast_period=tp))
        meanCube = iris.analysis.maths.add(meanCube, lastCube) 
    # end of for tp in tpoints[1:]:
    
    # get the time coord of last time cube and set to mean
    timeAxLast = lastCube.coords('time')[0]
    # get the fcst time coord of last time cube and set to mean
    fcstAxLast = tmpCube[-1].coords('forecast_period')[0]
    
    if action == 'mean':
        # to compute mean value of meanCube divide it by length of time
        # points which we added before 
        meanCube = iris.analysis.maths.divide(meanCube, float(len(tpoints)))
        print "Converted cube to %s mean : %s" % (actionIntervals, tmpCube.standard_name)
    elif action == 'sum':
        # for sum action, we no need to do here anything, because already 
        # we computed accumulation only!
        print "Converted cube to %s accumulation : %s" % (actionIntervals, tmpCube.standard_name)
    else:
        raise ValueError('argument "%s" not support' % action)
    # end of if not isAccumulation:

    # get the reference time bounds and time points from two extremes    
    rbounds = [timeAxFirst.bounds[0][0], timeAxLast.bounds[-1][-1]]
    
    if tpoint == 'cbound':
        #### THE CENTRE POINT OF REFERENCE TIME BOUNDS
        timepoint = [rbounds[-1] + ((rbounds[-1] - rbounds[0]) / 2.0)]
    elif tpoint == 'lbound':
       ###### THE START BOUNDS OF REFERENCE TIME POINT
        timepoint = [rbounds[0]]
    elif tpoint == 'rbound':    
        ###### THE END BOUNDS OF REFERENCE TIME POINT
        timepoint = [rbounds[-1]]
    # end of if tpoint == 'cbound':
    
    # update the time coordinate with new time point and time bounds
    timeAxFirst.points = timepoint
    # set time bounds if enabled
    if tbounds: 
        timeAxFirst.bounds = rbounds
    else:
        timeAxFirst.bounds = None
    # add the updated time coordinate to the meanCube
    meanCube.add_aux_coord(timeAxFirst)
    
    # get the forecat time bounds and time points from two extremes 
    fbounds = [round(fcstAxFirst.bounds[0][0]), round(fcstAxLast.bounds[-1][-1])] 
    
    if fpoint == 'cbound':
        #### THE CENTRE POINT OF FORECAST TIME BOUNDS
        fcstpoint = [fbounds[0] + ((fbounds[-1] - fbounds[0]) / 2.0)]
    elif fpoint == 'lbound':           
        ###### THE START BOUNDS OF FORECAST TIME POINT
        fcstpoint = [fbounds[0]]         
    elif fpoint == 'rbound':           
        ###### THE END BOUNDS OF FORECAST TIME POINT
        fcstpoint = [fbounds[-1]]        
    # end of if fpoint == 'cbound':   
    
    # update the time coordinate with new fcst time point and fcst time bounds
    fcstAxFirst.points = fcstpoint
    # set fcst bounds if enabled
    if fbounds: 
        fcstAxFirst.bounds = fbounds
    else:
        fcstAxFirst.bounds = None
    # add the updated fcst time coordinate to the meanCube
    meanCube.add_aux_coord(fcstAxFirst)
    # add attributes back to meanCube
    meanCube.attributes = tmpCube.attributes  
    # add standard_name
    meanCube.standard_name = tmpCube.standard_name
    meanCube.long_name = tmpCube.long_name if tmpCube.long_name else tmpCube.standard_name
    
    if action == 'mean':
        cm = iris.coords.CellMethod('mean', ('time',), intervals=(dt,), 
                                     comments=(actionIntervals+' mean',))
    elif action == 'sum':
        cm = iris.coords.CellMethod('sum', ('time',), intervals=(dt,), 
                                     comments=(actionIntervals+' accumulation',))
    
    # add cell_methods to the meanCube
    if fbounds: meanCube.cell_methods = (cm,)   
    
    # make memory free
    del tmpCube
    
    # return mean cube 
    return meanCube
# end of def cubeAverager(...):


def cubeAddSubtractor(cube, otherCube, action, standard_name=None, 
                        long_name=None, removeSTASH=True):
    '''
    iris.analysis.maths.subtract doesnt serving out purpose.
    So this cubeAddSubtractor Additiion/subtraction two cubes and set all 
    necessary meta information.

    Arulalan.T
    12-Fen-2016
    '''
    
    timeDimension = True if len(cube.shape) == 3 else False
    attr = cube.attributes
    if removeSTASH and 'STASH' in attr: attr.pop('STASH')
    lname = long_name if long_name else cube.long_name
    sname = standard_name if standard_name else cube.standard_name
    cm = cube.cell_methods[0] if cube.cell_methods else None 
    unit = cube.units 
    if action in ['add', 'sum', 'addition']:
        # do the simple addition
        resultant = cube.data + otherCube.data
    elif action in ['sub', 'remove', 'subtraction']:
        # do the simple substraction
        resultant = cube.data - otherCube.data
    # set fill_value 
    numpy.ma.set_fill_value(resultant, 9.999e+20)    
    resultant = iris.cube.Cube(data=resultant, units=unit, standard_name=sname, 
                       long_name=lname, attributes=attr, cell_methods=(cm,))
    idx = 0
    if timeDimension:
        resultant.add_dim_coord(cube.coords('time')[0], idx)
        idx += 1        
    resultant.add_dim_coord(cube.coords('latitude')[0], idx)
    resultant.add_dim_coord(cube.coords('longitude')[0], idx+1)
    for axc in cube.aux_coords: resultant.add_aux_coord(axc)    
    # return the updated, resultant cube
    return resultant
# end of def cubeAddSubtractor(...):

def cubeCummulator(cubes, standard_name=None, long_name=None, unit=None,
                    removeSTASH=False, addZerosFirstCube=True):
    '''
    cubeCummulator : It cummulate the data over time from starting cube.
    addZerosFirstCube : True | False. It does add zeros cubes begining of the 
      cummulated cubes (For the tigge purpose).
    Return : Generators | Yields the cummulated cubes
    
    Arulalan.T
    29-Sep-2016
    '''
    
    # first cube 
    precube = cubes[0]
    
    timeDimension = True if len(precube.shape) == 3 else False
    attr = precube.attributes
    if removeSTASH and 'STASH' in attr: attr.pop('STASH')
    lname = long_name if long_name else precube.long_name
    sname = standard_name if standard_name else precube.standard_name
    if sname == 'None': sname = None
#    cm = precube.cell_methods[0] if precube.cell_methods else None 
    unit = unit if unit else precube.units
    cm = iris.coords.CellMethod('sum', ('time',), intervals=('1 hour',), 
                     comments=(' accumulation',))
    
    precube.cell_methods = (cm,)
    precube.standard_name = sname
    precube.long_name = lname
        
    timeAxFirst = cubes[0].coords('time')[0]
    fcstAxFirst = cubes[0].coords('forecast_period')[0]

    if addZerosFirstCube:
        # get the time coord of first time cube and set to zerocube
        tbounds = [timeAxFirst.bounds[0][0], timeAxFirst.bounds[0][0]]
        timeAxFirst.points = [tbounds[0]]
        timeAxFirst.bounds = tbounds
        
        # get the fcst time coord of first time cube and set to zerocube
        fbounds = [fcstAxFirst.bounds[0][0], fcstAxFirst.bounds[0][0]]
        fcstAxFirst.points = [fbounds[0]]
        fcstAxFirst.bounds = fbounds
    
        # create first cube filled with zeros (for TIGGE cummulate standard)
        zerocube = numpy.ma.zeros(precube.data.shape)
        # set fill_value 
        numpy.ma.set_fill_value(zerocube, 9.999e+20)    
        zerocube = iris.cube.Cube(data=zerocube, units=unit, standard_name=sname, 
                           long_name=lname, attributes=attr, cell_methods=(cm,))
        # add the updated time coordinate to the meanCube
        zerocube.add_aux_coord(timeAxFirst)
        # add the updated fcst time coordinate to the meanCube
        zerocube.add_aux_coord(fcstAxFirst)
        # add dimension coords 
        zerocube.add_dim_coord(precube.coords('latitude')[0], 0)
        zerocube.add_dim_coord(precube.coords('longitude')[0], 1)
        for axc in precube.aux_coords: 
            if axc.standard_name in ['forecast_period', 'time']: continue
            zerocube.add_aux_coord(axc)    
                
        # add cell_methods to the zerocube
        zerocube.cell_methods = (cm,)
        
        # yeilding zeros cube 
        yield zerocube
    # end of if addZerosFirstCube:
            
    # yielding first cube 
    yield precube 
    
    timelen = cubes.coords('time')[0].shape[0]
    for idx in range(1, timelen, 1):
        # loop through over time index from second cubes onwards
        cummulated = cubes[idx].data + precube.data 

        # get the time coord of first time cube and set to mean
        timeAx = cubes[idx].coords('time')[0]
        tbounds = [timeAxFirst.bounds[0][0], timeAx.bounds[-1][-1]]
        timeAx.points = [tbounds[0] + ((tbounds[-1] - tbounds[0]) / 2.0)]
        timeAx.bounds = tbounds
        
        # get the fcst time coord of first time cube and set to mean
        fcstAx = cubes[idx].coords('forecast_period')[0]
        fbounds = [fcstAxFirst.bounds[0][0], fcstAx.bounds[-1][-1]]
        fcstAx.points = [fbounds[0] + ((fbounds[-1] - fbounds[0]) / 2.0)]
        fcstAx.bounds = fbounds
        
        # set fill_value 
        numpy.ma.set_fill_value(cummulated, 9.999e+20)    
        cummulated = iris.cube.Cube(data=cummulated, units=unit, standard_name=sname, 
                           long_name=lname, attributes=attr, cell_methods=(cm,))
        # add the updated time coordinate to the meanCube
        cummulated.add_aux_coord(timeAx)
        # add the updated fcst time coordinate to the meanCube
        cummulated.add_aux_coord(fcstAx)
        # add dimension coords 
        cummulated.add_dim_coord(cubes[idx].coords('latitude')[0], 0)
        cummulated.add_dim_coord(cubes[idx].coords('longitude')[0], 1)
        for axc in cubes[idx].aux_coords: 
            if axc.standard_name in ['forecast_period', 'time']: continue
            cummulated.add_aux_coord(axc)    
        
         # add cell_methods to the zerocube
        cummulated.cell_methods = (cm,)
        
        # yeilding contious time-cummulated cubes
        yield cummulated
        # assign cummulated to precube 
        precube = cummulated
    # end of for idx in range(1, timelen, 1):
# end of def cubeCummulator(...):

def cubeRealizationAverager(tmpCube, action='mean', dr='1 ENS'):
    """
    :param tmpCube:     The temporary cube data (in Iris format) with non-singleton time dimension
    :param action:      mean| sum (accumulated fields are summed and instantaneous are averaged).
    :param dr:   A standard string representing realization step duration/intervals.
    
    :return: meanCube:  An Iris formatted cube date containing the resultant data either as
                        averaged or summed.
    Arulalan.T
    18-July-2016
    """

    # extract realization points 
    rpoints = tmpCube.coord('realization').points
    # get the time coord of first time cube and set to mean
    timeAxFirst = tmpCube.coords('time')[0]
    fcstAxFirst = tmpCube.coords('forecast_period')[0]
    # assign first realization point data to mean data 
    meanCube = tmpCube.extract(iris.Constraint(realization=rpoints[0]))
    if meanCube.has_lazy_data():
        print "Loaded", meanCube.standard_name, "into memory",
        ## By accessing meanCube.data (even for printing), the full 
        ## data has been loaded into memory instead of being lazy 
        ## data. Otherwise while making average over realization it gets filled
        ## with 1e+20. So it is must one.
        print "- min", meanCube.data.min(), "max", meanCube.data.max(),
        print "has_lazy_data =", meanCube.has_lazy_data()
    # end of if tmpCube.has_lazy_data():

    # loop through remaining realization points 
    for rp in rpoints[1:]:
        # extract remaining realization points and add to meanCube
        lastCube = tmpCube.extract(iris.Constraint(realization=rp))
        meanCube = iris.analysis.maths.add(meanCube, lastCube) 
    # end of for rp in rpoints[1:]:
    
    if action == 'mean':
        # to compute mean value of meanCube divide it by length of time
        # points which we added before 
        meanCube = iris.analysis.maths.divide(meanCube, float(len(rpoints)))
        print "Converting cube to realization mean : %s" % (tmpCube.standard_name)
    elif action == 'sum':
        # for sum action, we no need to do here anything, because already 
        # we computed accumulation only!
        print "Converting cube to realization accumulation : %s" % (tmpCube.standard_name)
    else:
        raise ValueError('argument "%s" not support' % action)
    # end of if action == 'mean':
    
    if action == 'mean':
        cm = iris.coords.CellMethod('mean', ('realization',), intervals=(dr,), 
                                     comments=('mean of (1 control run + %d ensemble members)' % (len(rpoints)-1)))
    elif action == 'sum':
        cm = iris.coords.CellMethod('sum', ('realization',), intervals=(dr,), 
                                     comments=('accumulation of (1 control run + %d ensemble members)' % (len(rpoints)-1)))
        
    meanCube = iris.cube.Cube(data=meanCube.data, 
                       units=tmpCube.units, 
                       standard_name=tmpCube.standard_name, 
                       long_name=tmpCube.long_name, 
                       attributes=tmpCube.attributes,
                       cell_methods=(cm,))

    idx = 0
    for ax in tmpCube.coords(): 
        name = ax.standard_name if ax.standard_name else ax.long_name
        if name == 'realization': continue
        if isinstance(ax, iris.coords.DimCoord):      
            print ax
            if ax.standard_name in ['forecast_period', 'time'] and len(ax.points) == 1:
                meanCube.add_aux_coord(ax)
            else:
                meanCube.add_dim_coord(ax, idx)
                idx += 1
        elif isinstance(ax, iris.coords.AuxCoord):
            meanCube.add_aux_coord(ax)
    # end of for ax in tmpCube.coords(): 
    print meanCube    

    # make memory free
    del tmpCube
    
    # return mean cube 
    return meanCube
# end of def cubeRealizationAverager(...):
