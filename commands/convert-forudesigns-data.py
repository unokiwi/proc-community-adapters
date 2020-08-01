import click
from datetime import datetime
from dotenv import load_dotenv
import json
import math
import os
import pprint
import re
import statistics
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Custom libraries.
from lib import Logger as UkLogger

load_dotenv()

'''
Define constants.
'''

# Dirs.
LOGS_DIR = os.path.realpath(os.path.dirname(__file__) + '/../logs')
STATIC_RESOURCES_DIR = os.path.realpath(os.path.dirname(__file__) + '/../resources')
PROCESSING_YMD = datetime.today().strftime('%Y%m%d')
TX_IN_DIR = STATIC_RESOURCES_DIR + '/forudesigns/in'
TX_OUT_DIR = STATIC_RESOURCES_DIR + '/forudesigns/out'

# Logger.
LOG_LEVEL_ERROR = 40
LOG_LEVEL_WARNING = 30
LOG_LEVEL_INFO = 20
LOG_LEVEL_DEBUG = 10

VERBOSITY_DEBUG = 3
VERBOSITY_INFO = 2
VERBOSITY_WARNING = 1
VERBOSITY_NORMAL = 0

SORT_ALGO_NONE = -1
SORT_ALGO_DIRECT = 0
SORT_ALGO_ROT_30 = 30
SORT_ALGO_ROT_45 = 45
SORT_ALGO_ROT_60 = 60
SORT_ALGO_AUTO = 99

# Define logger.
log_file = LOGS_DIR + '/' + PROCESSING_YMD + '-convert-forudesigns-data.log'
logger = UkLogger(log_file=log_file, name='convert-forudesigns-data')

# Hijack system error handling.
sys.excepthook = logger.exception_handler

# Initialize pretty printer.
pp = pprint.PrettyPrinter(indent=2, depth=10)


@click.command()
@click.option('-v', '--verbose', count=True)
def convert_forudesigns_data(verbose):
    # Set logger verbosity.
    logger.print_verbosity = verbose
    logger.log_verbosity = int(os.getenv('LOG_VERBOSITY', '2'))

    # Process summary.
    for subdir in os.listdir(TX_IN_DIR):
        path = os.path.join(TX_IN_DIR, subdir)
        logger.log('Checking path ' + path, LOG_LEVEL_INFO)
        if not os.path.isdir(path):
            continue
        logger.log('Found directory ' + path, LOG_LEVEL_INFO)
        for filename in os.listdir(path):
            if not filename.endswith('.txt'):
                continue
            file_path = path + '/' + filename
            logger.log('Processing file ' + file_path, LOG_LEVEL_INFO)
            # Forudesigns data has GB2312 encoding.
            # Read data
            raw = []
            with open(file=file_path, mode='r', encoding='gb2312') as file:
                section = 0
                section_after_has_began = False
                n = 0
                for line in file:
                    line = line.replace('\n', '')
                    if line == '':
                        # Empty line. Happens at section break and at EOF.
                        if section == 0:
                            section = 1
                        elif section_after_has_began:
                            section = 99
                        continue
                    elif not re.match('^[0-9,]+$', line[0]):
                        # Not number. Skip line.
                        continue

                    # Line is not empty and contains numbers
                    parts = line.split(',')
                    if section == 0:
                        raw.append({
                            'before': {
                                'x': int(parts[0]),
                                'y': int(parts[1])
                            },
                            'after': {}
                        })
                    elif section == 1:
                        section_after_has_began = True
                        raw[n]['after'] = {
                            'x': int(parts[0]),
                            'y': int(parts[1])
                        }
                        n += 1
                    else:
                        logger.log('ERROR: More than 2 sections delimited by empty lines found in file.',
                                   LOG_LEVEL_ERROR)
                        return

            # # Note if first 4 entries are always border box, we may want to discard them.
            # raw = raw[4:]

            rows = get_chunked_rows(raw, verbose)
            if rows is None:
                return

            # Re-order inside of rows by x.
            # Re-order rows by median y value in each row.
            for row in rows:
                row.sort(key=lambda x: x['before']['x'])
            rows.sort(key=lambda x: statistics.median([y['before']['y'] for y in x]))

            # triangles = generate_triangles_blind(num_cols=len(rows[0]), num_rows=len(rows))
            triangles = generate_triangles_partial(rows)

            points_before = []
            points_after = []
            for row in rows:
                for value in row:
                    points_before.append(value['before'])
                    points_after.append(value['after'])

            json_data = {
                'images': [
                    {
                        'points': points_before
                    },
                    {
                        'points': points_after
                    }
                ],
                'triangles': triangles
            }

            tx_output_dir = os.path.join(TX_OUT_DIR, subdir)
            tx_output_path = f"{tx_output_dir}/{os.path.splitext(filename)[0]}.json"
            if not os.path.exists(tx_output_dir):
                os.makedirs(tx_output_dir)
            text = json.dumps(json_data)

            logger.log('Writing output file to ' + tx_output_path, LOG_LEVEL_INFO)
            with open(tx_output_path, 'w') as tx_file:
                tx_file.write(text)


