from obspy.core import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.core.event import Event, Origin
from obspy.core.trace import Trace
from obspy.core.stream import Stream
from obspy.core.inventory.inventory import Inventory
import warnings
import argparse
import os
import math

ARC_CLIENT = 'http://service.geonet.org.nz'
NRT_CLIENT = 'http://service-nrt.geonet.org.nz'
MAX_STATIONS = 30
MAX_RADIUS_DEFAULT = 0.1

station_limit_disabled = False
client = Client(NRT_CLIENT)

def lat_lng_dist(coord1: tuple, coord2: tuple) -> float:
    """
    Gets the distance between two sets of coordinates. Coordinates should be
    tuples in the format (lat, lng)
    """
    # I'm not desperate enough to do a bunch of maths when there's a lovely
    # answer on SO already:
    # https://stackoverflow.com/questions/19412462/getting-distance-between-two-points-based-on-latitude-longitude

    # approximate radius of earth in m
    R = 6.3781e6

    lat1 = math.radians(coord1[0])
    lon1 = math.radians(coord1[1])
    lat2 = math.radians(coord2[0])
    lon2 = math.radians(coord2[1])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

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
                waveforms = client.get_waveforms(nw.code, station.code,
                                                 location, channel, starttime, endtime)

                # Required for section plot. Has no ill effect on other plots so
                # we just calculate it for everything. If we don't have a lat
                # and lng it doesn't make sense to calculate a distance so we
                # just set it to 0. 
                # 
                # TODO: replace this with disallowing section plot for stn selection?
                if lat is not None and lng is not None:
                    for trace in waveforms:
                        d = lat_lng_dist((lat, lng), (station.latitude, station.longitude))
                        trace.stats['distance'] = d
                else:
                    for trace in waveforms:
                        trace.stats['distance'] = 0

                st += waveforms
                station_info += str(station) + '\n'
            except Exception as e:
                # Do something here?
                print('Exception: ' + str(e))
                pass
    print(station_info)
    return st


def get_waveforms_for_event(eventid: str, begin_off=10, end_off=60, channel='HNZ', maxradius=MAX_RADIUS_DEFAULT, station=None) -> tuple:
    """
    Get waveforms for an event within a given radius (default MAX_RADIUS_DEFAULT), and on any
    given channels. 

    Behaves the same as get_waveforms_for_time in terms of maxradius/station
    (e.g. set either of them but not both unless you know what you're doing. the
    unset one should be None)

    Returns a tuple of Stream, Event
    """
    cat = client.get_events(eventid=eventid)

    # Should have one and only one event associated with a given eventid
    assert len(cat) == 1, 'Length of returned catalog for event should be 1'

    event: Event = cat[0]
    origin: Origin = event.origins[0]
    otime: UTCDateTime = origin.time

    return (get_waveforms_for_time(origin.latitude, origin.longitude,
                                   otime - begin_off, otime + end_off, channel, maxradius=maxradius, station=station), cat[0])


def build_parser_common(parser):
    # Selection type, either we select what waveforms to save/view based on time
    # or a given event ID.

    seltype = parser.add_subparsers(
        help='Selection Type', required=True, dest='selection_type')

    # Event based parsing logic
    event_parser = seltype.add_parser('event', help='Event based')
    event_parser.add_argument(
        metavar='id', dest='event_id', type=str, help='Event ID, e.g. 2021p001797')
    mx_grp = event_parser.add_mutually_exclusive_group()
    mx_grp.add_argument('--max-radius', '-r', metavar='R',
                        type=float, help='Maximum radius', default=MAX_RADIUS_DEFAULT)
    mx_grp.add_argument('--station', '-s', type=str,
                        help='Station(s) to use, comma separate multiple stations')

    # Time based parsing logic
    time_parser = seltype.add_parser('time', help='Datetime based')
    time_parser.add_argument('datetime', type=UTCDateTime,
                             help='The date and time of the event, e.g. 2021-01-01T15:57:51Z')

    loc_type = time_parser.add_subparsers(
        help='Location type', required=True, dest='loc_type')

    loc_parser = loc_type.add_parser('at', help='Location based')
    loc_parser.add_argument('lat', type=str, help='Latitude')
    loc_parser.add_argument('lng', type=str, help='Longitude')
    loc_parser.add_argument('--max-radius', '-r', metavar='R',
                            type=float, help='Maximum radius', default=MAX_RADIUS_DEFAULT)

    stn_parser = loc_type.add_parser('stn', help='Station based')
    stn_parser.add_argument('station', type=str)

    parser.add_argument('--begin-offset', '-b', type=float,
                        help='Beginning offset in seconds from event start', default=10)
    parser.add_argument('--end-offset', '-e', type=float,
                        help='End offset in seconds from event start', default=60)
    parser.add_argument('--channel', '-c', type=str,
                        help='Channel(s) to use, comma separate multiple channels. Use ? as a wildcard', default='HNZ')

    parser.add_argument('--ignore-max-stations', action='store_true',
                        default=False, help='(Dangerous!) Ignore the max station limit')


