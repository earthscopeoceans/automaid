How to use J. D. Simon's v3.6.0 (writes .mhpsd files) with F. Rocca's unmerged automaid.
The long and the short of it: you must convert .BIN files into .LOG files first.

[0] clone Rocca's automaid (do this in path other than $AUTOMAID)

```
    $ git clone https://github.com/oseanfro/automaid.git
```

[1] cd into Rocca's automaid and activate `pymaid` conda env

```
    $ cd automaid
    $ conda activate pymaid
```

[2] decrypt server (convert *.BIN to *.LOG) using Rocca's `decrypt.py`
(note: the final "/" is very important in server path)


```
    $ python -c "import decrypt; decrypt.decrypt_all('/Users/joelsimon/mermaid/server/')"
```


[3] ensure you have Simon's remote automaid, not just ESO's

```
    $ cd $AUTOMAID
    $ git remote add joelsimon https://github.com/joelsimon/automaid.git
```

[4] cd into Simon's automaid (probably from ESO's) and ensure in his v3.6.0 branch
(note: if you have local edits you'll need to get rid of them, `commit`, or `stash` them)

```
    $ git fetch joelsimon
    $ git branch v3.6.0 joelsimon/v3.6.0
    $ git checkout v3.6.0

```

[5] run Simon's automaid as usual (`pymaid` env should still be active)

```
    $ python $AUTOMAID/scripts/main.py -s $MERMAID/server/ -p $MERMAID/processed/
```
