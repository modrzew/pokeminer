/*
	Created by Devsome
	thanks to imDevinC https://github.com/ImDevinC/pkgo-discord for the functions
	edited for https://github.com/modrzew/pokeminer
*/
var Discord = require("discord.js");
var request = require("request");

// Loading my Configs
var config = require("./bot/config.json");

var clientBot = new Discord.Client();

var joinUrl = "https://discordapp.com/oauth2/authorize?client_id=" + config.app_id + "&scope=bot&permissions=";

var alreadySeen = [];
var mapUrl = 'http://maps.google.com/maps?&z=10&ll={0}+{1}&q={0}+{1}';

clientBot.on("ready", function () {
	console.log("\n[INFO]\tTo add me visit this url:\n\t" + joinUrl + "\n\n");
	console.log("[INFO]\tReady to begin!");
	console.log("[INFO]\tYou're connected to [ " + clientBot.servers.length + " ] Servers with [" + clientBot.channels.length + "] Channels!");

	clientBot.setPlayingGame( config.games[Math.floor(Math.random() * (config.games.length))] );
});

clientBot.on('disconnected', function() {
	console.log("Disconnted ? Let me reconnect asap...");
	clientBot.loginWithToken(config.token);
});

clientBot.on("error", function (error) {
	console.log("Caught error: " + error);
});

// CMD+C at terminal
process.on("SIGINT", function () {
    console.log("\n Whoa wait, let me logout first...");
	clientBot.logout();
	process.exit(1);
});

function checkPokemon() {
	request('http://' + config.getServer + '/discord', (err, res, body) => {
		if (err) {
			console.log(err);
			return;
		}
		if (200 != res.statusCode) {
			console.log('Invalid response code: ' + res.statusCode);
			return;
		}
		parsePokemon(JSON.parse(body));
	});
}

function parsePokemon(results) {
  if (!Object.keys(results) || Object.keys(results).length < 1) {
    return;
  }
  foundPokemon = [];
  for (pokemon in results) {
		if(config.pokeShow.indexOf(results[pokemon].pokemon_id) >= 0 ) {
			// found
		} else {
			continue; // not found
		}
    foundPokemon.push(results[pokemon].key);
    if (alreadySeen.indexOf(results[pokemon].key) > -1) {
      continue;
    }

    newPokemonSighted(results[pokemon]);
    alreadySeen.push(results[pokemon].key);
  }

  clearStalePokemon(foundPokemon);
}

function clearStalePokemon(pokemons) {
  var oldSeen = alreadySeen;
  for (id in oldSeen) {
    var pokemon = pokemons.indexOf(oldSeen[id]);
    if (pokemon > -1) {
      continue;
    }

    var index = alreadySeen.indexOf(oldSeen[id]);
    alreadySeen.splice(index, 1);
  }
}

function newPokemonSighted(pokemon) {
	var diff = new Date(pokemon.disappear_time * 1000) - Date.now();
  diff = Math.floor(diff / 1000);
  diff = Math.floor(diff / 60);
  min_diff = diff % 60;
  var url = mapUrl.split('{0}').join(pokemon.lat);
  url = url.split('{1}').join(pokemon.lng);
  var message = '**' + pokemon.name + '** sighted, timeleft **' + min_diff + '**minutes ``' + pokemon.lat + ',' + pokemon.lng + '``\n' + url;
  notifyChannels(message)
}

function notifyChannels(message) {
  clientBot.sendMessage(config.channelID, message, {}, (err) => {
    if (err) {
			clientBot.sendMessage(config.channelID, err);
    }
  });
}

/* TOKEN */
clientBot.loginWithToken(config.token, (err, token) => {
	if (err) { console.log(err); setTimeout(() => { process.exit(1); }, 2000); }
	if (!token) { console.log(" WARN " + " failed to connect"); setTimeout(() => { process.exit(0); }, 2000); }
});

/* Changing game playing */
setInterval(() => {
	clientBot.setPlayingGame(config.games[Math.floor(Math.random() * (config.games.length))]);
}, (10 * 1000) * 60); //change playing game every 10 minutes

/* checking for new pokemon */
setInterval(() => {
	checkPokemon();
}, (config.CheckMinutes * 1000) * 10); //checking for Pokemon every two minutes
