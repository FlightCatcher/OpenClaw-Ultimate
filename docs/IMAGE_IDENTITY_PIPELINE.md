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
6. For full-body anime and creature identities, combine IP-Adapter guidance with
   low-denoise image-to-image anchoring from the clearest full-body reference.
   For an obscure identity that repeatedly scores below 90, first establish a
   canonical portrait with `identity_mode=anchor`; arbitrary new poses remain a
   separate acceptance target and may require a dedicated LoRA.
7. Generate sequentially at most three times. Never generate attempts in parallel.
8. Unload ComfyUI before loading the local vision reviewer.
9. Compare every candidate with the authoritative references.
10. Publish only when identity is at least 90, overall quality is at least 88, and
   there are no critical identity failures.
11. If the gate is not reached, preserve the best quarantined draft but do not
    display it as a successful result.

## Identity acceptance scopes

- **Canonical anchor:** the generated image keeps the authoritative reference's
  composition. Acceptance uses deterministic MAE, RMSE, and luminance-correlation
  measurements plus a local visual review. The Tianlu acceptance sample reached
  96.73 on the conservative objective score and 97 after the combined gate.
- **Novel pose or scene:** acceptance continues to use the strict reference-aware
  visual gate. A canonical anchor score must never be reported as proof that an
  arbitrary new pose reached the same similarity. Repeated sub-90 novel-pose results
  are a signal to train or install a character-specific LoRA instead of retrying
  indefinitely.

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
