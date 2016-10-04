import os
import pickle
from collections import deque
import math
import random

from geopy import distance, Point
from intervaltree import Interval, IntervalTree

import scipy.sparse
from scipy.sparse import csr_matrix
from scipy.spatial import KDTree
import numpy as np
from pyproj import Proj

import config


def distribute_pointset(points):
    """
    Distributes a list of scanpoints amongst workers and returns 
    a list of lists, each sublist is the set of scanpoints for one 
    of the workers

    Parameters:
        - points: list of (lat, lon) pairs

    Return value:
        - list of lists of (lat, lon) pairs
    """


    # how many points one row should have
    each_row = int(len(points) / config.GRID[0])
    # how many points one column of one row should have
    each_col = int(each_row / config.GRID[1])

    
    # do the actual distribution
    distributed_scanpoints = _actually_distribute_points(points, each_row, each_col)

    # filter out empty scanpoint sets, in case there is one
    final_list = list(filter(
        lambda worker_set: len(worker_set) > 0, 
        distributed_scanpoints
    ))

    return final_list


def _actually_distribute_points(points, each_row, each_col):
    """
    Does the actualy distribution part of distribute_pointset()
    """
    final_list = []
    # sort scanpoints by latitude(point[0])
    lat_sorted_points = deque(sorted(points, key=lambda point: point[0]))

    for row_number in range(0, config.GRID[0]):
        row_cell = []

        # add scanpoint to the list while there are point in the 
        # queue or we have enough points added
        while len(lat_sorted_points) > 0 and len(row_cell) < each_row:
            row_cell.append(lat_sorted_points.popleft())

        # distribute the points of this row
        distribution_for_this_row = _distribute_scanpoint_column(row_cell, each_col)

        final_list.extend(distribution_for_this_row)
    

    # check that that there was nothing skipped(rounding errors)
    if len(lat_sorted_points):
        total_worker = config.GRID[0] * config.GRID[1]

        # something was skipped, add it to the last worker if there are
        # enough lists already, otherwise append it as anothers workers
        # lists
        if len(final_list) < total_worker:
            final_list.append(list(lat_sorted_points))
        else:
            final_list[-1].extend(list(lat_sorted_points))

    return final_list

def _distribute_scanpoint_column(row_cell, each_col):
    """
    Returns splits the points in row_cell amongst #(each_col) workers
    and returns the distribution as list of lists
    """
    return_list = []

    # sort the input list by longitude
    lon_sorted_points = deque(sorted(row_cell, key=lambda point: point[1]))
    
    # iterate over columns in the row
    for col_number in range(0, config.GRID[1]):
        col_cell = []

        # add scanpoint to the list while there are point in the 
        # queue or we have enough points added
        while len(lon_sorted_points) > 0 and len(col_cell) < each_col:
            col_cell.append(lon_sorted_points.popleft())
    

        # append each of the lists
        return_list.append(col_cell)

    # if there are scan points left in the queue(rounding errors), 
    # add them to the last worker
    if len(lon_sorted_points):
        return_list[-1].extend(list(lon_sorted_points))

    return return_list

def _pointset_storage_filename():
    """
    Long name so that we can store all the relevant metadata in the name and
    have easy loading and dumping of the data with pickle
    """
    start_cords = '''{map_start_lat}-{map_start_lon}'''.format(
            map_start_lat=min(config.MAP_START[0], config.MAP_END[0]),
            map_start_lon=min(config.MAP_START[1], config.MAP_END[1]),
    )
    end_cords= '''{map_end_lat}-{map_end_lon}'''.format(
            map_end_lat=max(config.MAP_START[0], config.MAP_END[0]),
            map_end_lon=max(config.MAP_START[1], config.MAP_END[1]),
    )
    filename = '''{start_cords}__{end_cords}.data'''.format(
            start_cords=start_cords,
            end_cords=end_cords
    )
    return filename
    

def already_generated_pointset():
    """
    checks if we already calculated the scan points
    and returns them if that's the case
    """
    filename = _pointset_storage_filename()
    if os.path.isfile(filename):
        points = pickle.load(open(filename, "rb" ))

        return distribute_pointset(points)
    else:
        return False

def _generate_samples(spawn_points):
    """
    Generates a set of scan circles(or rather their centers) randomly around each
    point, so that the point still is included in the scan area.
    """
    # create the IntervalTrees

    # the maximum radius used should have some tolerance so that we can be sure
    # that even if there are small errors we still are in the scan area
    radius = config.SCAN_RADIUS-5
    circles = []

    for point in spawn_points:
        # generate #SAMPLES_PER_POINT circles per spawn point
        for i in range(0, config.SAMPLES_PER_POINT):
            
            # move randomly in any direction/distance inside the radius
            some_distance_away = random.uniform(0,radius)
            bearing = random.uniform(0, 359)
            
            origin = Point(point[0], point[1])
            destination = distance.distance(meters=some_distance_away).destination(origin, bearing)
            
            lat2, lon2 = destination.latitude, destination.longitude

            x = lat2
            y = lon2
            dist = distance.distance((x,y), point).meters
            if dist > config.SCAN_RADIUS:
                print('wtf???')

            # for faster processing
            circles.append((x,y))

    return circles


