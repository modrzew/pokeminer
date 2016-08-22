import config

EN_MESSAGES = {
	'ready':['[INFO] To add me visit this url: {}', '[INFO] READY to begin!', '[INFO] You are connected to {} servers!'],
	'ready_msg': 'Looking for new Pokemon!',
	'error': 'Caught error: {}',
	'shutdown': 'Let me logout first...',
	'sighting': '**{}** ({}) sighted!\n{}\nDisappearing in {:.0f} minutes.',
	'bot_desc': 'Reports sightings of rare Pokemon',
	'cmd_read_desc': 'Lists all tracked Pokemon',
	'cmd_read_msg': 'These are the tracked Pokemon:\n',
	'cmd_add_desc': 'Adds Pokemon to the watchlist',
	'cmd_add_added': 'Tracking {} now :rainbow:',
	'cmd_add_already_added': '{} is already on the watchlist :warning:',
	'cmd_add_usage': 'Usage: "!add pokemon_id" :point_up:',
	'cmd_remove_desc': 'Removes Pokemon from the Watchlist',
	'cmd_remove_removed': 'Stopped tracking {} :rainbow:',
	'cmd_remove_no_on_list' : '{} Is not being tracked :warning:',
	'cmd_remove_usage': 'Usage: "!remove pokemon_id" :point_up:',
}

DE_MESSAGES = {
	'ready':['[INFO] Um mich hinzuzufügen besuche diese url: {}', '[INFO] BEREIT!', '[INFO] Du bist mit {} servern verbunden!'],
	'ready_msg': 'Auf der Suche nach neuen Pokemon!',
	'error': 'Fehler gefunden: {}',
	'shutdown': 'Logge aus...',
	'sighting': '**{}** ({}) gesichtet!\n{}\nVerschwindet in {:.0f} Minuten.',
	'bot_desc': 'Berichtet über Sichtungen seltener Pokemon',
	'cmd_read_desc': 'Listet alle beobachteten Pokemon auf',
	'cmd_read_msg': 'Dies sind die beobachteten Pokemon:\n',
	'cmd_add_desc': 'Fügt ein Pokemon zu den beobachteten Pokemon hinzu',
	'cmd_add_added': 'Beobachte nun {} :rainbow:',
	'cmd_add_already_added': '{} wird bereits beobachtet :warning:',
	'cmd_add_usage': 'Verwendung: "!add pokemon_id" :point_up:',
	'cmd_remove_desc': 'Entferne ein Pokemon von den beobachteten Pokemon',
	'cmd_remove_removed': 'Beobachte {} nichtmehr :rainbow:',
	'cmd_remove_no_on_list' : '{} Wird nicht beobachtet :warning:',
	'cmd_remove_usage': 'Verwendung: "!remove pokemon_id" :point_up:',
}

DISCORD_MESSAGES = {
    'DE': DE_MESSAGES,
}.get(config.LANGUAGE.upper(), EN_MESSAGES)