# Draft: A coding-agent lifeboat inside an iPhone sandbox

> REVIEW_STATE: unreviewed
>
> This is source material for a future post, not accepted project history or a publication-ready article.

## The actual problem

The motivating problem was not “run an LLM on an iPhone.” It was reducing the human availability bottleneck in a coding workflow built around Ghostty, Herdr, and OMP on a Mac. The phone needed several independent degradation modes:

1. normal remote access to the real Mac agent session;
2. a small cloud-backed coding agent when the Mac is unavailable;
3. an offline model for explanation, debugging, and recall;
4. local Unix-like tools for rescue work.

That led to Tailscale On Demand, hardened Remote Login, Orca/SSH experiments, PocketPal, a-Shell, and eventually Pithon.

## Why a new harness

The surprising discovery was not that Python agents were absent. It was that popular agents depend on Node, native Python wheels, desktop subprocess semantics, or large SDK graphs. a-Shell allows standard Python and pure-Python packages, but its compiled WebAssembly commands lack sockets and fork. The boring choice—`urllib`, `json`, `pathlib`, and an explicit loop—became the most portable one.

Pithon asks what remains when an agent harness is reduced to load-bearing parts:

- stable prompt and tool prefixes;
- a provider call;
- parsed tool requests;
- bounded side effects;
- append-only state;
- observable feedback;
- explicit human judgment at dangerous transitions.

## The nested side quests

The project emerged through several nested questions:

- Can an iPhone be a good terminal for a persistent Mac coding session?
- Does Tailscale On Demand remove the battery cost without making reconnection unreliable?
- Can an offline 1–2B model act as a useful flashlight?
- Is PocketPal the right local GGUF runtime?
- Can a-Shell host a useful coding agent without pip dependencies?
- Can a reverse SSH tunnel temporarily make the phone legible to a Mac-side agent?
- Would Rust or Zig make the harness leaner, or merely collide with WASI's missing sockets and fork?

The answers increasingly favored architecture over product accumulation: keep the real session on the Mac, make the fallback agent independently useful, and characterize phone constraints with executable probes rather than assumptions.

## Harness engineering at tiny scale

OpenAI's harness-engineering account focuses on making environments legible and feedback loops executable. The same idea applies at hundreds of lines:

- the capability probe turns a-Shell folklore into facts;
- the provider boundary parses response shapes rather than guessing;
- policy owns path confinement once;
- oversized diffs fail instead of showing a misleading prefix;
- cache hit/miss metrics expose whether stable-prefix design works;
- repository docs map to executable owners;
- each discovered failure should become a regression test or diagnostic.

## Working title candidates

- “Pithon: rebuilding the load-bearing parts of Pi with Python's standard library”
- “The coding-agent lifeboat: what survives inside an iPhone sandbox”
- “No Node, no wheels, no daemon: a useful coding agent in stdlib Python”

## Claims requiring evidence before publication

- Real a-Shell DeepSeek tool loop on an iPhone 13.
- Measured cache-hit behavior across several turns.
- Measured PocketPal performance for LFM2.5-1.2B and Qwen3-1.7B.
- Whether a-Shell's SSH client supports `-R`.
- Whether Python loopback listening remains alive while a-Shell is foregrounded/backgrounded.
- End-to-end phone-to-Mac and Mac-to-phone experimental latency.
- Exact similarities and incompatibilities with upstream Pi.
