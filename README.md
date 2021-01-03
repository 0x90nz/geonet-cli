# geonet-cli

This is a simple command line application which allows collection of data from
the GeoNet FDSN service. It is in no way associated with or endorsed by GeoNet.

_Note:_ while there are a few safeguards in place, this was mostly just written
so I could download things easier than by hand. It is absolutely **not**
"production quality". Use your common sense and please be nice to GeoNet's
servers, don't do stupid things like request terabytes of data.

_Another note:_ I am not a seismologist, or anything even loosely resembling
one. Take anything I say specifically about this field with a 50 kilogram bag of
salt.

## Usage

This script should be able to be run with most recent versions of python 3. It
requires that you have the `obspy` module installed.

At the top level there are "actions", there currently exist `save-waveform`,
`plot` and `save-stream`. Each of these does something.

Below that you need a "selection type", this is how we know what data to
retrieve. Selections can either be events, or times. I much prefer events. You
can find the event by looking up the event on GeoNet and either copying from the
URL (e.g. "https://www.geonet.org.nz/earthquake/2021p001797", copy the
"2021p001797" bit) or the "PublicID" in the "Technical" section.

Time requires a UTC datetime, something of the format "2021-01-01T15:57:51Z" as
well as either a lat/lng pair, or a station ID.

Knowing this we can write a very simple command:

```
python geonet-cli.py plot event 2021p001797
```

This should plot all stations with a `HNZ` channel within 0.1 degrees (the
default value) of the epicentre of the event.

Each part of the command (i.e. the action, selection type etc.) has its own
arguments.

### Useful Arguments

This is a brief(-ish) overview of some useful arguments. For a more complete
look, check the help (`python geonet-cli.py --help`) and the help of specific
actions (e.g. `python geonet-cli.py plot --help`).

Stations can be selected with `--station` (short form `-s`). Multiple stations
can be comma-separated, e.g. `WEL,POLS,UHCS`. This is part of the event
selection type, and also the time selection type.

Channels can be selected with `--channel` (short form `-c`). These can contain
UNIX style wildcards (e.g. `*`, `?`). Find channels for specific sensors
[here](https://www.geonet.org.nz/data/network/sensor/WEL) (change `WEL` to
whatever sensor you're looking at).

The most interesting channels are probably the `HN?` series (strong motion
sensors, i.e. measuring acceleration) and the `HH?` series (weak motion sensors,
i.e. measuring velocity).

The beginning and end offset of the waveform can be adjusted with
`--begin-offset` (short form `-b`) and `--end-offset` (short form `-e`). These
are in seconds, begin offset is subtracted from the time of the event and end
offset it added to it. The defaults are 10 and 60 respectively.

If using automatic station selection, the maximum radius can be specified with
`--max-radius` (short form `-r`). This is in degrees, and should be kept
relatively small if including strong motion sensors as there are a _lot_ of
them. There is a soft limit of 30 on the number of stations to get data for,
mostly in order to catch mistakes. 

If you are sure that you know what you're doing, you can specify
`--ignore-max-stations` which will disable this limit, but this is dangerous, so
you have been warned!

### Saving waveforms

This is primarily what I wrote this utility for. You can save the waveforms of
events in a few different formats. For now I only support `wav` and `mseed`, but
it should be trivial to add more.

_A note on wav files:_ The wav files seem to have a sample rate of 7000Hz, this
is wrong. Most of the sensors sample at something like 200Hz (at least the ones
I'm interested in). 

If you want to use the data properly, you can force Audacity
to import it correctly by importing as "Signed 32-bit PCM", "1 Channel (Mono)"
with a sample rate of whatever your sensor uses (e.g. 200Hz). It's also useful
to skip past the RIFF and WAVE headers.

To save an event to a specific folder, the `--out-dir` (or just `-o`) argument
can be used.

If not specific name for the output folder is required, then `--auto-name` or
`-a` can be used to automatically create a folder name and save to it. This is
either based on the time of the event or the event id, dependent on which is
present.

So, putting this together, we could save all the waveforms for any stations
within 0.1 degrees of the epicentre of the event `2021p001797` with this
command:

```
python geonet-cli.py save-waveform -a event 2021p001797
```

### Plotting

Waveforms can also be plotted for easy visualisation. This can be done with the
`plot` action.

For example, to plot just the WEL station, you could use a command like this:

```
python geonet-cli.py plot event 2021p001797 -s WEL
```

A section plot can also be generated, this is a plot of multiple traces by
distance. For this it doesn't really make sense to use a `stn` mode for a `time`
event, so make sure to use `at` (lat/lng based) for that.

To select the type, use `--type` (short form `-t`):

```
python geonet-cli.py plot -t section event 2021p001797
```

### Saving the Stream

A stream can consist of multiple traces. Each trace is a waveform. The action
`save-stream` can be used to save a stream of all the traces from a given
command. At this moment this command is only really useful for exporting data
for use in another program.

The default format is `MSEED` but this can be changed with the `--format` (short
form `-f`) argument.
