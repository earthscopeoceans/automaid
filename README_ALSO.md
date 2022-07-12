Scripts by Frederic Rocca to decrypt .BIN to .LOG files:
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
    $ cd $AUTOMAID/decrypt/
```

[2] Decrypt  *BIN to *LOG (latter will be placed in same server/ directory) --
```
    $ python -c "import decrypt; decrypt.decrypt_all('/path/to/mermaid/server/')"
```
(note that final "/" in server/ path is REQUIRED!)

[3] Run `automaid` as normal --
```
    $ python $AUTOMAID/scripts/main.py -s $MERMAID/server/ -p $MERMAID/processed/
```
