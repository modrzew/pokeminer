import discord
from discord.ext import commands
import asyncio
import signal
import sys
import time
from geopy.geocoders import GoogleV3
import json

import config
import db
from names import POKEMON_NAMES
from messages import DISCORD_MESSAGES

# Check whether config has all necessary attributes
REQUIRED_SETTINGS = (
    'DISCORD_APP_ID',
    'DISCORD_TOKEN',
    'DISCORD_CHANNELS',
    'DISCORD_UPDATE_INTERVAL',
    'GOOGLE_MAPS_KEY',
)
for setting_name in REQUIRED_SETTINGS:
    if not hasattr(config, setting_name):
        raise RuntimeError('Please set "{}" in config'.format(setting_name))

join_url = "https://discordapp.com/oauth2/authorize?client_id=" + config.DISCORD_APP_ID + "&scope=bot&permissions="

client = commands.Bot(command_prefix='!', description=DISCORD_MESSAGES['bot_desc'])
already_seen = {}
geolocator = GoogleV3(api_key=config.GOOGLE_MAPS_KEY)

icon_path = './static/icons/{}.png'
watchlist_path = 'watchlist.json'
with open(watchlist_path) as json_data:
    watchlist = json.load(json_data)['watchlist'] 

@client.event
async def on_ready():
	print(DISCORD_MESSAGES['ready'][0].format(join_url))
	print(DISCORD_MESSAGES['ready'][1])
	print(DISCORD_MESSAGES['ready'][2].format(count_iterable(client.servers)))
	client.loop.create_task(sightings_update_task())
	for id in config.DISCORD_CHANNELS:
		channel = client.get_channel(id)
		await client.send_message(channel, DISCORD_MESSAGES['ready_msg'])


@client.event
async def on_error(event, *args, **kwargs):
	print(DISCORD_MESSAGES['error'].format(event))

@client.command(description=DISCORD_MESSAGES['cmd_read_desc'], help=DISCORD_MESSAGES['cmd_read_desc'])
async def read(): #Displays all tracked pokemon
    tracked_pokemon = "```\n"
    for id in watchlist:
         tracked_pokemon += '{} {}\n'.format(id, POKEMON_NAMES[id]) 
    tracked_pokemon += "```"
    await client.say(DISCORD_MESSAGES['cmd_read_msg'] + tracked_pokemon)

@client.command(description=DISCORD_MESSAGES['cmd_add_desc'], help=DISCORD_MESSAGES['cmd_add_desc'])
async def add(id: int):
	if id not in watchlist:
		watchlist.append(id)
		with open(watchlist_path, 'w') as json_data:
			json.dump({'watchlist': watchlist}, json_data)
		await client.say(DISCORD_MESSAGES['cmd_add_added'].format(POKEMON_NAMES[id]))
	else:
		await client.say(DISCORD_MESSAGES['cmd_add_already_added'].format(POKEMON_NAMES[id]))

@add.error
async def add_error(error, id):
	await client.say(DISCORD_MESSAGES['cmd_add_usage'])

@client.command(description=DISCORD_MESSAGES['cmd_remove_desc'], help=DISCORD_MESSAGES['cmd_remove_desc'])
async def remove(id: int):
	if id is None:
		await client.say(DISCORD_MESSAGES['cmd_remove_usage'])
	elif id in watchlist:
		watchlist.remove(id)
		with open(watchlist_path, 'w') as json_data:
			json.dump({'watchlist': watchlist}, json_data)
		await client.say(DISCORD_MESSAGES['cmd_remove_removed'].format(POKEMON_NAMES[id]))
	else:
		await client.say(DISCORD_MESSAGES['cmd_remove_no_on_list'].format(POKEMON_NAMES[id]))

@remove.error
async def remove_error(error, id):
	await client.say(DISCORD_MESSAGES['cmd_remove_usage'])

async def check_pokemon():
	session = db.Session()
	pokemons = db.get_sightings(session)
	session.close()

	for sighting in pokemons:
		await process_sighting(sighting)

	remove_stale_sightings()

async def process_sighting(sighting):
	if sighting.pokemon_id in watchlist:
	    if sighting.id not in already_seen.keys():
		    already_seen[sighting.id] = sighting
		    await report_sighting(sighting)

async def report_sighting(sighting):
	name = POKEMON_NAMES[sighting.pokemon_id]
	location = geolocator.reverse('' + sighting.lat + ', ' + sighting.lon, exactly_one=True)
	street = location.address
	disapper_time_diff = ((sighting.expire_timestamp - time.time()) // 60)
	message = DISCORD_MESSAGES['sighting'].format(name, sighting.pokemon_id, street, disapper_time_diff)

	for id in config.DISCORD_CHANNELS:
		channel = client.get_channel(id)
		await client.send_file(channel, icon_path.format(sighting.pokemon_id), content=message)

async def sightings_update_task():
    await client.wait_until_ready()
    while not client.is_closed:
    	await check_pokemon()
    	await asyncio.sleep(60 * config.DISCORD_UPDATE_INTERVAL)

def remove_stale_sightings():
	old_seen = already_seen.copy()
	for key in old_seen:
		if old_seen[key].expire_timestamp < time.time():
			del already_seen[key]

def count_iterable(i):
	return sum(1 for e in i)

client.run(config.DISCORD_TOKEN)