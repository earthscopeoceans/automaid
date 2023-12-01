!!! PREPROCESSING STEPS MUST BE RUN BEFORE MAIN AUTOMAID ROUTINE !!!

Scripts by Frederic Rocca to concatenate and decrypt .BIN to .LOG files:
https://github.com/oseanfro/automaid.git

Will soon be embedded into ESO's automaid version.

Until that time you must manually decrypt using these instructions
(before running the main `automaid` routine).

[0] Activate pymaid --

```
    $ conda activate pymaid
```
(or maybe ```$ source activate pymaid```)


[1] Navigate to decrypt/ directory --
```
    $ cd $AUTOMAID/preprocess/
```


[4] Concatenate .000, .001, ..., .00N etc .LOG files (latter will be placed in same server/ directory) --
```
    $ python -c "import concatenate; concatenate.concatenate_files('/path/to/mermaid/server/')"
```
(note that final "/" in server/ path is REQUIRED!)
[ JDS: python -c "import concatenate; concatenate.concatenate_files('/Users/joelsimon/mermaid/server_jamstec/')"]


[3] Decrypt *BIN to *LOG (latter will be placed in same server/ directory) --
```
    $ python -c "import decrypt; decrypt.decrypt_all('/path/to/mermaid/server/')"
```
(note that final "/" in server/ path is REQUIRED!)
[ JDS: python -c "import decrypt; decrypt.decrypt_all('/Users/joelsimon/mermaid/server/')" ]
[ FJS: python -c "import decrypt; decrypt.decrypt_all('/u/fjsimons/MERMAID/sustech/')" ]
[ FJS: python -c "import decrypt; decrypt.decrypt_all('/u/fjsimons/MERMAID/psdmaid/')" ]


[4] Run `automaid` as normal --
```
    $ python $AUTOMAID/scripts/main.py -s $MERMAID/server/ -p $MERMAID/processed/
```
[ FJS: python $YFILES/automaid/scripts/main.py -s $MERMAID/sustech -p $MERMAID/processed-sustech ]
[ FJS: python $YFILES/automaid/scripts/main.py -s $MERMAID/psdmaid -p $MERMAID/processed-stanford ]
