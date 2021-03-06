import asyncio
import threading
import os
import sys
import queue
import schedule
import time
import logging
from datetime import datetime

import util
import discordbot
import api
import weather
import monitoring

class Scheduler():
    def __init__(self, sendqueue, weather, monitoring, logger, loop):
        self.sendqueue = sendqueue
        self.weather = weather
        self.monitoring = monitoring
        self.logger = logger
        self.loop = loop

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.logger.debug('launch scheduler')
        if os.environ.get('MORNING') is not None:
            schedule.every().day.at(os.environ.get('MORNING')).do(self.good_morning)
        if os.environ.get('EVENING') is not None:
            schedule.every().day.at(os.environ.get('EVENING')).do(
                (lambda: self.sendqueue.put({ 'message': '夕ごはんの時間です' })))
        if os.environ.get('CADVISOR') is not None and os.environ.get('CONTAINERS') is not None:
            schedule.every(5).minutes.do(self.monitoring.run, show_all=False)

        while True:
            schedule.run_pending()
            time.sleep(1)

    def good_morning(self):
        self.sendqueue.put({ 'message': 'おはようございます'})
        self.weather.run()

def initlogger():
    logdir = '/logs/discordbot'
    os.makedirs(logdir, exist_ok=True)
    starttime = datetime.now().strftime('%Y%m%d-%H%M')
    logging.getLogger().setLevel(logging.WARNING)
    logger = logging.getLogger('discordbot')
    if os.environ.get('DEBUG'):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logFormatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s',
                                     datefmt='%Y%m%d-%H%S')
    fileHandler = logging.FileHandler('/{}/{}'.format(logdir, starttime))
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)
    return logger, starttime

def main(logger):
    envse = ['DISCORD_TOKEN', 'DISCORD_CHANNEL_NAME', 'DISCORDBOT_TOKEN']
    envsc = ['LOCATION', 'XRAIN_ZOOM', 'MANET',
             'GOOGLE_MAPS_API_KEY', 'DARK_SKY_API_KEY', 'CADVISOR', 'CONTAINERS', 'MORNING', 'EVENING', 'XRAIN_LAT', 'XRAIN_LON', 'PORT']

    f = util.environ(envse, 'error')
    util.environ(envsc, 'warning')
    if f:
        logger.error('error: some environment variables are not set. exiting.')
        sys.exit(1)

    sendqueue = queue.Queue()

    httploop = asyncio.new_event_loop()
    ap = api.API(httploop, sendqueue, logger, os.environ.get('DISCORDBOT_TOKEN'))
    threading.Thread(target=ap.run, name='api', daemon=True).start()

    wea = weather.Weather(sendqueue, logger)
    mon = monitoring.Monitoring(sendqueue, logger)
    scheduleloop = asyncio.new_event_loop()
    sched = Scheduler(sendqueue, wea, mon, logger, scheduleloop)
    threading.Thread(target=sched.run, name='scheduler', daemon=True).start()

    logger.debug('launch discord client')
    client = discordbot.DiscordClient(os.environ.get('DISCORD_CHANNEL_NAME'), sendqueue, wea, mon, logger)
    client.run(os.environ.get('DISCORD_TOKEN'))

if __name__ == '__main__':
    logger, starttime = initlogger()
    logger.info('started discordbot at {0}'.format(starttime))
    main(logger)

