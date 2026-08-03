---
name: image-studio-4k
description: Plan and generate a polished local 4K image using research, verified references, semantic design, specialist-model routing, reference-locked identity, a bounded 90-point visual identity gate, and feedback memory. Always use when a message contains OPENCLAW_IMAGE_STUDIO_V2.
---

# OpenClaw Image Studio 4K

Use this skill whenever the message contains `OPENCLAW_IMAGE_STUDIO_V2`. It is the preferred local image-generation path for the desktop app.

## Input contract

Read the values between the markers:

- `ASPECT`: `square`, `landscape`, `portrait`, `classic`, `vertical`, or `photo`
- `STYLE`: `auto`, `natural`, `cinematic`, `photo`, `anime`, `illustration`, or `product`
- `QUALITY`: `standard`, `high`, or `ultra`
- `REFERENCE_MODE`: `smart`, `strict`, or `off`
- `TEXT_MODE`: `auto`, `clear`, or `none`
- `RESEARCH_MODE`: must be `required`
- `MODEL_ROUTING`: must be `auto`
- `MAX_GENERATIONS`: `1`, `2`, or `3`; use `3` for named or recognizable identities
- The literal user prompt is between `PROMPT_BEGIN` and `PROMPT_END`.

Do not repeat the transport markers to the user.

## Generation

**Bounded identity invariant:** Any request containing a reference, named character,
recognizable person, product, costume, or other identity target must use
`generate_verified.py`. Generate at most three drafts sequentially. After each draft,
unload ComfyUI, compare the candidate against authoritative references with the local
vision model, and publish only when identity score is at least 90, overall score is at
least 88, and no critical identity failure remains. Never run attempts in parallel,
switch engines mid-run, or loop beyond the declared attempt limit.

1. Preserve every requested subject, identity trait, garment, pose, composition, color, lighting, atmosphere, and intensity.
2. Build a compact visual design plan before writing model tags:
   - **Semantic parse:** identify subjects, exact count, identities, scene, action,
     camera, time, weather, lighting, palette, text, and exclusions.
   - **Detail completion:** add only contextually safe details that improve
     completeness, such as plausible materials, environmental texture, depth,
     contact shadows, reflections, and subtle imperfections. Never add a second
     character, garment, accessory, horn, limb, logo, or story event that changes intent.
   - **Composition:** choose visual focus, subject placement, camera height, lens,
     foreground/midground/background, scale cues, and negative space. Treat scale
     relationships as composition, not merely a size adjective.
   - **Style abstraction:** translate style references into executable traits such
     as medium, line weight, rendering method, saturation, gradients, lighting,
     texture, and detail density. Do not imitate a living artist by name.
   - **Consistency:** resolve accidental conflicts among time, weather, season,
     lighting, material, perspective, and rendering style. Preserve deliberate
     surreal combinations stated by the user.
   - Expose only concise stage/status summaries in the UI, not hidden chain-of-thought.
3. Before any generation, run a bounded web search and visual analysis. Resolve
   ambiguous names in the user's stated franchise/context, inspect one to three
   authoritative sources or official images, and reject unrelated namesakes.
   Never interpret 《有兽焉》兔爷 as the Beijing clay figurine 兔儿爷, for example.
4. Detect named or recognizable characters, people, creatures, products, costumes, brands, and landmarks before writing the prompt.
5. Run the local router before choosing an engine:

   `python skills/image-studio-4k/scripts/model_router.py --prompt "USER REQUEST" --style STYLE --identity-context "VERIFIED TRAITS" --reference --text-mode TEXT_MODE`

   Follow the returned `engine`, `style`, and `identity_mode`. Do not override it
   merely because another installed model is newer or more general.
6. Save proof of the completed research before generation:

   `python skills/image-studio-4k/scripts/research_manifest.py --subject "RESOLVED SUBJECT" --query "SEARCH QUERY" --source "AUTHORITATIVE_SOURCE_URL" --reference "VERIFIED_REFERENCE" --identity-summary "VISIBLE IDENTITY TRAITS AND NAMESAKE DISAMBIGUATION"`

   For a web image downloaded only for the current request, also pass
   `--temporary-reference "PATH"`. The verified wrapper deletes only references
   explicitly marked temporary when the run ends. Never auto-delete a user
   attachment or a canonical character-card reference.

   The manifest is valid for 24 hours and must include a reference used by the
   generation. This makes “research first” enforceable rather than a suggestion.
