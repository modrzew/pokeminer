# -*- coding: utf-8 -*-
from datetime import datetime
import argparse
import logging
import os
import random
import sys
import threading
import time

from pgoapi import (
    exceptions as pgoapi_exceptions,
    PGoApi,
    utilities as pgoapi_utils,
)

import config
import db
import utils


# Check whether config has all necessary attributes
REQUIRED_SETTINGS = (
    'DB_ENGINE',
    'ENCRYPT_PATH',
    'CYCLES_PER_WORKER',
    'MAP_START',
    'MAP_END',
    'GRID',
    'ACCOUNTS',
    'SCAN_RADIUS',
    'SCAN_DELAY',
    'DISABLE_WORKERS',
)
for setting_name in REQUIRED_SETTINGS:
    if not hasattr(config, setting_name):
        raise RuntimeError('Please set "{}" in config'.format(setting_name))


workers = {}
local_data = threading.local()


class MalformedResponse(Exception):
    """Raised when server response is malformed"""

class BannedAccount(Exception):
    """Raised when account is banned"""

def configure_logger(filename='worker.log'):
    logging.basicConfig(
        filename=filename,
        format=(
            '[%(asctime)s][%(threadName)10s][%(levelname)8s][L%(lineno)4d] '
            '%(message)s'
        ),
        style='%',
        level=logging.INFO,
    )

logger = logging.getLogger()


