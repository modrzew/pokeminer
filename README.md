# pokeminer

Pokemon Go scraper capable of scanning large area for Pokemon spawns over long period of time. Suitable for gathering data for further analysis.

## Oh great, another map?

This is not *a map*. Yeah, map is included, but main goal of this app is to *gather data* and put it in the database for further analysis. There are several other projects (including aforementioned PokemonGo-Map) that do better job at being just a map.

## How does it work?

`worker.py` gets rectangle as a start..end coordinates (configured in `config.py`) and spawns *n* workers. Each of the worker uses different Google/PTC account to scan its surrounding area for Pokemon. To put it simply: **you can scan entire city for Pokemon**. All gathered information is put into a database for further processing (since servers are unstable, accounts may get banned, Pokemon disappear etc.). `worker.py` is fully threaded, waits a bit before rescanning, and logins again after X scans just to make sure connection with server is in good state. It's also capable of restarting workers that are misbehaving, so that data-gathering process is uninterrupted.

There's also  a simple interface for gathered data that displays active Pokemon on a map. It can generate nicely-looking reports, too.

Here it is in action:

![In action!](static/map.png)

And here are workers together with their area of scan:

![In action!](static/map-workers.png)

## Bulletpoint list of features

- multithreaded, multiple accounts at the same time
- aims at being very stable for long-term runs
- able to map entire city (or larger area) in real time
- gathers Pokemon and Gyms
- data gathering for further analysis
- visualization
- reports for gathered data

## Setting up

[/u/gprez](https://www.reddit.com/u/gprez) made [a great tutorial on Reddit](https://www.reddit.com/r/pokemongodev/comments/4tz66s/pokeminer_your_individual_pokemon_locations/d5lovb6). Check it out if you're not accustomed with Python applications.

**Note**: Pokeminer works only with Python 3.5. Python 2.7 is **not supported** and not compatible at all since I moved from threads to coroutines. Seriously, it's 2016, Python 2.7 hasn't been developed for 6 years, why don't you upgrade already?

Create the database by running Python interpreter. Note that if you want more than 10 workers simultaneously running, SQLite is probably not the best choice.

```py
$> python
Python 2.7.10 (default, Jan 13 2016, 14:23:43)
[GCC 4.8.4] on linux2
Type "help", "copyright", "credits" or "license" for more information.
>>> import db
>>> db.Base.metadata.create_all(db.get_engine())
```

Copy `config.py.example` to `config.py` and modify as you wish. See [wiki page](https://github.com/modrzew/pokeminer/wiki/Config) for explanation on properties.

Run the worker:

```
python worker.py
```

Optionally run the live map interface and reporting system:

```
python web.py --host 127.0.0.1 --port 8000
```

### How many workers do I need?

Credits go to [Aiyubi](https://github.com/Aiyubi) that did the original math in [#124](https://github.com/modrzew/pokeminer/issues/124). Thanks!

**tl;dr**: about 1.2 workers per km².

Longer version: there's a set delay between each scan and one spawn lasts for at least 15 minutes, so there's a max PPC (points per cycle) for one worker, otherwise you risk missed spawns. As I'm writing this scan delay is set to 10, so combining it with 15 minutes it gives max of **90 PPC**. You can check that value in worker.py's status window.

And how many workers you need? Let's calculate that for hexagonal grid:

```
overlap_area = (pi - 3/2*sqrt(3) *2) * 2
overlap_correction_factor ~ 1.17
```

Results:

```
numer_of_workers = (pi * radius²) /( pi * 70m²) * 1.17 * 10s / (15*60s) = (radius_in_km)² * 2.65
```

For example, a radius of 5.5km is around 95km² and with the formula above would be ~80 workers.

## Reports

There are three reports, all available as web pages on the same server as live map:

1. Overall report, available at `/report`
2. Single species report, available at `/report/<pokemon_id>`
3. Gym statistics page, available by running `gyms.py`

Here's how the overall report looks like:

[![](http://i.imgur.com/Yy4VTq0m.jpg)](http://i.imgur.com/Yy4VTq0.jpg)

Gyms statistics server is in a separate file, because it's intended to be shared publicly as a webpage - [just as I did for Wrocław](https://pogowroc.modriv.net).

[![](http://i.imgur.com/1098HkEm.png)](http://i.imgur.com/1098HkE.png)

## License

See [LICENSE](LICENSE).

This project was based on an very, very early version of [AHAAAAAAA/PokemonGo-Map](https://github.com/AHAAAAAAA/PokemonGo-Map), which it doesn't share any code with now. Currently it uses [tejado/pgoapi](https://github.com/tejado/pgoapi).