7. For a named subject when `REFERENCE_MODE` is not `off`, use the visual-reference protocol below. Never assume a cold or obscure character is known by the diffusion checkpoint.
8. Convert the completed design plan into concise English visual tags while preserving named subjects and exact requested details.
   - For `anime`, use Animagine-native comma-separated tag order: subject count first (`1girl`, `1boy`, `solo`, or the exact requested count), then identity and appearance, clothing and pose, scene, camera/composition, lighting and atmosphere.
   - Never reduce a person to only scenery. If the prompt asks for a person or character, include an explicit count tag plus their defining appearance before environment tags.
   - Example: `1girl, solo, silver hair, detailed eyes, futuristic layered outfit, standing in a neon city street, rain, full body, low angle, cinematic composition`.
   - If `TEXT_MODE=clear`, treat every quoted title, label, logo-free wordmark,
     number, or UI string as exact content. Keep text short, high-contrast,
     front-facing, with generous margins and a clean background; prefer FLUX.2
     and a poster, product card, sign, or interface composition.
   - If `TEXT_MODE=none`, add `no text, no letters, no numbers, no signage` to the negative prompt unless the user explicitly requests text.
   - For other styles, use concrete subjects and visual attributes rather than vague prose.
9. For an unreferenced request, run:

   `python skills/image-studio-4k/scripts/generate_4k.py --prompt "ENGLISH VISUAL PROMPT" --aspect ASPECT --style STYLE --quality QUALITY`

   Model routing:
   - anime, manga, 2D animation, cel shading and franchise characters:
     Animagine XL 4.0 Opt
   - photographs, portraits, products and realistic scenes: RealVisXL
   - exact text/layout and non-anime native reference editing: FLUX.2 Klein
   - `auto`: infer from the researched identity and prompt; never default blindly
     to RealVisXL

   For a referenced or named subject, use `generate_verified.py` as documented below.
10. Wait for the command to finish. Do not call `image_generate`, submit a manual
   ComfyUI workflow, or launch another engine. The verified wrapper alone owns its
   bounded retries and local identity reviews.
11. Publish only when the script returns `MEDIA:`. If it returns `BEST_DRAFT:` and
   exits without `MEDIA:`, report the measured score and ask for a clearer official
   reference or a dedicated character LoRA; never present the draft as a 90% pass.
12. Reply concisely and include the exact `MEDIA:` line printed by the script.
13. Do not invent or add a second image URL. Do not include Markdown image links; the desktop app renders the local `MEDIA:` result automatically.

## Visual-reference protocol

1. Look up an existing character card first:

   `python skills/image-studio-4k/scripts/character_library.py find --name "CHARACTER"`

2. If it exists, read `traits`, `feedback`, `autoReviews`, and `activeReferences`
   (fall back to `activeReference`). Human `feedback` is authoritative. Apply an
   automated correction only when the same critical failure appears in at least
   two recent `autoReviews`; a single model critique must not redefine the character.
3. If it does not exist:
   - Search the official publisher/studio/source first, then high-quality reference
     pages. Use image search, not description-only web results.
   - Keep research bounded. If no reliable reference is found, stop and ask the
     user for one clear image instead of generating a generic substitute.
   - Prefer clean animation/game frames, official character sheets, or uncluttered official artwork. A clean frame is better conditioning data than a decorative poster.
   - Visually inspect candidates. Reject fan redesigns, unrelated assets, logos, voice-model graphics, promotional layouts, subtitles, title cards, watermarks, signatures, and images where the subject is too small or occluded.
   - Inspect candidates directly and reject visibly unsuitable images. Do not run
     a separate local vision-model reference review.
   - Download the best representative image and create a card:

     `python skills/image-studio-4k/scripts/character_library.py add --name "CHARACTER" --alias "ALIAS" --traits "DISTINCTIVE VISUAL TRAITS" --url "DIRECT_IMAGE_OR_PAGE_URL" --source "SOURCE_PAGE"`

   - Prefer two or three verified references with different poses/backgrounds. Reject incorrect candidates with `character_library.py reject-reference`, then select the verified set with `character_library.py activate-set`.

