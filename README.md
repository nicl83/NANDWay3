# NANDWay3
A rewrite of NANDWay in Python 3.

## About
This is a crude re-write of NANDWay - originally a Python 2 script - in Python 3.
It requires Python 3.10 or later and PySerial.

I have written this with Pylint as my guide - I squished bugs until Pylint stopped screaming at me, then I shipped it.
I do NOT have the hardware to do road-tests of this script. It SHOULD match the behaviour of the Python 2 version, however I cannot guarantee it does.
***You use this script at your OWN RISK.*** (Something something thermonuclear war.)

I was asked to upload this to GitHub at 1am about two months after I initially wrote it,
and I believe I was part-way through a more comprehensive PEP8 compliant re-write when I was interrupted by IRL commitments,
so I'm including two versions of the code.

`NANDWay3.py` is the in-progress PEP8 rewrite. It is probably the more unstable of the two.
`NANDWay3_dcord.py` is an older pre-rewrite version. It is likely more stable, but Pylint doesn't like it very much.

I will happily take a look at bug reports, however please remember that I do not have the original hardware.

## Credits
```
# *************************************************************************
# Python 3.x rewrite by nicl83
# *************************************************************************
# Teensy++ 2.0 modifications by Effleurage
#  NANDway.py
#
# Teensy++ 2.0 modifications by judges@eEcho.com
# *************************************************************************
#  noralizer.py - NOR flasher for PS3
#
# Copyright (C) 2010-2011  Hector Martin "marcan" <hector@marcansoft.com>
#
# This code is licensed to you under the terms of the GNU GPL, version 2;
# see file COPYING or http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
# *************************************************************************
```

Original `noralizer` script by @marcan. NANDWay originally by Effleurage. My thanks to @Lazr1026 for using her Wii Us as test dummies for this rewrite.