def generate_triangles_blind(num_cols, num_rows):
    triangles = []
    tri_cols = num_cols - 1
    tri_rows = num_rows - 1
    for i in range(tri_rows):
        counter = i * num_cols
        for j in range(tri_cols):
            triangles.append([counter, counter + 1, counter + num_cols])
            triangles.append([counter + 1, counter + 1 + num_cols, counter + num_cols])
            counter += 1

    return triangles


def generate_triangles_partial(rows):
    triangles = []

    # We will draw triangles for rows that have the same number of elements.
    last_num_cols = 0
    counter = 0
    for i, row in enumerate(rows):
        num_cols = len(row)

        # Only generate triangles for this row if number of elements per row are equal.
        if last_num_cols == num_cols:
            # Generate triangles starting from previous row counters.
            start = counter - num_cols
            tri_cols = num_cols - 1
            for j in range(tri_cols):
                triangles.append([start, start + 1, start + num_cols])
                triangles.append([start + 1, start + 1 + num_cols, start + num_cols])
                start += 1

        # Update row counters to include current row length.
        counter += num_cols
        last_num_cols = num_cols

    return triangles


def get_chunked_rows(raw, verbose, algo=SORT_ALGO_AUTO):
    # We are going to begin with a long list of assumptions, as follows:
    # 1. Points belonging to the same each row will have lower y std dev.
    # 2. Recommended rows to columns ratio is 1:1.

    raw_elements_length = len(raw)
    recommended_row_to_col_ratio = 1
    logger.log('Elements in raw: ' + str(raw_elements_length), LOG_LEVEL_DEBUG)
    if raw_elements_length < 25:
        logger.log('Total elements < 25, detection will likely be problematic.', LOG_LEVEL_WARNING)
    suggested_rows_count = math.ceil(math.sqrt(raw_elements_length / recommended_row_to_col_ratio))

    # First we will clean up data by ordering by y and x, depending on algo.
    if algo == SORT_ALGO_NONE:
        # No sort, assume input data is orderly.
        mapped = [x['before']['y'] for x in raw]
    elif algo == SORT_ALGO_DIRECT:
        mapped = [x['before']['y'] for x in raw]
    elif algo == SORT_ALGO_ROT_30:
        # Rotate 30 deg CCW: y' = -sin(30 deg) * x + cos(30 deg) * y
        mapped = [-0.5 * x['before']['x'] + 0.866 * x['before']['y'] for x in raw]
    elif algo == SORT_ALGO_ROT_45:
        # Rotate 45 deg CCW: y' = -sin(45 deg) * x + cos(45 deg) * y
        mapped = [-0.7071 * x['before']['x'] + 0.7071 * x['before']['y'] for x in raw]
    elif algo == SORT_ALGO_ROT_60:
        # Rotate 60 deg CCW: y' = -sin(60 deg) * x + cos(60 deg) * y
        mapped = [-0.866 * x['before']['x'] + 0.5 * x['before']['y'] for x in raw]
    else:
        # Perform all rotation algos and pick one with least amount of rows (best fit).
        rows_sets = [
            {
                'rows': get_chunked_rows(raw, verbose, SORT_ALGO_DIRECT),
                'algo': SORT_ALGO_DIRECT,  # Listed first for higher priority if this works.
                'sort': 0
            },
            {
                'rows': get_chunked_rows(raw, verbose, SORT_ALGO_NONE),
                'algo': SORT_ALGO_NONE,
                'sort': 0
            }
        ]
        for row_set in rows_sets:
            rows_count_ratio = len(row_set['rows']) / suggested_rows_count
            row_set['sort'] = rows_count_ratio if rows_count_ratio > 1 else 1/rows_count_ratio
        rows_sets.sort(key=lambda x: x['sort'])
        logger.log(f"Algo selected: {rows_sets[0]['algo']} Length: {len(rows_sets[0]['rows'])}", LOG_LEVEL_INFO)
        return rows_sets[0]['rows']

    # Sort raw values and mapped values together.
    if algo != SORT_ALGO_NONE:
        mapped, raw = map(list, zip(*sorted(zip(mapped, raw), key=lambda pair: pair[0])))

    min_cols = 2
    max_compare_cols = max(min_cols, min(5, suggested_rows_count))
    logger.log(f'Suggested max comparison cols between {min_cols}-5: {max_compare_cols}', LOG_LEVEL_DEBUG)
    last_stdev = 1000
    min_stdev = 3
    new_row_stdev_multiplier_threshold = 2.5
    processed = 0
    rows = []

    logger.log(f'Algo: {algo}', LOG_LEVEL_DEBUG)
    logger.log(mapped, LOG_LEVEL_DEBUG)
    # Each iteration detects the beginning of a fresh row using moving elements with variable size of at least min_cols.
    bracket_size = min_cols
    for end in range(processed + bracket_size, raw_elements_length):
        # Calculate starting cursor.
        start = end - bracket_size

        stdev = statistics.stdev(mapped[start:end])
        logger.log(f'Start: {start} End: {end} Std Dev: {stdev}', LOG_LEVEL_DEBUG)

        if stdev > last_stdev * new_row_stdev_multiplier_threshold:
            # Std dev jumped up too much, meaning we have found the beginning of a new row.
            # We will save the current row.
            rows.append(raw[processed:end-1])

            # and processed the beginning index of the next row.
            processed = end-1
            # reset bracket size
            bracket_size = min_cols
        else:
            # Element belongs to same row, attempt to increase bracket_size for future comparison.
            bracket_size = min(bracket_size + 1, max_compare_cols)

        # Set this stdev as new stdev to compare against.
        last_stdev = max(min_stdev, stdev)

    # Also transfer last row.
    rows.append(raw[processed:])

    # Display some statistics for debugging.
    if verbose >= VERBOSITY_INFO:
        length_stats = [len(x) for x in rows]
        logger.log(f'Displaying row length stats with algo {algo}.', LOG_LEVEL_INFO)
        logger.log('Raw elements: ' + str(raw_elements_length), LOG_LEVEL_INFO)
        logger.log('Rows: ' + str(len(rows)), LOG_LEVEL_INFO)
        logger.log('Max: ' + str(max(length_stats)), LOG_LEVEL_INFO)
        logger.log('Median: ' + str(statistics.median(length_stats)), LOG_LEVEL_INFO)
        logger.log('Mode: ' + str(statistics.multimode(length_stats)), LOG_LEVEL_INFO)

    return rows

    # # Failed strategy
    # # Clean data
    # raw.sort(key=lambda x: x['before']['y'] * 10000 + x['before']['x'])
    #
    # # Take a point, find top 2 neighbors with increase in X, pick closest 1 as next neighbor.
    # # Assume increase in y > N times increase in x is a bad pick, and we will start a new row instead.

    # cleaned = []
    # row = []
    # y_inc_multi_threshold_new_row = 1.5
    # y_inc_multi_threshold_no_compute = 4
    # nearest_neighbors = [{
    #     'index': None,
    #     'dist': 200000000,
    #     'new_row': 0
    # }]
    # while len(raw):
    #     print('Elements remaining: ' + str(len(raw)))
    #
    #     # If both top candidates are too far away vertically, then assume no good candidates and begin new row.
    #     # If second candidate is ok, then use that.
    #     if nearest_neighbors[0]['new_row']:
    #         if len(nearest_neighbors) > 1 and not nearest_neighbors[1]['new_row']:
    #             nearest_neighbors[0]['index'] = nearest_neighbors[1]['index']
    #         else:
    #             nearest_neighbors[0]['index'] = None
    #
    #     if nearest_neighbors[0]['index'] is None:
    #         cleaned.append(row)
    #         row = []
    #         current_point = raw.pop(0)
    #     else:
    #         current_point = raw.pop(nearest_neighbors[0]['index'])
    #         # No more elements remaining.
    #         if not len(raw):
    #             cleaned.append(row)
    #             break
    #
    #     row.append(current_point)
    #     nearest_neighbors = [{
    #         'index': None,
    #         'dist': 200000000,
    #         'new_row': 0
    #     }]
    #     for i, point in enumerate(raw):
    #         if point['before']['x'] < current_point['before']['x']:
    #             continue
    #         x_shift = point['before']['x'] - current_point['before']['x']
    #         y_shift = point['before']['y'] - current_point['before']['y']
    #         new_row = 0
    #         if x_shift is 0 or (abs(y_shift) / x_shift > y_inc_multi_threshold_no_compute):
    #             # Too much y shift. Assume point is too far away and not worth computing.
    #             continue
    #         if x_shift is 0 or (abs(y_shift) / x_shift > y_inc_multi_threshold_new_row):
    #             # Too much y shift. Assume point belongs in a new row.
    #             new_row = 1
    #
    #         dist_sq = x_shift ** 2 + y_shift ** 2
    #         if dist_sq < nearest_neighbors[0]['dist']:
    #             nearest_neighbors.insert(0, {
    #                 'index': i,
    #                 'dist': dist_sq,
    #                 'new_row': new_row
    #             })
    #         elif dist_sq < nearest_neighbors[1]['dist']:
    #             nearest_neighbors.insert(1, {
    #                 'index': i,
    #                 'dist': dist_sq,
    #                 'new_row': new_row
    #             })
    #
    #     # print(current_point)
    #     # print(nearest_neighbor)
    #     # print(raw[nearest_neighbor])


if __name__ == '__main__':
    convert_forudesigns_data()
