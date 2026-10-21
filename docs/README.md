> **AI-written documentation — non-authoritative.** Verify scientific, data-management, and operational details against the linked primary sources and current project code before relying on them.

# automaid documentation

Short reference pages for data access and output formats. Each topic has its
own page so that updates stay focused.

`automaid` processes raw MERMAID instrument files from the configured `server`
directory and writes derived products to the configured `processed` directory.
Its outputs include seismic data products, plots, and metadata. After each run,
it refreshes flat symlink directories containing links to every matching
waveform file found under the processed directory, plus metadata symlink
directories grouped by type. GeoCSV `geo_DET_REQ.csv` files are linked as
`<instrument_id>.geocsv`; `gps.txt` and `gps.csv` become
`<instrument_id>.gps.txt` and `<instrument_id>.gps.csv`. Automaid and mseed2sac
metadata CSVs are also mirrored under their respective directories. With `-p`
omitted or set to `processed`, mirrors are under `$MERMAID/`; with any other
`-p` value, they are under that processed directory. Mirror paths do not retain
the processed tree hierarchy, and duplicate mirror filenames cause processing
to fail. These Argo pages are reference material; automaid does not currently
produce standard Argo profile files.

- [Where Argo files go](CTD_data_centers.md): authoritative archives and discovery tools.
- [What the file formats are](CTD_file_formats.md): Argo profile formats and automaid's current SAL/TEMP-related outputs.
- [Argo pathway goals](CTD_argo_goals.md): near-term example-shaped NetCDF and long-term archive pathway.
- [Near-term NetCDF checklist](CTD_netcdf_checklist.md): tasks for the pseudo-compliant prototype.
- [CTD open questions](CTD_open_questions.md): unresolved timing and position questions, including Argo `JULD` versus `JULD_LOCATION`.

These pages summarize external standards and current code behavior. They do not
make automaid an Argo DAC, GDAC, or format-compliant producer.