parser = argparse.ArgumentParser(description='GeoNet CLI')

action = parser.add_subparsers(help='Action', required=True, dest='action')

save_waveform = action.add_parser('save-waveform', help='Save a waveform')

save_waveform.add_argument('--format', '-f', type=str,
                           choices=['wav', 'mseed'], default='wav', help='Output file format')

out_mxgrp = save_waveform.add_mutually_exclusive_group()
out_mxgrp.add_argument('--out-dir', '-o', type=str,
                       help='Output directory (created if non-existent)')
out_mxgrp.add_argument('--auto-name', '-a', action='store_true', default=False,
                       help='Automatically create a directory from time or event name')
build_parser_common(save_waveform)


plot = action.add_parser('plot', help='Plot waveforms')
plot.add_argument('--type', '-t', dest='plot_type', type=str, choices=['relative', 'section'], default='relative', help='Type of plot')
build_parser_common(plot)

save_stream = action.add_parser('save-stream', help='Save the stream')
save_stream.add_argument('--format', '-f', type=str, choices=['AH', 'GSE2', 'MSEED', 'PICKLE', 'Q', 'SAC', 'SACXY',
                                                    'SEGY', 'SH_ASC', 'SLIST', 'SU', 'TSPAIR', 'WAV'], 
                         default='MSEED', help='Output file format')
save_stream.add_argument('filename', type=str, help='Output filename')
build_parser_common(save_stream)

args = parser.parse_args()

station_limit_disabled = args.ignore_max_stations
# station_limit_disabled = True

stream = None
lat = None
lng = None
time = None
if args.selection_type == 'event':
    ev: Event
    stream: Stream
    stream, ev = get_waveforms_for_event(
        args.event_id,
        args.begin_offset,
        args.end_offset,
        args.channel,
        args.max_radius if args.station is None else None,
        args.station
    )
    lat = ev.origins[0].latitude
    lng = ev.origins[0].longitude
    time = ev.origins[0].time
elif args.selection_type == 'time':
    lat = None if 'lat' not in args else args.lat
    lng = None if 'lng' not in args else args.lng
    stream = get_waveforms_for_time(
        float(lat),
        float(lng),
        args.datetime - args.begin_offset,
        args.datetime + args.end_offset,
        args.channel,
        None if 'max_radius' not in args else args.max_radius,
        station=None if 'station' not in args else args.station
    )
    time = args.datetime


if args.action == 'save-waveform':
    if args.auto_name:
        dir_prefix = 'EV-' + \
            args.event_id if args.selection_type == 'event' else 'EV-' + args.datetime
        dir_prefix += '/'
    else:
        dir_prefix = '' if args.out_dir is None else args.out_dir + '/'

    os.makedirs(dir_prefix, exist_ok=True)
    for trace in stream:
        print(trace)
        trace.write(dir_prefix + trace.id + '.' +
                    args.format, format=args.format.upper())
elif args.action == 'plot':
    if args.plot_type == 'relative':
        stream.plot(type='relative', reftime=time)
    elif args.plot_type == 'section':
        stream.plot(type='section', norm_method='stream', time_down=True, reftime=time)
elif args.action == 'save-stream':
    stream.write(stream[0].id + '.' + args.format.lower(), format=args.format)
