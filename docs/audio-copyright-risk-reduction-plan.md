# Audio Copyright Risk Reduction Plan

## Goal

Reduce audio-based copyright matches by ensuring the final recap does not contain
audio from the movie when using the voiceover-only delivery policy. Lowering the
movie soundtrack to 20% is not a reliable way to avoid a match; automated systems
may recognize audio at reduced levels, and no mix setting can guarantee that a
platform will not issue a claim.

This plan addresses audio only. It does not establish that the video, dialogue,
or other included material is cleared for publication.

## Current Behavior

The `narration` audio mode now uses the `voiceover-only` profile by default:
movie audio is not mixed, narration plays at its authored positions, and an
optional configured BGM fills the remaining timeline while ducking under
narration. With no BGM, uncovered intervals are silent.

## Delivery Options

### Recommended: voiceover-only

- Exclude the movie's audio stream from the final mix for the entire output
  duration. Do not merely set its gain to zero in ordinary ducking windows.
- Keep narration at its authored level. Where narration has no placement, leave
  silence rather than restoring movie audio.
- Add only music or effects that are separately licensed for the intended
  platform and use.
- Make this a named, explicit audio policy so it cannot be confused with normal
  ducking or a 20% source-audio setting.

This is the strongest option for removing the movie soundtrack as a source of
audio matches. A silent gap is preferable to reintroducing unlicensed movie
audio if reducing audio-match risk is the priority.

### Alternative: `source-ducking`

Keep movie audio and configured BGM at 20% in narration gaps and duck both to 5%
during narration, using the same longer, minimum three-second bridge. This preserves selected dialogue and action
sound with fewer rapid level changes, but it also retains audio that can trigger
a match. The 20% setting is a mix choice, not a copyright-risk control.

Use this only when the source audio is cleared for use or when the publisher
accepts the risk. Do not label this policy copyright-safe.

### Alternative: `legacy-ducking`

Retain the previous configurable source-audio envelope unchanged. This option is
available for projects that depend on the existing mix values and automation.

For either profile, supply BGM through `BGM_PATH`; the tool does not bundle or
certify a copyright-free track. Confirm the asset license covers the intended
platform, territory, monetization, and duration.

## Implementation Plan

1. Keep `voiceover-only` as the default narration profile and expose
  `source-ducking` and `legacy-ducking` as explicit alternatives.
2. In `voiceover-only`, never map the movie audio stream. Use BGM only when
  explicitly configured; otherwise leave uncovered intervals silent.
3. In `source-ducking`, use a 20% source level in gaps, 5% under narration, and
  a minimum three-second bridge. Continue ducking configured BGM under
  narration. Keep the previous configurable mix under `legacy-ducking`.
4. Record the selected profile and source-audio inclusion in settings, timeline,
  manifest, and QC. Require an explicit non-default profile for strict adopted
  prepared beds whose stems may include movie audio.
5. Test with distinct synthetic tones to prove movie audio is absent in the
  default profile and present in opted-in source profiles, while narration and
  configured gap BGM remain audible.
6. Document that user-supplied BGM rights are not automatically verified and
  that muting movie audio cannot guarantee a platform outcome or clear video
  rights.

## Acceptance Criteria

- A voiceover-only render contains no audio stream derived from the movie at
  any point in its duration.
- Narration remains audible at its intended placements; configured BGM fills
  uncovered intervals, and without BGM they remain silent.
- QC and the manifest identify the selected policy and block accidental source
  audio inclusion.
- The 20% source-ducking profile and the previous legacy mix remain explicitly
  selectable and are documented as not providing copyright protection.
- Tests demonstrate source-audio absence in both voiceover and non-voiceover
  windows.

## Limitations

Removing movie audio can reduce audio-match risk from the soundtrack, but it
cannot guarantee that a social platform will not claim, block, mute, or restrict
the upload. Video matching, narration content, replacement music, and platform
rules remain separate considerations. Use only material you have the rights or
permission to publish.