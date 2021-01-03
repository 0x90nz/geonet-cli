from obspy.core import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.core.event import Event, Origin
from obspy.core.trace import Trace
from obspy.core.stream import Stream
from obspy.core.inventory.inventory import Inventory
import warnings
import argparse
import os

ARC_CLIENT = 'http://service.geonet.org.nz'
NRT_CLIENT = 'http://service-nrt.geonet.org.nz'
MAX_STATIONS = 30
MAX_RADIUS_DEFAULT = 0.1

station_limit_disabled = False
client = Client(NRT_CLIENT)


def get_waveforms_for_time(lat, lng, starttime, endtime, channel, maxradius, location='*', station=None) -> Stream:
    """
    Get waveforms from stations within a given radius from start time to end
    time (ish, the returned waveforms probably won't start or end exactly when
    asked for).

    Channels can be found here:
    https://www.geonet.org.nz/data/supplementary/channels

    Stations can also be specified (be sure to set maxradius to None, or a large
    value if doing this, as to not exclude the station you're specifying). Use:
    https://www.geonet.org.nz/data/network/sensor/search to find station names.
    Multiple stations can be specified comma separated, e.g. 'WEL,VUWS,WNKS'
    """

    # For whatever reason GeoNet returns version '1' not version '1.0' and obspy
    # throws a fit when it sees this. Just ignore it
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        inv: Inventory = client.get_stations(latitude=lat, longitude=lng, maxradius=maxradius,
                                             channel=channel, level='channel', starttime=starttime, endtime=endtime, station=station)

    # We want to be nice to GeoNet. If we're requesting >30 stations it's likely
    # something might have gone wrong (e.g. maxradius was too big) and we'd end
    # up requesting a ton of data, which is no fun for anyone.
    station_count = sum([len(nw) for nw in inv])
    if station_count > MAX_STATIONS and not station_limit_disabled:
        raise RuntimeError(
            f'Failing because station count exceeded maximum of {MAX_STATIONS} (was {station_count}). Disable station count limit to ignore this')

    st = Stream()
    station_info = ''
    for nw in inv:
        for station in nw:
            try:
                st += client.get_waveforms(nw.code, station.code,
                                           location, channel, starttime, endtime)
                station_info += str(station)
            except:
                # Do something here?
                pass
    return st


def get_waveforms_for_event(eventid: str, begin_off=10, end_off=60, channel='HNZ', maxradius=MAX_RADIUS_DEFAULT, station=None) -> Stream:
    """
    Get waveforms for an event within a given radius (default MAX_RADIUS_DEFAULT), and on any
    given channels. 

    Behaves the same as get_waveforms_for_time in terms of maxradius/station
    (e.g. set either of them but not both unless you know what you're doing. the
    unset one should be None)
    """
    cat = client.get_events(eventid=eventid)

    # Should have one and only one event associated with a given eventid
    assert len(cat) == 1, 'Length of returned catalog for event should be 1'

    event: Event = cat[0]
    origin: Origin = event.origins[0]
    otime: UTCDateTime = origin.time

    return get_waveforms_for_time(origin.latitude, origin.longitude,
                                  otime - begin_off, otime + end_off, channel, maxradius=maxradius, station=station)

def build_parser_common(parser):
    # Selection type, either we select what waveforms to save/view based on time
    # or a given event ID.

    seltype = parser.add_subparsers(help='Selection Type', required=True, dest='selection_type')

    # Event based parsing logic
    event_parser = seltype.add_parser('event', help='Event based')
    event_parser.add_argument(metavar='id', dest='event_id', type=str, help='Event ID, e.g. 2021p001797')
    mx_grp = event_parser.add_mutually_exclusive_group()
    mx_grp.add_argument('--max-radius', '-r', metavar='R', type=float, help='Maximum radius')
    mx_grp.add_argument('--station', '-s', type=str, help='Station(s) to use, comma separate multiple stations')

    # Time based parsing logic
    time_parser = seltype.add_parser('time', help='Datetime based')
    time_parser.add_argument('datetime', type=UTCDateTime, help='The date and time of the event, e.g. 2021-01-01T15:57:51Z')

    loc_type = time_parser.add_subparsers(help='Location type', required=True, dest='loc_type')

    loc_parser = loc_type.add_parser('at', help='Location based')
    loc_parser.add_argument('lat', type=str, help='Latitude')
    loc_parser.add_argument('lng', type=str, help='Longitude')
    loc_parser.add_argument('--max-radius', '-r', metavar='R', type=float, help='Maximum radius', default=MAX_RADIUS_DEFAULT)

    stn_parser = loc_type.add_parser('stn', help='Station based')
    stn_parser.add_argument('station', type=str)

    parser.add_argument('--begin-offset', '-b', type=float, help='Beginning offset in seconds from event start', default=10)
    parser.add_argument('--end-offset', '-e', type=float, help='End offset in seconds from event start', default=60)
    parser.add_argument('--channel', '-c', type=str, help='Channel(s) to use, comma separate multiple channels. Use ? as a wildcard', default='HNZ')

    parser.add_argument('--ignore-max-stations', action='store_true', default=False, help='(Dangerous!) Ignore the max station limit')

parser = argparse.ArgumentParser(description='GeoNet CLI')

action = parser.add_subparsers(help='Action', required=True, dest='action')

save_waveform = action.add_parser('save-waveform', help='Save a waveform')

save_waveform.add_argument('--format', '-f', type=str, choices=['wav', 'mseed'], default='wav', help='Output file format')

out_mxgrp = save_waveform.add_mutually_exclusive_group()
out_mxgrp.add_argument('--out-dir', '-o', type=str, help='Output directory (created if non-existent)')
out_mxgrp.add_argument('--auto-name', '-a', action='store_true', default=False, help='Automatically create a directory from time or event name')
build_parser_common(save_waveform)


plot = action.add_parser('plot', help='Plot waveforms')
build_parser_common(plot)

args = parser.parse_args()

station_limit_disabled = args.ignore_max_stations

stream = None
if args.selection_type == 'event':
    stream = get_waveforms_for_event(
        args.event_id,
        args.begin_offset,
        args.end_offset,
        args.channel,
        args.max_radius if args.station is None else None,
        args.station
    )
elif args.selection_type == 'time':
    stream = get_waveforms_for_time(
        args.lat,
        args.lng,
        args.datetime - args.begin_offset,
        args.datetime + args.end_offset,
        args.channel,
        args.max_radius,
        station=args.station
    )


if args.action == 'save-waveform':
    if args.auto_name:
        dir_prefix = 'EV-' + args.event_id if args.selection_type == 'event' else 'EV-' + args.datetime
        dir_prefix += '/'
    else:
        dir_prefix = '' if args.out_dir is None else args.out_dir + '/'

    os.mkdir(dir_prefix)
    for trace in stream:
        trace.write(dir_prefix + trace.id + '.' + args.format, format=args.format.upper())
elif args.action == 'plot':
    stream.plot()
