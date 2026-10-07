# Manager goals

- Preserve continuity of apk-research across chats/runtimes without relying on conversational memory alone.
- Keep the Windows GUI and managed Android research workflow reliable and understandable for the owner.
- Preserve forensic correctness: RAW-first evidence, explicit provenance, exact packet/flow accounting and no causal overclaim.
- Evolve the product incrementally from the latest verified baseline, protecting the proven v0.10.5 startup/runtime path unless evidence justifies change.
- Keep releases reproducible through the repository's commit-triggered CI/AVD/Windows packaging gates.
- Maintain durable project decisions, verified lessons and active commitments on the authoritative `context` branch.
- Make decrypted HTTPS application traffic directly inspectable in apk-research: requests and responses, including URL, method/status, headers and available bodies, while preserving passive RAW PCAP as an independent source of truth and explicitly marking interception-induced behavior.
