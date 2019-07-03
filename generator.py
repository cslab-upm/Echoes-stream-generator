#!/usr/bin/python

__author__ = "Samuel Lemes Perera @slemesp"

import os
import json
import threading
import subprocess
import shutil

# pip install psutil --user
import psutil
# pip install configparser --user
import configparser

from datetime import datetime
from playlist_generator import PlaylistWorking
from sound_generator import SoundGenerator

# pip install paho-mqtt --user
import paho.mqtt.client as mqtt


import logging
import logging.handlers as handlers

logger = logging.getLogger('echoes_generator')
logger.setLevel(logging.INFO)

LOCAL_PATH = os.path.dirname(os.path.realpath(__file__))

logHandler = handlers.RotatingFileHandler(os.path.join(LOCAL_PATH, 'contadoresdeestrellas_generator.log'), maxBytes=1000000, backupCount=2)
logHandler.setLevel(logging.INFO)
logger.addHandler(logHandler)

#
# def parsePath(path):
#     return os.path.expanduser(os.path.expandvars(os.path.normpath(path)))

# ------------------------------------------------------------------------------

config_ini = configparser.ConfigParser()
config_ini.read(os.path.join(LOCAL_PATH, 'config.py'))

ICECAST_HOST = str(config_ini['ICECAST']['HOST'])
ICECAST_PORT = int(config_ini['ICECAST']['PORT'])
ICECAST_SOURCE_PASS = str(config_ini['ICECAST']['SOURCE_PASS'])

MQTT_HOST = str(config_ini['MQTT']['HOST'])
MQTT_PORT = int(config_ini['MQTT']['PORT'])

LIQUIDSOAP = str(config_ini['LIQUIDSOAP']['PATH'])

# ------------------------------------------------------------------------------

MQTT_TOPIC_STATIONS = "station/echoes/#"
MQTT_TOPIC_SERVER_UP = "server/status/up"


CONFIG_FILE = os.path.join(LOCAL_PATH, '.meteor_radio.ini')  # parsePath("$HOME/.meteor_radio.ini")

config = configparser.ConfigParser()

config['STATIONS'] = {}

config.read(CONFIG_FILE)

config['STREAMING'] = {}
# parsePath("$HOME/meteor-files/default-noise.wav")
config['STREAMING']['noise_file_path'] = os.path.join(LOCAL_PATH, 'assets', 'default-noise.wav')
config['STREAMING']['m3u8_folder_path'] = os.path.join(LOCAL_PATH, 'stations')  # parsePath("$HOME/meteor-files")
config['STREAMING']['time'] = '1'

NOISE_RESOURCES_LEN = 5

NOISE_PLAYLIST = [
    os.path.join(LOCAL_PATH, 'assets', 'noise-000.wav'),  # parsePath("$HOME/meteor-files/noise-000.wav"),
    os.path.join(LOCAL_PATH, 'assets', 'noise-001.wav'),  # parsePath("$HOME/meteor-files/noise-001.wav"),
    os.path.join(LOCAL_PATH, 'assets', 'noise-002.wav'),  # parsePath("$HOME/meteor-files/noise-002.wav"),
    os.path.join(LOCAL_PATH, 'assets', 'noise-003.wav'),  # parsePath("$HOME/meteor-files/noise-003.wav"),
    os.path.join(LOCAL_PATH, 'assets', 'noise-004.wav')  # parsePath("$HOME/meteor-files/noise-004.wav")
]

NOISE_FILENAME_TEMPLATE = 'noise-%03d.wav'


stations_playlist_working = {}


def updateConfigFile():
    logger.info("updateConfigFile")
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)


def registerStation(stationName):
    if stationName not in config['STATIONS']:
        logger.info("Register Station %s" % (stationName))
        config['STATIONS'][stationName] = json.dumps({'register': datetime.utcnow().isoformat()})
        updateConfigFile()
        startStation(stationName)


def registerStationEvent(stationName, data):

    station_info = json.loads(config['STATIONS'][stationName])
    if 'last_event' not in station_info or station_info['last_event'] < data['t'][0]:
        logger.info("Event from Station %s" % (stationName))
        station_info['last_event'] = data['t'][0]
        station_info['last_event_date'] = datetime.fromtimestamp(data['t'][0]).utcnow().isoformat()
        if 'total_events' in station_info:
            station_info['total_events'] = station_info['total_events'] + 1
        else:
            station_info['total_events'] = 1

        config['STATIONS'][stationName] = json.dumps(station_info)
        updateConfigFile()
        addEventToPlaylist(stationName, data)
    else:
        logger.warning("Event from Station %s not valid" % (stationName))


