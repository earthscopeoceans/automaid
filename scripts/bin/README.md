This directory must contain the executables

`icdf24_v103_test`
`icdf24_v103ec_test`

These two executables are not git tracked because they are system specific and
can be remade by running `make` in $AUTOMAID/scripts/src/V103 and
$AUTOMAID/scripts/src/V103ec.  They must be made in those two respective
directories and copied here.

And when automaid has been run this directory will additionally (briefly, before
being deleted to clear the cache for the next seismogram) contain

`wtcoeffs`
`wtcoeffs.icdf24_5`
`wtcoeffs.icdf24_3`

and so on, where '_5' corresponds to 5 wavelet scales.

Ensure the output files `wtcoeffs*` are cleared after each event, so that
lingering data from one event is not attached to a latter, incomplete event.
