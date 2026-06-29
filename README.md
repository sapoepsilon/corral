# corral

Broker ephemeral backend boxes on a Proxmox-style host, and serialize scarce
resources (like a single physical test device) behind a lock.

You have one always-on box and want N more **on demand** — one per PR, per Slack
thread, per QA run — each its own isolated backend, torn down when done. And you
have one real phone everyone has to share. corral is the small piece that hands
those out and queues access, while staying ignorant of *what* your backend or
frontend actually is.

- **Backends fan out.** Clone-on-demand up to a cap; past the cap, `allocate`
  returns `{"status":"wait"}` and the caller waits.
- **Devices serialize.** `corral resource <name> -- <cmd>` runs a command holding
  a named lock, so the one phone is used by one run at a time.
- **Generic by hooks.** The engine clones/destroys/lists/queues. Everything
  project-specific (install the backend, build the frontend, reach a device) is a
  hook script you write. See [HOOKS.md](HOOKS.md).
- **Zero dependencies.** One Python 3.11+ file, stdlib only. Providers shell out
  to `pct`/`qm` over SSH.

## Quick start

```bash
corral init                 # scaffolds corral.toml + hooks/ stubs
$EDITOR corral.toml hooks/* # point it at your Proxmox node, fill in the hooks
corral list                 # show the pool
```

## Lifecycle

```bash
# frontend-only change: reuse the always-on baseline, no clone
corral allocate thread-42 --kind shared

# backend change: clone on demand (or {"status":"wait"} if at cap)
blob=$(corral allocate thread-42) || { echo "queued"; exit; }

# ...build & deploy your frontend against $blob, run QA...

# share the one physical device with everyone else
corral resource pixel -- ./hooks/deploy-frontend android-device "$blob" 100.x.y.z:5555

corral release thread-42    # tears the clone down (runs teardown-extra first)
corral reap --ttl 120       # cron insurance: destroy clones a crashed run leaked
```

## Providers

`[provider] type` is `proxmox` (drives `pct`/`qm` over SSH; `kind = lxc|qemu`) or
`mock` (a JSON file — used by the test suite and for trying the flow with no infra).

## Test

```bash
python3 test_corral.py
```

Drives the real CLI against the mock provider: cap enforcement, the wait signal,
idempotent re-allocate, release-frees-a-slot.

## Adapters

`hooks/` for one project is an *adapter*. The reference adapter lives in
[`adapters/mock/`](adapters/mock/). Real example: the Kentra Health adapter
(Proxmox linked-clone + Supabase + Tailscale + Flutter/adb) in the private
kentra-monorepo under `corral/`.