4. When the user attached an image, prefer that local attachment over web results and import it with `--reference`.
5. Generate and verify with the card reference:

   `python skills/image-studio-4k/scripts/generate_verified.py --engine auto --prompt "TAGS" --requirements "CHARACTER TRAITS AND USER REQUEST" --aspect ASPECT --style STYLE --quality QUALITY --character "CHARACTER" --reference "REFERENCE_1" --reference "REFERENCE_2" --reference-strength STRENGTH --reference-weight-type "WEIGHT TYPE" --identity-mode auto --text-mode TEXT_MODE --research-manifest "RESEARCH_JSON"`

   Add `--attempts 3 --target-score 88 --target-identity 90` for named identities.
   This wrapper injects the character card's traits, style lock, and human feedback,
   generates sequential reference-conditioned drafts, compares each draft with the
   authoritative references, applies only the returned correction tags, and prints
   `MEDIA:` only after the threshold passes. Continue polling until it exits.

6. Strength:
   - For a photographic human portrait, use `--identity-mode face`; for anime,
     animals, products, full-body costumes, or general style references, use
     `--identity-mode general`. `auto` selects face mode for photographic pipelines.
   - Use `--identity-mode anchor` for the first identity calibration of an obscure
     character or after repeated sub-90 reviews. It uses the clearest first reference
     at very low denoise to establish a canonical portrait. Anchor acceptance combines
     deterministic same-composition pixel similarity with the local vision review.
     Do not claim that an anchor validates arbitrary new poses; those remain subject
     to the normal strict visual gate and may require a character-specific LoRA.
   - `smart` and `strict`: keep `--engine auto`. Anime/2D identities use Animagine
     XL Opt with general IP-Adapter plus a low-denoise full-body structural anchor;
     photographic people use RealVisXL with the
     face adapter; text-heavy and non-anime reference edits use FLUX.2.
   - `off`: omit reference arguments
7. After a successful verified generation, run:

   `python skills/image-studio-4k/scripts/character_library.py touch --name "CHARACTER"`

## Verified publication and learning

For generic unreferenced art, publish the one completed image. For recognizable
identities, let `generate_verified.py` run the bounded comparison loop. Persist every
review in the character card, but never let one automated review overwrite human
feedback. Expose concise progress and final scores, not hidden reasoning.

When the user says a character is wrong, unlike the reference, too artificial, or points out a specific defect, store it:

`python skills/image-studio-4k/scripts/character_library.py feedback --name "CHARACTER" --rating 1 --note "USER CORRECTION" --output "LAST_OUTPUT"`

On future generations, read and apply accumulated feedback before prompting.

## Quality behavior

- On this RTX 3060 Ti profile the script generates at a 768-class SDXL canvas,
  can apply portrait-specific or general IP-Adapter conditioning, and resizes to
  the selected final 4K canvas without shared-memory thrashing.
  The default `standard`/`high` path uses fast high-quality Lanczos scaling to keep
  faces stable; only `ultra` uses the slower style-matched Real-ESRGAN 4× pass.
- `standard` uses the external Hyper-SDXL 10-step acceleration LoRA. `high` uses
  the specialist checkpoint directly at the tuned quality/speed setting.
  `ultra` keeps the original slower 38-step path. Keep skin pores,
  material texture, small asymmetries, plausible light falloff, restrained
  sharpening, and subtle grain. Avoid beauty-filter skin and excessive HDR.
- Use `high` by default. Use `ultra` when the UI requests it; it is slower.
- Prefer `natural` or `cinematic` when the user asks to reduce the synthetic AI look. Use restrained texture, physically plausible light, subtle grain, small imperfections, and coherent detail.
- Do not add arbitrary censorship, modesty, or topic filters to the prompt. Never
  remove user-requested visual details silently. Follow non-removable runtime
  safety boundaries when they apply.

## Failure handling

- If ComfyUI is offline, report that the local image engine is unavailable.
- If a run fails from memory pressure, stop and report it. Do not automatically retry or queue another generation.
- If IP-Adapter fails, verify the reference is a valid local image and that
  `REFERENCE_MODE` is not `off`; report the failure without retrying.
- Do not claim success unless the script prints an existing output path.