class Slave(threading.Thread):
    """Single worker walking on the map"""
    def __init__(
        self,
        group=None,
        target=None,
        name=None,
        worker_no=None,
        points=None,
    ):
        super(Slave, self).__init__(group, target, name)
        self.worker_no = worker_no
        local_data.worker_no = worker_no
        self.points = points
        self.count_points = len(self.points)
        self.step = 0
        self.cycle = 0
        self.seen_per_cycle = 0
        self.total_seen = 0
        self.error_code = None
        self.running = True
        center = self.points[0]
        self.api = PGoApi()
        #self.api.activate_signature(config.ENCRYPT_PATH)
        self.api.set_position(center[0], center[1], 100)  # lat, lon, alt
        if hasattr(config, 'PROXIES') and config.PROXIES:
            self.api.set_proxy(config.PROXIES)

    def run(self):
        """Wrapper for self.main - runs it a few times before restarting

        Also is capable of restarting in case an error occurs.
        """
        self.cycle = 1
        self.error_code = None

        username, password, service = utils.get_worker_account(self.worker_no)
        while True:
            try:
                loginsuccess = self.api.login(
                    username=username,
                    password=password,
                    provider=service,
                )
                if not loginsuccess:
                    self.error_code = 'LOGIN FAIL'
                    self.restart()
                    return
            except pgoapi_exceptions.AuthException:
                logger.warning('Login failed!')
                self.error_code = 'LOGIN FAIL'
                self.restart()
                return
            except pgoapi_exceptions.NotLoggedInException:
                logger.error('Invalid credentials')
                self.error_code = 'BAD LOGIN'
                self.restart()
                return
            except pgoapi_exceptions.ServerBusyOrOfflineException:
                logger.info('Server too busy - restarting')
                self.error_code = 'RETRYING'
                self.restart()
                return
            except pgoapi_exceptions.ServerSideRequestThrottlingException:
                logger.info('Server throttling - sleeping for a bit')
                time.sleep(random.uniform(1, 5))
                continue
            except Exception:
                logger.exception('A wild exception appeared!')
                self.error_code = 'EXCEPTION'
                self.restart()
                return
            break
        while self.cycle <= config.CYCLES_PER_WORKER:
            if not self.running:
                self.restart()
                return
            try:
                self.main()
            except MalformedResponse:
                logger.warning('Malformed response received!')
                self.error_code = 'RESTART'
                self.restart()
                return
            except BannedAccount:
                self.error_code = 'BANNED?'
                self.restart(30, 90)
                return
            except Exception:
                logger.exception('A wild exception appeared!')
                self.error_code = 'EXCEPTION'
                self.restart()
                return
            if not self.running:
                self.restart()
                return
            self.cycle += 1
            if self.cycle <= config.CYCLES_PER_WORKER:
                logger.info('Going to sleep for a bit')
                self.error_code = 'SLEEP'
                self.running = False
                time.sleep(random.randint(30, 60))
                logger.info('AWAKEN MY MASTERS')
                self.running = True
                self.error_code = None
        self.error_code = 'RESTART'
        self.restart()

    def main(self):
        """Heart of the worker - goes over each point and reports sightings"""
        session = db.Session()
        self.seen_per_cycle = 0
        self.step = 0
        for i, point in enumerate(self.points):
            if not self.running:
                return
            logger.info('Visiting point %d (%s %s)', i, point[0], point[1])
            self.api.set_position(point[0], point[1], 0)
            cell_ids = pgoapi_utils.get_cell_ids(point[0], point[1])
            self.api.set_position(point[0], point[1], 100)
            response_dict = self.api.get_map_objects(
                latitude=pgoapi_utils.f2i(point[0]),
                longitude=pgoapi_utils.f2i(point[1]),
                cell_id=cell_ids
            )
            if not isinstance(response_dict, dict):
                logger.warning('Response: %s', response_dict)
                raise MalformedResponse
            if response_dict['status_code'] == 3:
                logger.warning('Account banned')
                raise BannedAccount
            responses = response_dict.get('responses')
            if not responses:
                logger.warning('Response: %s', response_dict)
                raise MalformedResponse
            map_objects = response_dict['responses'].get('GET_MAP_OBJECTS', {})
            pokemons = []
            forts = []
            if map_objects.get('status') == 1:
                for map_cell in map_objects['map_cells']:
                    for pokemon in map_cell.get('wild_pokemons', []):
                        # Care only about 15 min spawns
                        # 30 and 45 min ones (negative) will be just put after
                        # time_till_hidden is below 15 min
                        # As of 2016.08.14 we don't know what values over
                        # 60 minutes are, so ignore them too
                        invalid_time = (
                            pokemon['time_till_hidden_ms'] < 0 or
                            pokemon['time_till_hidden_ms'] > 900000
                        )
                        if invalid_time:
                            continue
                        pokemons.append(
                            self.normalize_pokemon(
                                pokemon, map_cell['current_timestamp_ms']
                            )
                        )
                    for fort in map_cell.get('forts', []):
                        if not fort.get('enabled'):
                            continue
                        if fort.get('type') == 1:  # probably pokestops
                            continue
                        forts.append(self.normalize_fort(fort))
            for raw_pokemon in pokemons:
                db.add_sighting(session, raw_pokemon)
                self.seen_per_cycle += 1
                self.total_seen += 1
            session.commit()
            for raw_fort in forts:
                db.add_fort_sighting(session, raw_fort)
            # Commit is not necessary here, it's done by add_fort_sighting
            logger.info(
                'Point processed, %d Pokemons and %d forts seen!',
                len(pokemons),
                len(forts),
            )
            # Clear error code and let know that there are Pokemon
            if self.error_code and self.seen_per_cycle:
                self.error_code = None
            self.step += 1
            time.sleep(
                random.uniform(config.SCAN_DELAY, config.SCAN_DELAY + 2)
            )
        session.close()
        if self.seen_per_cycle == 0:
            self.error_code = 'NO POKEMON'

    @staticmethod
    def normalize_pokemon(raw, now):
        """Normalizes data coming from API into something acceptable by db"""
        return {
            'encounter_id': raw['encounter_id'],
            'spawn_id': raw['spawn_point_id'],
            'pokemon_id': raw['pokemon_data']['pokemon_id'],
            'expire_timestamp': (now + raw['time_till_hidden_ms']) / 1000.0,
            'lat': raw['latitude'],
            'lon': raw['longitude'],
        }

    @staticmethod
    def normalize_fort(raw):
        return {
            'external_id': raw['id'],
            'lat': raw['latitude'],
            'lon': raw['longitude'],
            'team': raw.get('owned_by_team', 0),
            'prestige': raw.get('gym_points', 0),
            'guard_pokemon_id': raw.get('guard_pokemon_id', 0),
            'last_modified': raw['last_modified_timestamp_ms'] / 1000.0,
        }

    @property
    def status(self):
        """Returns status message to be displayed in status screen"""
        if self.error_code:
            msg = self.error_code
        else:
            msg = 'C{cycle},P{seen},{progress:.0f}%'.format(
                cycle=self.cycle,
                seen=self.seen_per_cycle,
                progress=(self.step / float(self.count_points) * 100)
            )
        return '[W{worker_no}: {msg}]'.format(
            worker_no=self.worker_no,
            msg=msg
        )

    def restart(self, sleep_min=5, sleep_max=20):
        """Sleeps for a bit, then restarts"""
        time.sleep(random.randint(sleep_min, sleep_max))
        start_worker(self.worker_no, self.points)

    def kill(self):
        """Marks worker as not running

        It should stop any operation as soon as possible and restart itself.
        """
        self.error_code = 'KILLED'
        self.running = False

    def disable(self):
        """Marks worker as disabled"""
        self.error_code = 'DISABLED'
        self.running = False


