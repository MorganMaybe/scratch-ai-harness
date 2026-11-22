# Security

This is a local tool with two things worth being careful about: your API key,
and a dev control server that's more exposed than I'd like. Both are covered
below, plainly.

## API key

- It's stored in `bridge\.deepseek_key` (git-ignored) or in an environment
  variable. Nothing else.
- `run_live.ps1` loads it into `DEEPSEEK_API_KEY` and never prints it.
- The Squeak image never receives the key. The Bridge and Usage pages show
  only whether a key is present and where it came from, never the value.
- The logger redacts the common shapes (`oc_sk_`, `Authorization`, `Bearer`,
  `sk-`, `api_key=`). That's a safety net. It doesn't make it fine to paste a
  log somewhere public.

If you accidentally commit a key, revoke it at the provider right away. Then
rewrite the commit or branch before you publish anything. Deleting it in a
later commit isn't enough, because it's still in the history.

## Local-only services

- `127.0.0.1:8765` is the chat bridge. It binds to loopback only.
- `8767` is the dev control server. It compiles local `.st` files and runs
  commands in the image. The **release image never starts it.**

**Important:** the dev control server listens on `0.0.0.0:8767`, not just on
loopback. The 2009 Squeak `Socket>>listenOn:` API can't bind to a single
interface, so it binds to all of them. That means Windows Firewall will prompt
you, and anyone else on the same network who can reach your machine can reach
the port. I haven't found a clean way around that yet.

What to do about it:

- Don't run the dev image on a network you don't trust, such as a café or a
  shared office.
- Block inbound 8767 in the firewall.
- Or set `controlServer=off` in `scratch\base\harness.ini` (created by
  `run_scratch.ps1`) to stop the server from starting at all.
- Never expose 8767 to the internet, a tunnel or a reverse proxy.

The release image doesn't start this server and doesn't touch 8767, so the
release build is the one to use if you're just playing with it.

## Audit bundles

`run_live.ps1 -Audit full` writes prompts, project context and raw model output
under `scratch\base\audit\`. They're local debugging artifacts. Don't paste
them into a public issue, commit them, or attach them to a release.

## Release bundle

`tools\make_release_bundle.ps1` leaves out:

- `bridge\.deepseek_key`, `bridge\harness.ini` and `.env*` files
- logs, audits, probes and diagnostic dumps
- the dev control image when you pass `-NoDevImage` to the bundle builder (the
  default bundle includes both images on purpose; the dev image is the one that
  starts 8767, so testers should launch `run_release.ps1`)
- imported Scratch 2.0 media, which isn't redistributable

Check a bundle before you publish it:

```powershell
Get-ChildItem release -Recurse -File | Where-Object {
  $_.Name -match 'deepseek_key|harness\.ini|audit|\.log$|scratch2'
}
```

If that prints anything, don't publish the bundle.

## Reporting

For a security problem, open a private security advisory on GitHub, or contact
the maintainer directly. Don't include a live key, a private project or an
audit bundle in a public issue.
