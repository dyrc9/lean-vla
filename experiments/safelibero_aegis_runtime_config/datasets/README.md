# Intentionally empty

SafeLIBERO evaluation reads the BDDL and `pruned_init` assets from the pinned
AEGIS checkout.  No demonstration dataset is required by the evaluation path;
this existing empty directory prevents upstream LIBERO from falling back to an
interactive per-user configuration or emitting a misleading missing-path
warning.