def addEventToPlaylist(stationName, data):

    if stationName in stations_playlist_working and stations_playlist_working[stationName]:
        logger.info("add Event To Playlist %s" % (stationName))

        event_audio_paths = SoundGenerator(seconds_split=config['STREAMING']['time'], noise_dbfs=data['peak_lower']).generate(data['t'], data['s_n'], os.path.join(
            config['STREAMING']['m3u8_folder_path'], stationName))
        for event_audio_path in event_audio_paths:
            stations_playlist_working[stationName].addEvent(event_audio_path)


def on_station_message(client, userdata, msg):

    topic = msg.topic.split('/')
    if topic[2] == 'event':
        registerStation(topic[3])
        registerStationEvent(topic[3], json.loads(str(msg.payload)))
        try:
            generateNoiseResources(topic[3], json.loads(str(msg.payload))['peak_lower'])
        except Exception as e:
            logger.error(e)
            pass

    elif topic[2] == 'register':
        registerStation(str(msg.payload))

    else:
        logger.warning(msg.topic + " " + str(msg.payload))


def listenStations():
    mqtt_client = mqtt.Client()
    # mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_station_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.subscribe(MQTT_TOPIC_STATIONS)
    mqtt_client.loop_forever()


def loadStations():
    for (config_key, config_val) in config.items(u'STATIONS'):
        startStation(config_key)
#
#
# def run_command(command):
#     print(' '.join(command))
#     process = subprocess.Popen(command, stdout=subprocess.PIPE)
#     while True:
#         output = process.stdout.readline()
#         if output == '' and process.poll() is not None:
#             break
#         if output:
#             print output.strip()
#     rc = process.poll()
#     return rc


def generateNoiseResources(stationName, noise_dbfs=12, force=False):
    logger.info("generateNoiseResources %s" % (stationName))
    station_info = json.loads(config['STATIONS'][stationName])
    if not force and 'noise_dbfs' in station_info and station_info['noise_dbfs'] == noise_dbfs:
        return

    station_info['noise_dbfs'] = noise_dbfs
    config['STATIONS'][stationName] = json.dumps(station_info)
    updateConfigFile()

    folder_station = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName)

    event_noise_paths = SoundGenerator(noise_dbfs=12, seconds_split=(1 + int(
        config['STREAMING']['time']) * NOISE_RESOURCES_LEN)).generate([0], [0], folder_station)

    logger.info(event_noise_paths[0])

    cmdLine = ['ffmpeg', '-i', event_noise_paths[0], '-f', 'segment', '-segment_time', '1',
               '-c', 'copy', os.path.join(folder_station, NOISE_FILENAME_TEMPLATE)]
    ffmpeg = subprocess.Popen(cmdLine, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = ffmpeg.communicate()

    if os.path.isfile(event_noise_paths[0]):
        os.remove(event_noise_paths[0])


def generateStationResources(stationName):
    logger.info("generateStationResources: %s " % (stationName))
    folder_station = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName)

    if os.path.exists(folder_station):
        shutil.rmtree(folder_station, ignore_errors=False, onerror=None)

    if not os.path.exists(folder_station):
        os.makedirs(folder_station)
    # else:
    #     print(folder_station)

    liq_file = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName, stationName + '.liq')
    m3u_file = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName, stationName + '.m3u')
    log_file = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName, stationName + '.log')

    generateNoiseResources(stationName, force=True)

    f = open(liq_file, "w+")
    f.write("#!%s\r\n" % (LIQUIDSOAP))
    f.write("set(\"log.file.path\",\"%s\")\r\n" % (log_file))
    f.write("set(\"log.level\",0)\r\n")

    f.write("set(\"audio.converter.samplerate.libsamplerate.quality\",\"best\")\r\n")
    # f.write("set(\"audio.converter.samplerate.preferred\",\"libopus\")\r\n")
    # f.write("set(\"decoder.external.ffmpeg.path\",\"ffmpeg\")\r\n")
    # f.write("set(\"decoder.stream_decoders\",[\"OGG\",\"WAV\"])\r\n")
    # f.write("set(\"decoder.file_decoders\",[\"OGG\",\"WAV\"])\r\n")
    # f.write("set(\"decoder.file_extensions.ffmpeg\",[\"ogg\",\"wav\"])\r\n")
    # f.write("set(\"decoder.mime_types.ogg\",[\"audio/x-opus+ogg\",\"audio/ogg\",\"application/x-ogg\",\"audio/x-ogg\"])\r\n")
    # f.write("set(\"playlists.mime_types.xml\",[\"audio/x-opus+ogg\",\"audio/ogg\",\"application/x-ogg\",\"audio/x-ogg\"])\r\n")
    # f.write("set(\"scheduler.fast_queues\",1)\r\n")

    f.write("myplaylist = playlist(reload_mode=\"watch\",mode=\"normal\",reload=1,mime_type=\"application/x-mpegURL\",default_duration=%f,length=%f,conservative=true,\"%s\")\r\n" %
            (float(config['STREAMING']['time']), float(config['STREAMING']['time']) * NOISE_RESOURCES_LEN, m3u_file))
    f.write("security = single(\"%s\")\r\n" % (config['STREAMING']['noise_file_path']))
    f.write("radio = myplaylist\r\n")

    f.write("radio = fallback(track_sensitive = false, [radio, security])\r\n")
    # f.write("output.icecast(%mp3,\r\n")
    # f.write("output.icecast(%vorbis,\r\n")
    f.write("output.icecast(%opus,\r\n")
    f.write("  host = \"%s\", port = %s,\r\n" % (ICECAST_HOST, ICECAST_PORT))
    f.write("  password = \"%s\", mount = \"%s\",\r\n" % (ICECAST_SOURCE_PASS, stationName))
    f.write("  icy_metadata=\"true\",\r\n")
    f.write("  genre = \"Live\",\r\n")
    f.write("  description = \"Un proyecto para que entre todos ayudemos a contar los meteoros en las lluvias de estrellas.\",\r\n")
    f.write("  name = \"Contadores de Estrellas - %s\",\r\n" % (stationName))
    f.write("  url = \"http://www.contadoresdeestrellas.org\",\r\n")
    f.write("  audio_to_stereo(radio))\r\n")
    f.close()


