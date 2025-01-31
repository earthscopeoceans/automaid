function readmhpsd_example()
% READMHPSD_EXAMPLE
%
% Read and plot an .mhpsd file in MATLAB.
%
% Relies on functions in $OMNIA, in particular `readmhpsd` --
% https://github.com/joelsimon/omnia.git
%
% Author: Joel D. Simon
% Contact: jdsimon@alumni.princeton.edu | joeldsimon@gmail.com
% Last modified: 25-Apr-2023, Version 9.3.0.948333 (R2017b) Update 9 on MACI64

clc
close all

% Read the MERMAID Hydrophone Power-Spectral-Density file.
filename = '20211116T125142.0002_6194A40E.MER.STD.mhpsd';
[hdr, psd] = readmhpsd(filename);

% Display the header info (similar to a SAC header).
disp(hdr)

% Recreate the 50-95% percentile figure from automaid v3.6.0-X
figure
semilogx(psd.freq, psd.perc50, 'b', 'LineWidth', 2)
hold on
semilogx(psd.freq, psd.perc95, 'r', 'LineWidth', 2)
hold off
legend('50th percentile', '95th percentile')
title(sprintf('Network: %s Station: %s Start Time: %s', hdr.Network, hdr.Station, ...
              hdr.StartTime))

% Note that psd.freq(1) = 0, log(0) is undef, so the first point MATLAB plots is
% psd.freq(2) (and Python draws a straight line headed towards 0 to the left and
% bounds the left XLim seemingly arbitrarily...)
xlim([psd.freq(1) psd.freq(end)])
ylim([-110 -40])

% Add cosmetic finishes.
shrink([], 1, 1.5)
longticks([], 2)
xlabel('Freq. [Hz]')
ylabel('dBfs$^2$/Hz')
latimes
%savepdf(filename)
