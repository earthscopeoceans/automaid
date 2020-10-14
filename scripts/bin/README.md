This directory, when the source code has been compiled, will contain

`icdf24_v103_test`
`icdf24_v103ec_test`

And when automaid has been run, it will contain

`wtcoeffs`
`wtcoeffs.icdf24_5`
`wtcoeffs.icdf24_3`

and so on, where '_5' corresponds to 5 wavelet scales.

Ensure the output files `wtcoeffs*` are cleared after each event, so that
lingering data from one event is not attached to a latter, incomplete event.
