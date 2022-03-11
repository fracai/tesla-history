#!/usr/bin/env python

# python3 tesla-csv.py --token /config/token_file.json --history /history/

import argparse
import sys
import os
import json
import datetime
import time
import pytz
import pathlib
import teslapy

def elapsed_time(seconds, suffixes=['y','w','d','h','m','s'], add_s=False, separator=' '):
    """
    Takes an amount of seconds and turns it into a human-readable amount of time.
    """
    # the formatted time string to be returned
    time = []
    # the pieces of time to iterate over (days, hours, minutes, etc)
    # - the first piece in each tuple is the suffix (d, h, w)
    # - the second piece is the length in seconds (a day is 60s * 60m * 24h)
    parts = [(suffixes[0], 60 * 60 * 24 * 7 * 52),
          (suffixes[1], 60 * 60 * 24 * 7),
          (suffixes[2], 60 * 60 * 24),
          (suffixes[3], 60 * 60),
          (suffixes[4], 60),
          (suffixes[5], 1)]
    # for each time piece, grab the value and remaining seconds, and add it to
    # the time string
    for suffix, length in parts:
        value = seconds / length
        floored = int(value)
        if floored > 0:
            seconds = seconds % length
            time.append('%d%s' % (floored,
                           (suffix, (suffix, suffix + 's')[floored > 1])[add_s]))
        if seconds < 1:
            break
    return separator.join(time)

parser = argparse.ArgumentParser(description='Tesla Powerwall/Solar stats retrieval')
parser.add_argument('--config', help='configuration json' )
parser.add_argument('--history', help='history base path' )
args = parser.parse_args()

config = None
with open(args.config, 'r') as config_file:
    config = json.load(config_file)

if not config:
    print ("configuration not loaded")
    sys.exit()

with teslapy.Tesla(config['user']) as tesla:
    if not tesla.authorized:
        tesla.refresh_token(refresh_token=config['refresh_token'])
    tz_eastern = pytz.timezone(config['timezone'])
    tz_utc = pytz.utc
    
    battery_list = tesla.battery_list()
    solar_list = tesla.solar_list()
    
    for battery in tesla.battery_list():
        dir_name = '_{}/'.format(battery['energy_site_id'])
        file_name = 'backup.json'
        out_path = os.path.join(args.history, dir_name, file_name)
        backup_data = battery.get_history_data(kind='backup')
        if backup_data:
            pathlib.Path(os.path.join(args.history, dir_name)).mkdir(parents=True, exist_ok=True)
            with open (out_path, 'w') as json_file:
                print ('backup -> {}'.format(out_path))
                json.dump(backup_data, json_file, indent=4)
            for event in backup_data['events']:
                event['length'] = elapsed_time(
                    event['duration'] / 1000,
                    [' year',' week',' day',' hour',' minute',' second'],
                    add_s=True,
                    separator=', ')
                ts = datetime.datetime.strptime(event['timestamp'], '%Y-%m-%dT%H:%M:%S%z')
                backup_dir = os.path.join(
                    args.history,
                    dir_name,
                    'backup',
                    ts.strftime('%Y'))
                pathlib.Path(backup_dir).mkdir(parents=True, exist_ok=True)
                file_name = '{}.json'.format(ts.strftime('%Y%m%d %H%M%S %z'))
                out_path = os.path.join(args.history, backup_dir, file_name)
                if os.path.exists(out_path):
                    continue
                with open (out_path, 'w') as json_file:
                    print ('backup -> {}'.format(out_path))
                    json.dump(event, json_file, indent=4)
        time.sleep(1)

    cur_date = datetime.datetime.today().replace(
        hour=0, minute=0, second=0, microsecond=0)

    # set a different start date
    #cur_date = datetime.datetime(2021,7,7)

    remaining_sites = []
    remaining_sites.extend(battery_list)
    remaining_sites.extend(solar_list)

    while True:
        if not remaining_sites:
            break
        # set the end date to 1 second before midnight
        end_date = cur_date
        end_date -= datetime.timedelta(seconds=1)
        print (end_date)
        file_name = '{}.json'.format(end_date.strftime('%F'))
        for site in remaining_sites[:]:
            id = site['energy_site_id']
            print ('id:', id)
            dir_name = '_{}/{}'.format(id, end_date.strftime('%Y/%Y-%m/'))
            iso_end_date = tz_eastern.localize(end_date).astimezone(tz_utc).isoformat()
            out_path = os.path.join(args.history, dir_name, file_name)
            if os.path.exists(out_path):
                # if the current file already exists, assume this site is fully retrieved and drop it from the list
                remaining_sites.remove(site)
                continue
            print ('dt: ', iso_end_date)
            print ('{} -> {}/{}'.format(cur_date.isoformat(), dir_name, file_name))
            cal_data = None
            try:
                # get the site data
                cal_data = site.get_calendar_history_data(
                    kind='power',
                    end_date=iso_end_date
                )
            except Exception as e:
                print (e)
                continue
            if not cal_data or not len(cal_data['time_series']):
                continue
            #print (json.dumps(cal_data, indent=2))
            print ('sn:', cal_data['serial_number'])
            print ('ct:', len(cal_data['time_series']))
            #print (json.dumps(cal_data['time_series'][-1], indent=2))
            pathlib.Path(os.path.join(args.history, dir_name)).mkdir(parents=True, exist_ok=True)
            with open (out_path, 'w') as json_file:
                json.dump(cal_data, json_file, indent=4)
            time.sleep(1)
        # move backwards one day
        cur_date -= datetime.timedelta(days=1)
