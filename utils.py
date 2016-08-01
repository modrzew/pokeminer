import math
from geopy import distance
from geopy import Point

import config


def get_map_center():
    """Returns center of the map"""
    if isinstance(config.GRID[0], (int, long, float, complex)):
        lat = (config.MAP_END[0] + config.MAP_START[0]) / 2
        lon = (config.MAP_END[1] + config.MAP_START[1]) / 2
        return lat, lon
    else:
        lat = (config.MAP_END[0][0] + config.MAP_START[0][0]) / 2
        lon = (config.MAP_END[0][1] + config.MAP_START[0][1]) / 2
        return lat, lon


def get_scan_area_single(GRID, MAP_START, MAP_END):
    """Returns the square kilometers for configured scan area"""
    lat1 = MAP_START[0]
    lat2 = MAP_END[0]
    lon1 = MAP_START[1]
    lon2 = MAP_END[1]
    p1 = Point(lat1, lon1)
    p2 = Point(lat1, lon2)
    p3 = Point(lat1, lon1)
    p4 = Point(lat2, lon1)

    width = distance.distance(p1, p2).kilometers
    height = distance.distance(p3, p4).kilometers
    area = int(width * height)
    return area

def get_scan_area():
    if isinstance(config.GRID[0], (int, long, float, complex)):
        return get_scan_area_single(config.GRID, config.MAP_START, config.MAP_END)
    else:
        area = 0
        for i in range(len(config.GRID)):
            area = area + get_scan_area_single(config.GRID[i], config.MAP_START[i], config.MAP_END[i])
        return area


def get_start_coords(p):
    """Returns center of square for given worker"""
    center = [sum(y) / len(y) for y in zip(*p)]
    return center[0], center[1]


def float_range(start, end, step):
    """xrange for floats, also capable of iterating backwards"""
    if start > end:
        while end < start:
            yield start
            start += -step
    else:
        while start < end:
            yield start
            start += step


def get_points_per_worker_single(GRID, MAP_START, MAP_END):
    """Returns all points that should be visited for whole grid"""
    total_workers = GRID[0] * GRID[1]
    lat_gain = getattr(config, 'LAT_GAIN', 0.0015)
    lon_gain = getattr(config, 'LON_GAIN', 0.0025)
    points = [[] for _ in range(total_workers)]
    total_rows = math.ceil(
        abs(MAP_START[0] - MAP_END[0]) / lat_gain
    )
    total_columns = math.ceil(
        abs(MAP_START[1] - MAP_END[1]) / lon_gain
    )
    for map_row, lat in enumerate(
        float_range(MAP_START[0], MAP_END[0], lat_gain)
    ):
        for map_col, lon in enumerate(
            float_range(MAP_START[1], MAP_END[1], lon_gain)
        ):
            # Figure out which worker this should go to
            grid_row = int(map_row / float(total_rows) * GRID[0])
            grid_col = int(map_col / float(total_columns) * GRID[1])
            worker_no = grid_row * GRID[1] + grid_col
            points[worker_no].append((lat, lon))
    points = [sort_points_for_worker(p) for p in points]
    return points
    
def get_points_per_worker():
    if isinstance(config.GRID[0], (int, long, float, complex)):
        return get_points_per_worker_single(config.GRID, config.MAP_START, config.MAP_END)
    else:
        points = []
        for i in range(len(config.GRID)):
            points.extend(get_points_per_worker_single(config.GRID[i], config.MAP_START[i], config.MAP_END[i]))
        return points



def sort_points_for_worker(p):
    center = get_start_coords(p)
    return sorted(p, key=lambda p: get_distance(p, center))


def get_distance(p1, p2):
    return math.sqrt(pow(p1[0] - p2[0], 2) + pow(p1[1] - p2[1], 2))
