# Security

## API key

- Stored only in `bridge\.deepseek_key` (git-ignored) or the environment.
- `run_live.ps1` loads it into `DEEPSEEK_API_KEY` and never prints it.
- The Squeak image never receives the key. The Bridge/Usage page shows only
  *presence/source*, never the value.
- Logs are redacted (`oc_sk_`, `Authorization`, `Bearer`, `sk-`, `api_key=`).

If you accidentally commit a key, revoke it at the provider immediately and
rewrite the commit/branch before publishing.

## Local-only services

- `127.0.0.1:8765` — chat bridge. Binds loopback only.
- `8767` — dev control server. Compiles local `.st` files. It is **not started
  by the release image**.

**Important:** the dev control server uses the 2009 Squeak `Socket>>listenOn:`
API, which cannot bind a single interface. It listens on `0.0.0.0:8767`, so
Windows Firewall prompts and other machines on the same network could reach it.
Do not run the dev image on an untrusted network. Block 8767 inbound, or set
`controlServer=off` in `scratch\base\harness.ini` (created by
`run_scratch.ps1`). The full-screen release image never starts this server and
does not touch 8767.

## Audit bundles

`run_live.ps1 -Audit full` writes prompts, project context and raw model output
under `scratch\base\audit\`. These are local debugging artifacts. Do not paste
them into public issues, commit them, or attach them to a release.

## Release bundle

`tools\make_release_bundle.ps1` excludes:

- `bridge\.deepseek_key`, `bridge\harness.ini`, `.env*`
- logs, audits, probes and diagnostic dumps
- the dev control image from the release-only bundle
- imported Scratch 2.0 media (non-redistributable)

Verify a bundle before publishing:

```powershell
Get-ChildItem release -Recurse -File | Where-Object {
  $_.Name -match 'deepseek_key|harness\.ini|audit|\.log$|scratch2'
}
```

## Reporting

Open a private security advisory on GitHub or contact the maintainer directly;
do not include a live key, a private project, or an audit bundle in a public
issue.
