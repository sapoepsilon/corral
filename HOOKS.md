# Hook contract

corral knows how to clone, destroy, list, and queue boxes. It knows nothing about
your backend, your frontend, or your devices. That gap is filled by **hook
scripts** in `hooks/` (path set by `[hooks] dir`). Every hook is optional — a
missing hook is a no-op.

A hook is any executable. corral passes the **connection blob** (JSON) as both
`$1` and the `$CORRAL_BLOB` env var. A hook that wants to add fields to the blob
prints a JSON object on its **last stdout line**; corral merges it in. A non-zero
exit aborts the operation.

## The blob

Fields corral always sets:

| Field | Meaning |
|---|---|
| `key` | the allocation key (e.g. a Slack thread id) |
| `kind` | `clone` or `shared` |
| `box_id` | Proxmox VMID of the box |
| `name` | `<name_prefix><key>` |
| `proxmox_ssh` | ssh host of the Proxmox node (so hooks can `ssh $proxmox_ssh pct exec $box_id -- ...`) |
| `box_kind` | `lxc` or `qemu` |

`shared` allocations also carry `ip` (the baseline_ip). Hooks add whatever else
the project needs — typically `backend_url` and `ip`.

## The hooks

| Hook | When | Args | Should do |
|---|---|---|---|
| `setup-backend` | after a box is cloned/started, or on a shared allocate | blob | make the box reachable (e.g. `tailscale up`), install/start the backend, **echo `{"backend_url":...,"ip":...}`** |
| `build-frontend` | called by your pipeline, not the engine | `<target> <blob>` | build for `web` / `ios-sim` / `ios-device` / `macos` / `android-emu` / `android-device` |
| `deploy-frontend` | called by your pipeline | `<target> <blob> [device]` | serve the URL / install to a sim / push to a device |
| `health` | your pipeline polls it | blob | exit 0 when the backend is ready |
| `teardown-extra` | before corral destroys the box | blob | cleanup the destroy won't cover (tailscale logout, dns) |

`build-frontend` / `deploy-frontend` / `health` are called by *your* pipeline, not
by corral itself — corral only invokes `setup-backend` (on allocate) and
`teardown-extra` (on release/reap). They live here so a project keeps all its
target-specific glue in one place.

## Networking is a hook concern

corral does not run `tailscale` for you. Bringing the box onto a network (and
discovering its IP) belongs in `setup-backend`, because the right answer differs
per project and per box type (`pct exec` vs `qm guest exec` vs direct ssh). Echo
the resulting `ip` / `backend_url` and the rest of the pipeline uses them.
