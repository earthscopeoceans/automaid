> **AI-written documentation — non-authoritative.** Verify operational details against the current project code before relying on them.

# Processed output permissions

After all floats, symlink mirrors, and the final corrected pressure report are
written successfully, automaid removes owner, group, and other write permission
bits from every regular file and directory in the configured processed tree,
including the root directory and incomplete cycle directories. Existing read
and execute permissions are preserved. Symlinks are skipped and linked
directories are not traversed, so targets outside the tree are not modified.

Mirror symlinks to canonical files in the processed tree consequently provide
read-only access. Mirror directories located outside the processed tree retain
their existing permissions. Mirrors located inside a custom processed tree have
their directory write permissions removed along with the rest of the tree.

At the start of a subsequent run, automaid restores owner write permission to
every regular file and directory in an existing processed tree. Symlinks and
their targets are not modified. A fresh processed directory starts writable.
The automatic final locking step is reached only after processing and mirror
rebuilding succeed. A failed run can leave the processed tree writable; a
permission error during locking propagates and can leave it partially locked.

These permission bits protect against accidental modification through normal
filesystem access. The file owner can change them again; they do not provide
an immutable archive or replace backups.
