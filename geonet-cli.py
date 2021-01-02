from obspy.core import UTCDateTime
from obspy.clients.fdsn import Client
from obspy.core.event import Event
from obspy.core.trace import Trace
from obspy.core.stream import Stream

ARC_CLIENT = 'http://service.geonet.org.nz'
NRT_CLIENT = 'http://service-nrt.geonet.org.nz'

# https://www.geonet.org.nz/data/supplementary/channels
CHANNEL = 'HN?'

client = Client(NRT_CLIENT)

start_time = UTCDateTime('2020-12-30T12:10:38.000')

cat = client.get_events(eventid='2021p001797')

# Should have one and only one event associated with a given eventid
assert(len(cat) == 1)

event: Event = cat[0]
origin = event.origins[0]
otime = origin.time

inv = client.get_stations(latitude=origin.latitude, longitude=origin.longitude,
                          maxradius=0.1, channel=CHANNEL, level='channel', starttime=otime-10, endtime=otime+60)

st = Stream()
for network in inv:
    for station in network:
        print(station)
        try:
            st += client.get_waveforms(network.code, station.code, '*', CHANNEL, otime-10, otime+60)
        except:
            pass

print(st)

for tr in st:
    tr.write(tr.id + '.wav', format='WAV')
st.plot()
