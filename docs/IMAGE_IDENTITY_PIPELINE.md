# VELA verified image identity pipeline

VELA uses a bounded, local-first workflow for named characters, people, products,
costumes, and any request containing a visual reference. Generic unreferenced art
keeps the fast direct ComfyUI route.

## Contract

1. Resolve the subject in its stated franchise or context.
2. Search a bounded set of authoritative sources and inspect one to three images.
3. Reject namesakes, fan redesigns, watermarks, title cards, and obscured subjects.
4. Write an identity card from visible evidence. The card is authoritative over
   the vision model's remembered franchise knowledge.
5. Route anime and 2D identities to Animagine XL, photos to RealVisXL, and exact
   text or non-anime reference edits to FLUX.2.
6. Generate sequentially at most three times. Never generate attempts in parallel.
7. Unload ComfyUI before loading the local vision reviewer.
8. Compare every candidate with the authoritative references.
9. Publish only when identity is at least 90, overall quality is at least 88, and
   there are no critical identity failures.
10. If the gate is not reached, preserve the best quarantined draft but do not
    display it as a successful result.

## Resource profile

The target machine is an RTX 3060 Ti with 8 GB VRAM and 16 GB RAM. Reference-locked
SDXL generation therefore uses a 768-class latent and scales the accepted output to
the requested 4K canvas. ComfyUI and the local vision reviewer run serially.

## Reference lifecycle

- User attachments are never deleted automatically.
- Canonical references selected for a character card remain available for future
  identity consistency.
- Web images downloaded only for one request are marked as temporary in the
  research manifest and deleted when the bounded run exits, including failures.
- Source URLs, visible identity traits, scores, and user feedback remain as compact
  learning records.

## UI routing

The desktop UI sends recognizable identities, strict-reference requests, and image
attachments through the OpenClaw Agent skill. Only generic image prompts use the
direct `/api/generate-image` path. The Agent response must contain a real `MEDIA:`
path before the UI renders an image.

## Acceptance

The 90 value is a local vision-review threshold, not a mathematical guarantee of
copyright-identical artwork. A failed gate is reported honestly. Repeated failures
should lead to a clearer official reference or a dedicated character LoRA, not an
unbounded retry loop.
