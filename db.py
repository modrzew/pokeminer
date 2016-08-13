from datetime import datetime
import enum
import time

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship


try:
    import config
    DB_ENGINE = config.DB_ENGINE
except (ImportError, AttributeError):
    DB_ENGINE = 'sqlite:///db.sqlite'


class Team(enum.Enum):
    none = 0
    mystic = 1
    valor = 2
    instict = 3


def get_engine():
    return create_engine(DB_ENGINE)


def get_engine_name(session):
    return session.connection().engine.name


Base = declarative_base()


class SightingCache(object):
    """Simple cache for storing actual sightings

    It's used in order not to make as many queries to the database.
    It's also capable of purging old entries.
    """
    def __init__(self):
        self.store = {}

    @staticmethod
    def _make_key(sighting):
        return (
            sighting['pokemon_id'],
            sighting['spawn_id'],
            normalize_timestamp(sighting['expire_timestamp']),
            sighting['lat'],
            sighting['lon'],
        )

    def add(self, sighting):
        self.store[self._make_key(sighting)] = sighting['expire_timestamp']

    def __contains__(self, raw_sighting):
        expire_timestamp = self.store.get(self._make_key(raw_sighting))
        if not expire_timestamp:
            return False
        timestamp_in_range = (
            expire_timestamp > raw_sighting['expire_timestamp'] - 5 and
            expire_timestamp < raw_sighting['expire_timestamp'] + 5
        )
        return timestamp_in_range

    def clean_expired(self):
        to_remove = []
        for key, timestamp in self.store.items():
            if timestamp < time.time() - 120:
                to_remove.append(key)
        for key in to_remove:
            del self.store[key]


class FortCache(object):
    """Simple cache for storing fort sightings"""
    def __init__(self):
        self.store = {}

    @staticmethod
    def _make_key(fort_sighting):
        return fort_sighting['external_id']

    def add(self, sighting):
        self.store[self._make_key(sighting)] = (
            sighting['team'],
            sighting['prestige'],
            sighting['guard_pokemon_id'],
        )

    def __contains__(self, sighting):
        params = self.store.get(self._make_key(sighting))
        if not params:
            return False
        is_the_same = (
            params[0] == sighting['team'] and
            params[1] == sighting['prestige'] and
            params[2] == sighting['guard_pokemon_id']
        )
        return is_the_same

SIGHTING_CACHE = SightingCache()
FORT_CACHE = FortCache()


class Sighting(Base):
    __tablename__ = 'sightings'

    id = Column(Integer, primary_key=True)
    pokemon_id = Column(Integer)
    spawn_id = Column(String(32))
    expire_timestamp = Column(Integer, index=True)
    encounter_id = Column(String(32))
    normalized_timestamp = Column(Integer)
    lat = Column(String(20), index=True)
    lon = Column(String(20), index=True)


class Fort(Base):
    __tablename__ = 'forts'

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64), unique=True)
    lat = Column(String(20), index=True)
    lon = Column(String(20), index=True)

    sightings = relationship(
        'FortSighting',
        backref='fort',
        order_by='FortSighting.last_modified'
    )


class FortSighting(Base):
    __tablename__ = 'fort_sightings'

    id = Column(Integer, primary_key=True)
    fort_id = Column(Integer, ForeignKey('forts.id'))
    last_modified = Column(Integer)
    team = Column(Integer)
    prestige = Column(Integer)
    guard_pokemon_id = Column(Integer)

    __table_args__ = (
        UniqueConstraint(
            'fort_id',
            'last_modified',
            name='fort_id_last_modified_unique'
        ),
    )


Session = sessionmaker(bind=get_engine())


def normalize_timestamp(timestamp):
    return int(float(timestamp) / 120.0) * 120


def get_since():
    """Returns 'since' timestamp that should be used for filtering"""
    return time.mktime(config.REPORT_SINCE.timetuple())


def get_since_query_part(where=True):
    """Returns WHERE part of query filtering records before set date"""
    if config.REPORT_SINCE:
        return '{noun} expire_timestamp > {since}'.format(
            noun='WHERE' if where else 'AND',
            since=get_since(),
        )
    return ''


