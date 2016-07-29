import os
DB_ENGINE = os.environ.get('DATABASE_URL', '') or 'postgresql://localhost'  # anything SQLAlchemy accepts
# the office
# MAP_START = (37.7764953, -122.3941588)  # top left corner
# MAP_END = (37.7763596,-122.3886228)  # bottom right corner

# SF
MAP_START = (37.8104085,-122.5252033)
MAP_END = (37.7064505,-122.3559452)


# LAT_GAIN and LON_GAIN can be configured to tell how big a space between
# points visited by worker should be. LAT_GAIN should also compensate for
# differences in distance between degrees as you go north/south.
LAT_GAIN = 0.0015
LON_GAIN = 0.0025

ACCOUNTS = [
    # username, password, service (google/ptc)
]
	
for key in os.environ.keys():
	if 'ACCOUNT_' in key:
		ACCOUNTS.append((os.environ[key], 'password1', 'ptc'))

if len(ACCOUNTS) == 1:
    GRID = (1, 1)  # row, column
else:
    grid_rows = len(ACCOUNTS)/2
    grid_columns = 2
    GRID = (grid_rows, grid_columns) # row, column

# Trash Pokemon won't be shown on the live map.
# Their data will still be collected to the database.
TRASH_IDS = [16, 19, 41, 96]

# List of stage 2 & rare evolutions to show in the report
STAGE2 = [
    3, 6, 9, 12, 15, 18, 31, 34, 45, 62, 65, 68, 71, 76, 94, 139, 141, 149
]