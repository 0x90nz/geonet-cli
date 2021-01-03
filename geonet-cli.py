from obspy.core import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.core.event import Event, Origin
from obspy.core.trace import Trace
from obspy.core.stream import Stream
from obspy.core.inventory.inventory import Inventory
import warnings

ARC_CLIENT = 'http://service.geonet.org.nz'
NRT_CLIENT = 'http://service-nrt.geonet.org.nz'
MAX_STATIONS = 30

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
            f'Failing because station count exceeded maximum of {MAX_STATIONS}. Disable station count limit to ignore this')

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


def get_waveforms_for_event(eventid: str, begin_off=10, end_off=60, channel='HNZ', maxradius=0.1, station=None) -> Stream:
    """
    Get waveforms for an event within a given radius (default 0.1), and on any
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


get_waveforms_for_event('2021p001797').plot()