def _check_scan_point_set_for_safety(points, scan_points):
    """
    Given a final set of scan points and the set which should be covered
    by these scan points, check if they all are covered and if not add
    them as their own scan points
    """
    log = open('minimal_scan_calculations.log', 'a')
    error_counter = 0
    for point in points:
        covered = False
        for circle in scan_points:
            # if there's a circle which covers the point, we can stop the evaluation for this point
            if distance.distance((point['x'], point['y']), (circle[0], circle[1])).meters <= config.SCAN_RADIUS:
                covered = True
                break
        if not covered:
            error_counter += 1
            print('A sad lonely circle has been found :(')
            scan_points.append((point['x'], point['y']))

    msg = '{sp} spawnpoints, {scp} scanpoints, {error} errors catched\n'.format(
            sp=len(points),
            scp=len(scan_points),
            error=error_counter
    )
    log.write(msg)
    log.close()

    return scan_points


def _transform_to_euclidean(coordinates):
    """
    transforms a list of coordinates to euclidean
    coordinates for faster distance calculations.
    tuples have to be (lat, lon)
    """
    to_euclid = Proj(proj='utm')
    coords = [ (to_euclid(point[1], point[0])) for point in coordinates]
    return coords


def choose_best_scan_points(matrix):
    """
    Returns which scan points will be the best as
    list of indicies.
    Parameter:
        Matrix: a matrix with a row for each scan point. An entry (i,j)
                is 1 if the spawn point number j can be reached from
                scan point i
                - eg: p = spawn point, sc = scan point("scan circle")

                      p1  p2  p3 

                 sc1  1   0   1

                 sc2  1   1   0

                 point p1 is in scan reach of both, sc1 and sc2
                 point p2 can only be reached from scan point sc2
                 point p3 can only be reached from scan point sc1
    
    """

    # list of incides of the choosen scan points
    choosen_circles = []

    # array filled with one's, used to mark which points
    # cannot be scanned with the choosen_circles
    identity_array = np.ones((1, matrix.shape[1]))

    # could also be while true, however this ensures
    # termination even if there was a mistake beforehand
    for i in range(0, matrix.shape[1]):

        # maximum unscanned points reachable with a single
        # scan
        nnz = matrix.getnnz(1)
        maximum = nnz.max()
        
        # we can't cover new points, hence we are done
        if maximum == 0:
            print('done')
            break

        # determine which scan point( = row indicies)
        # can scan the most uncovered points
        for i,x in enumerate(nnz):
            if x == maximum:
                new_circle = matrix.getrow(i)
                choosen_circles.append(i)
                break


        # mark which colums we've already covered
        # by setting each of them to zero
        identity_array -= new_circle.toarray()

        # create a diagonal matrix which will be used to
        # erease all covered points from the scan matrix
        mult_matrix = scipy.sparse.diags(identity_array[0])

        # set points we've already scanned to 0
        matrix = matrix * mult_matrix

    return choosen_circles







def calculate_minimal_pointset(spawn_points):
    """
    Given a set of spawn locations calculate and return the best possible scan
    points so that we can reduce the amount of scanning as much as possible.
    Result is already split up into worker sublists
    """
    # check if we have anything to do at all
    pointset = already_generated_pointset()
    if pointset:
        return pointset


    print('Number of spawnpoints: ' +str(len(spawn_points)))
    print('Generating samples...')
    circles = _generate_samples(spawn_points)

    # transform coordinates to euclidean to reduce the time needed
    # for calculating distances(which is very ressource hungry)
    euclid_circles = _transform_to_euclidean(circles)
    euclid_points = _transform_to_euclidean(spawn_points)

    print('Starting distance calculations')

    # create a tree which can be scanned by location
    tree_of_points = KDTree(euclid_points)

    # and query it. returns the distances in matches[0]
    # and the indicies in tree_of_points.data in matches[1]
    matches = tree_of_points.query(
            euclid_circles, 
            # needed: upper bound for #matches.
            50,
            distance_upper_bound=70
    )
    indexes = []
    for index, circle_number in enumerate(matches[1]):

        indexes.extend( [
                [index, point_index]
                for point_index in circle_number 
                if point_index < len(euclid_points)
        ])

    row_ind = [index[0] for index in indexes]
    col_ind = [index[1] for index in indexes]
    entries = [1 for point_index in indexes]

    # for details what this matrix looks like
    # peek at the docstring for the
    # choose_best_scan_points methods
    inside_matrix = scipy.sparse.csr_matrix(
            (entries, (row_ind, col_ind)), 
            shape=((len(euclid_circles), len(euclid_points)))
    )
    print('Distance calculations finished')
    print('Calculating best scan points')
    circle_indexes = choose_best_scan_points(inside_matrix)
    print('Best scan points are calculated')
    print('total scanning points: ' + str(len(circle_indexes)))

    scan_points = [ circles[index] for index in circle_indexes]

    
    points = [{'x': x[0], 'y': x[1]} for x in spawn_points]
    # better check the result
    print('starting safety check to ensure no spawn point missed')
    print('If you ever see this message coming up:\n' + \
          '"A sad lonely circle has been found :("\n' + \
          'report back immediately, as I\'m thing about ' + \
          'removing the safety check for performace reasons')
    scan_points = _check_scan_point_set_for_safety(points, scan_points)
    print('Calculating minimal scan point set done, set size: ' + str(len(scan_points)))

    # We need a list of simple (lat,lon) tuples
    points = list(map(lambda scan_point: (scan_point[0], scan_point[1]), scan_points))
    print(len(points))

    # save the calculations
    filename = _pointset_storage_filename()
    pickle.dump(points, open(filename, "wb" ))

    # and return the scan point set distributes over the available workers
    return distribute_pointset(points)



def inside_radius(p1, p2):
    """
    Checks if the distance of two points is smaller than the scan radius
    """
    return distance.distance((p1['x'], p1['y']), (p2['x'],p2['y'])).meters <= config.SCAN_RADIUS
