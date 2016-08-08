from datetime import datetime, timedelta
import time

from flask import Flask, render_template

from names import POKEMON_NAMES
from web import get_args  # pretty handy function, actually
import config
import db
import utils
from decimal import *


app = Flask(__name__, template_folder='templates')


CACHE = {
    'data': None,
    'generated_at': None,
}


def get_stats():
    cache_valid = (
        CACHE['data'] and
        CACHE['generated_at'] > datetime.now() - timedelta(minutes=15)
    )
    if cache_valid:
        return CACHE['data']
    session = db.Session()
    forts = db.get_forts(session)
    session.close()
    count = {t.value: 0 for t in db.Team}
    strongest = {t.value: None for t in db.Team}
    guardians = {t.value: {} for t in db.Team}
    top_guardians = {t.value: None for t in db.Team}
    prestige = {t.value: 0 for t in db.Team}
    percentages = {}
    prestige_percent = {}
    total_prestige = 0
    last_date = 0
    for fort in forts:
        if fort['last_modified'] > last_date:
            last_date = fort['last_modified']
        team = fort['team']
        count[team] = count[team] + 1
        if team != 0:
            # Strongest gym
            existing = strongest[team]
            should_replace = (
                existing is not None and
                fort['prestige'] > existing[0] or
                existing is None
            )
            pokemon_id = fort['guard_pokemon_id']
            if should_replace:
                strongest[team] = (
                    fort['prestige'],
                    pokemon_id,
                    POKEMON_NAMES[pokemon_id],
                )
            # Guardians
            guardian_value = guardians[team].get(pokemon_id, 0)
            guardians[team][pokemon_id] = guardian_value + 1
            # Prestige
            prestige[team] += fort['prestige']
    total_prestige = sum(prestige.values())
    for team in db.Team:
        percentages[team.value] = (
            Decimal(count.get(team.value)) / Decimal(len(forts)) * 100
            )
        prestige_percent[team.value] = (
            Decimal(prestige.get(team.value)) / Decimal(total_prestige) * 100
        )
        if guardians[team.value]:
            pokemon_id = sorted(
                guardians[team.value],
                key=guardians[team.value].__getitem__,
                reverse=True
            )[0]
            top_guardians[team.value] = POKEMON_NAMES[pokemon_id]
    CACHE['generated_at'] = datetime.now()
    CACHE['data'] = {
        'order': sorted(count, key=count.__getitem__, reverse=True),
        'count': count,
        'total_count': len(forts),
        'strongest': strongest,
        'prestige': prestige,
        'prestige_percent': prestige_percent,
        'percentages': percentages,
        'last_date': last_date,
        'top_guardians': top_guardians,
        'generated_at': CACHE['generated_at'],
    }
    return CACHE['data']


@app.route('/')
def index():
    stats = get_stats()
    team_names = {k.value: k.name.title() for k in db.Team}
    styles = {1: 'primary', 2: 'danger', 3: 'warning'}
    return render_template(
        'gyms.html',
        area_name=config.AREA_NAME,
        area_size=utils.get_scan_area(),
        minutes_ago=int((datetime.now() - stats['generated_at']).seconds / 60),
        last_date_minutes_ago=int((time.time() - stats['last_date']) / 60),
        team_names=team_names,
        styles=styles,
        **stats
    )


if __name__ == '__main__':
    args = get_args()
    app.run(debug=True, host=args.host, port=args.port)
