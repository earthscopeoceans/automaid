> **AI-written documentation — non-authoritative.** Verify scientific, data-management, and operational details against the linked primary sources and current project code before relying on them.

# automaid documentation

Short reference pages for data access and output formats. Each topic has its
own page so that updates stay focused.

`automaid` processes raw MERMAID instrument files from the configured `server`
directory and writes derived products to the configured `processed` directory.
The server directory is read only to automaid. Processing stops before any
writes if it overlaps the processed tree, database directory, or mirror paths.
Each run also compares SHA-256 fingerprints of the server file tree before and
after processing, including on failure. A changed fingerprint raises an error;
the check detects changes by other processes as well as by automaid and reads
the full server contents twice.
Each processed float directory retains copies of server `.MER`, `.LOG`, and
`.BIN` files in `MER/`, `LOG/`, and `BIN/`, respectively. Successfully decoded
`.BIN` logs are written directly to `LOG/` under their `.LOG` names. A fresh
decode replaces any same-stem server `.LOG` copy in that directory. Server `.out`
and `.vit` files remain at the float directory's top level. These archives are
included in the final read-only processed tree. Numbered `.LOG` and `.BIN`
fragments copied from the server are kept beside their terminal files.
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

## GeoCSV workflow

- [Production and workflow](geocsv.md): outputs, scientific sources, deduplication and ownership.
- [Payload schema](../../mermaid-geocsv/docs/format-spec.md): exact header, fields, missingness and examples.
- [Clock timing matrix](clock-timing-matrix.md): signs, source mappings, correction serialization and limitations.