def add_sighting(session, pokemon):
    # Check if there isn't the same entry already
    if pokemon in SIGHTING_CACHE:
        return
    existing = session.query(Sighting) \
        .filter(Sighting.pokemon_id == pokemon['pokemon_id']) \
        .filter(Sighting.spawn_id == pokemon['spawn_id']) \
        .filter(Sighting.expire_timestamp > pokemon['expire_timestamp'] - 10) \
        .filter(Sighting.expire_timestamp < pokemon['expire_timestamp'] + 10) \
        .filter(Sighting.lat == pokemon['lat']) \
        .filter(Sighting.lon == pokemon['lon']) \
        .first()
    if existing:
        return
    obj = Sighting(
        pokemon_id=pokemon['pokemon_id'],
        spawn_id=pokemon['spawn_id'],
        encounter_id=str(pokemon['encounter_id']),
        expire_timestamp=pokemon['expire_timestamp'],
        normalized_timestamp=normalize_timestamp(pokemon['expire_timestamp']),
        lat=pokemon['lat'],
        lon=pokemon['lon'],
    )
    session.add(obj)
    SIGHTING_CACHE.add(pokemon)


def add_fort_sighting(session, raw_fort):
    if raw_fort in FORT_CACHE:
        return
    # Check if fort exists
    fort = session.query(Fort) \
        .filter(Fort.external_id == raw_fort['external_id']) \
        .filter(Fort.lat == raw_fort['lat']) \
        .filter(Fort.lon == raw_fort['lon']) \
        .first()
    if not fort:
        fort = Fort(
            external_id=raw_fort['external_id'],
            lat=raw_fort['lat'],
            lon=raw_fort['lon'],
        )
        session.add(fort)
    if fort.id:
        existing = session.query(FortSighting) \
            .filter(FortSighting.fort_id == fort.id) \
            .filter(FortSighting.team == raw_fort['team']) \
            .filter(FortSighting.prestige == raw_fort['prestige']) \
            .filter(FortSighting.guard_pokemon_id ==
                    raw_fort['guard_pokemon_id']) \
            .first()
        if existing:
            # Why it's not in cache? It should be there!
            FORT_CACHE.add(raw_fort)
            return
    obj = FortSighting(
        fort=fort,
        team=raw_fort['team'],
        prestige=raw_fort['prestige'],
        guard_pokemon_id=raw_fort['guard_pokemon_id'],
        last_modified=raw_fort['last_modified'],
    )
    session.add(obj)
    try:
        session.commit()
    except IntegrityError:  # skip adding fort this time
        session.rollback()
    else:
        FORT_CACHE.add(raw_fort)


def get_sightings(session):
    return session.query(Sighting) \
        .filter(Sighting.expire_timestamp > time.time()) \
        .all()


def get_forts(session):
    query = session.execute('''
		SELECT
			fs.fort_id,
			fs.id,
			fs.team,
			fs.prestige,
			fs.guard_pokemon_id,
			fs.last_modified,
			f.lat,
			f.lon
		FROM
			(SELECT 
				fort_id, 
				MAX(last_modified) AS last_modified
			FROM
				fort_sightings
			GROUP BY
				fort_id) AS fmax,
			fort_sightings AS fs,
			forts AS f
		WHERE 
			fs.fort_id = fmax.fort_id AND
			f.id = fmax.fort_id AND
			fs.last_modified = fmax.last_modified
		GROUP BY
			fort_id
		;
    ''')
    return query.fetchall()


def get_session_stats(session):
    query = '''
        SELECT
            MIN(expire_timestamp) ts_min,
            MAX(expire_timestamp) ts_max,
            COUNT(*)
        FROM `sightings`
        {report_since}
    '''
    min_max_query = session.execute(query.format(
        report_since=get_since_query_part()
    ))
    min_max_result = min_max_query.first()
    length_hours = (min_max_result[1] - min_max_result[0]) // 3600
    if length_hours == 0:
        length_hours = 1
    # Convert to datetime
    return {
        'start': datetime.fromtimestamp(min_max_result[0]),
        'end': datetime.fromtimestamp(min_max_result[1]),
        'count': min_max_result[2],
        'length_hours': length_hours,
        'per_hour': min_max_result[2] / length_hours,
    }