def startStationStream(stationName):
    logger.info("startStationStream: %s " % (stationName))
    liq_file = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName, stationName + '.liq')

    cmdLine = [LIQUIDSOAP, liq_file]
    if not isRunningCmdLine(cmdLine):
        command1 = subprocess.Popen(cmdLine, shell=False,  stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def startStationPlaylist(stationName):
    if stationName not in stations_playlist_working:
        logger.info("startStationPlaylist: %s " % (stationName))
        m3u_file = os.path.join(config['STREAMING']['m3u8_folder_path'], stationName, stationName + '.m3u')

        station_noise_playlist = []
        for i in range(0, NOISE_RESOURCES_LEN):
            if os.path.isfile(os.path.join(config['STREAMING']['m3u8_folder_path'], stationName, NOISE_FILENAME_TEMPLATE % i)):
                station_noise_playlist.append(os.path.join(
                    config['STREAMING']['m3u8_folder_path'], stationName, NOISE_FILENAME_TEMPLATE % i))

        if len(station_noise_playlist) != NOISE_RESOURCES_LEN:
            station_noise_playlist = NOISE_PLAYLIST

        stations_playlist_working[stationName] = PlaylistWorking(stationName, m3u_file,  station_noise_playlist)
        stations_playlist_working[stationName].start()


def startStation(stationName):
    generateStationResources(stationName)
    startStationStream(stationName)
    startStationPlaylist(stationName)


def serverUp():
    logger.info("serverUp")
    mqtt_client = mqtt.Client()
    # mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    mqtt_client.publish(MQTT_TOPIC_SERVER_UP, True)
    mqtt_client.loop_stop()


def isRunningCmdLine(cmdLine):
    for q in psutil.process_iter():
        if q.cmdline() == cmdLine:
            return True
    return False


def isRunning():
    count = 0
    for q in psutil.process_iter():
        if q.name() == 'python':
            cmdLine = q.cmdline()
            if cmdLine and os.path.basename(__file__) in cmdLine[1]:
                count += 1

    return count > 1


if __name__ == '__main__':

    if isRunning():
        print("Previous Script running. Please kill previous process and execute newly.")
        exit()

    try:
        updateConfigFile()
        serverUp()
        loadStations()
        listenStations()
    except Exception as e:
        logger.error(e)
        raise