def get_status_message(workers, count, start_time, points_stats):
    messages = [workers[i].status.ljust(20) for i in range(count)]
    running_for = datetime.now() - start_time
    output = [
        'PokeMiner\trunning for {}'.format(running_for),
        '{len} workers, each visiting ~{avg} points per cycle '
        '(min: {min}, max: {max})'.format(
            len=len(workers),
            avg=points_stats['avg'],
            min=points_stats['min'],
            max=points_stats['max'],
        ),
        '',
        '{} threads active'.format(threading.active_count()),
        '',
    ]
    previous = 0
    for i in range(4, count + 4, 4):
        output.append('\t'.join(messages[previous:i]))
        previous = i
    return '\n'.join(output)


def start_worker(worker_no, points):
    logger.info('Worker (re)starting up!')
    worker = Slave(
        name='worker-%d' % worker_no,
        worker_no=worker_no,
        points=points
    )
    if (worker_no not in config.DISABLE_WORKERS):
        worker.daemon = True
        worker.start()
    else:
        worker.disable()
    workers[worker_no] = worker


def spawn_workers(workers, status_bar=True):
    points = utils.get_points_per_worker()
    start_date = datetime.now()
    count = config.GRID[0] * config.GRID[1]
    for worker_no in range(count):
        start_worker(worker_no, points[worker_no])
    lenghts = [len(p) for p in points]
    points_stats = {
        'max': max(lenghts),
        'min': min(lenghts),
        'avg': sum(lenghts) / float(len(lenghts)),
    }
    last_cleaned_cache = time.time()
    last_workers_checked = time.time()
    workers_check = [
        (worker, worker.total_seen) for worker in workers.values()
        if worker.running
    ]
    while True:
        now = time.time()
        # Clean cache
        if now - last_cleaned_cache > (15 * 60):  # clean cache
            db.SIGHTING_CACHE.clean_expired()
            last_cleaned_cache = now
        # Check up on workers
        if now - last_workers_checked > (5 * 60):
            # Kill those not doing anything
            for worker, total_seen in workers_check:
                if not worker.running:
                    continue
                if worker.total_seen <= total_seen:
                    worker.kill()
            # Prepare new list
            workers_check = [
                (worker, worker.total_seen) for worker in workers.values()
            ]
            last_workers_checked = now
        if status_bar:
            if sys.platform == 'win32':
                _ = os.system('cls')
            else:
                _ = os.system('clear')
            print(get_status_message(workers, count, start_date, points_stats))
        time.sleep(0.5)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--no-status-bar',
        dest='status_bar',
        help='Log to console instead of displaying status bar',
        action='store_false',
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default=logging.INFO
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    if args.status_bar:
        configure_logger(filename='worker.log')
        logger.info('-' * 30)
        logger.info('Starting up!')
    else:
        configure_logger(filename=None)
    logger.setLevel(args.log_level)
    spawn_workers(workers, status_bar=args.status_bar)