def get_punch_card(session):
    if get_engine_name(session) == 'sqlite':
        bigint = 'BIGINT'
    else:
        bigint = 'UNSIGNED'
    query = session.execute('''
        SELECT
            CAST((expire_timestamp / 300) AS {bigint}) ts_date,
            COUNT(*) how_many
        FROM `sightings`
        {report_since}
        GROUP BY ts_date
        ORDER BY ts_date
    '''.format(bigint=bigint, report_since=get_since_query_part()))
    results = query.fetchall()
    results_dict = {r[0]: r[1] for r in results}
    filled = []
    for row_no, i in enumerate(range(int(results[0][0]), int(results[-1][0]))):
        item = results_dict.get(i)
        filled.append((row_no, item if item else 0))
    return filled


def get_top_pokemon(session, count=30, order='DESC'):
    query = session.execute('''
        SELECT
            pokemon_id,
            COUNT(*) how_many
        FROM sightings
        {report_since}
        GROUP BY pokemon_id
        ORDER BY how_many {order}
        LIMIT {count}
    '''.format(order=order, count=count, report_since=get_since_query_part()))
    return query.fetchall()


def get_stage2_pokemon(session):
    result = []
    if not hasattr(config, 'STAGE2'):
        return []
    for pokemon_id in config.STAGE2:
        query = session.query(Sighting) \
            .filter(Sighting.pokemon_id == pokemon_id)
        if config.REPORT_SINCE:
            query = query.filter(Sighting.expire_timestamp > get_since())
        count = query.count()
        if count > 0:
            result.append((pokemon_id, count))
    return result


def get_nonexistent_pokemon(session):
    result = []
    query = session.execute('''
        SELECT DISTINCT pokemon_id FROM sightings
        {report_since}
    '''.format(report_since=get_since_query_part()))
    db_ids = [r[0] for r in query.fetchall()]
    for pokemon_id in range(1, 152):
        if pokemon_id not in db_ids:
            result.append(pokemon_id)
    return result


def get_all_sightings(session, pokemon_ids):
    # TODO: rename this and get_sightings
    query = session.query(Sighting) \
        .filter(Sighting.pokemon_id.in_(pokemon_ids))
    if config.REPORT_SINCE:
        query = query.filter(Sighting.expire_timestamp > get_since())
    return query.all()


def get_spawns_per_hour(session, pokemon_id):
    if get_engine_name(session) == 'sqlite':
        ts_hour = 'STRFTIME("%H", expire_timestamp)'
    else:
        ts_hour = 'HOUR(FROM_UNIXTIME(expire_timestamp))'
    query = session.execute('''
        SELECT
            {ts_hour} AS ts_hour,
            COUNT(*) AS how_many
        FROM sightings
        WHERE pokemon_id = {pokemon_id}
        {report_since}
        GROUP BY ts_hour
        ORDER BY ts_hour
    '''.format(
        pokemon_id=pokemon_id,
        ts_hour=ts_hour,
        report_since=get_since_query_part(where=False)
    ))
    results = []
    for result in query.fetchall():
        results.append((
            {
                'v': [int(result[0]), 30, 0],
                'f': '{}:00 - {}:00'.format(
                    int(result[0]), int(result[0]) + 1
                ),
            },
            result[1]
        ))
    return results


def get_total_spawns_count(session, pokemon_id):
    query = session.execute('''
        SELECT COUNT(id)
        FROM sightings
        WHERE pokemon_id = {pokemon_id}
        {report_since}
    '''.format(
        pokemon_id=pokemon_id,
        report_since=get_since_query_part(where=False)
    ))
    result = query.first()
    return result[0]


def get_all_spawn_coords(session, pokemon_id=None):
    points = session.query(Sighting.lat, Sighting.lon)
    if pokemon_id:
        points = points.filter(Sighting.pokemon_id == int(pokemon_id))
    if config.REPORT_SINCE:
        points = points.filter(Sighting.expire_timestamp > get_since())
    return points.all()
