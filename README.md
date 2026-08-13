# Synkronize

[![Validate](https://github.com/zthijs/synkronize/actions/workflows/validate.yml/badge.svg)](https://github.com/zthijs/synkronize/actions/workflows/validate.yml)
[![Lint](https://github.com/zthijs/synkronize/actions/workflows/lint.yml/badge.svg)](https://github.com/zthijs/synkronize/actions/workflows/lint.yml)
[![Test](https://github.com/zthijs/synkronize/actions/workflows/test.yml/badge.svg)](https://github.com/zthijs/synkronize/actions/workflows/test.yml)

**Set your lights to the vibrant color of whatever your media player is playing.**

Synkronize is a custom integration for [Home Assistant](https://www.home-assistant.io/).
It watches a `media_player`, pulls the album art of the current track, picks the
most *vibrant* color out of it, and pushes that to your RGB lights. When
playback stops it hands the lights back exactly as it found them.

## Why "vibrant" and not "dominant"

Most color-extraction tools give you the *most common* color in an image. On
album art that is usually the background - a near-black, or a washed-out grey -
which on a lamp reads as "the light failed to turn on".

Synkronize scores the whole extracted palette instead, the way Android's Palette
API does: candidates are judged on how close their saturation and lightness sit
to a target, with dominance only as a tiebreaker. Run against real photos, the
difference is the entire point of the integration:

| Image                  | Most common color | What Synkronize picks |
| ---------------------- | ----------------- | --------------------- |
| Forest photo           | `#364f21` (dark olive) | `#7db21d` (bright green) |
| Lake at dusk           | `#212a19` (near black) | `#28aab9` (teal)         |
| Beach sunset           | `#f49c99` (pale pink)  | `#fd5d3a` (orange)       |

## Features

- **Follows any media player** - anything that publishes album art works: Spotify, Sonos, Plex, Music Assistant, Chromecast.
- **Vibrancy scoring** - five swatches per cover (Vibrant, Light Vibrant, Dark Vibrant, Muted, Dominant), selectable from the stock light card's effect dropdown.
- **Saturation boost** - pushes the extracted color toward full saturation so it actually reads as vivid on a lamp.
- **Multi-light** - spread the palette across your lights, or put the same color on all of them.
- **Puts your lights back** - the pre-sync state is snapshotted and restored when the music stops.
- **One entity** - `light.synkronize_*` drops into any stock Tile, Mushroom, or Bubble card. No custom card needed.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zthijs&repo=synkronize&category=integration)

1. HACS → three-dot menu → **Custom repositories**
2. Add `https://github.com/zthijs/synkronize` with category **Integration**
3. Search for **Synkronize**, install it, and restart Home Assistant

### Manual

Copy `custom_components/synkronize` into your `config/custom_components/`
directory and restart Home Assistant.

## Setup

**Settings → Devices & Services → Add Integration → Synkronize**, then pick:

- the **media player** whose artwork to follow, and
- the **lights** that should follow it (RGB-capable).

That creates one `light.synkronize_*` entity. Turn it on to start syncing.

```yaml
type: tile
entity: light.synkronize_spotify_bed_light
features:
  - type: light-brightness
```

## How it behaves

| You do this | Synkronize does this |
| --- | --- |
| Turn the entity **on** | Snapshots your lights, starts watching, applies the current artwork's color |
| Track changes | Re-extracts and re-applies (debounced, so skipping tracks does not strobe your room) |
| Pause briefly | Holds the color - the grace period has not elapsed |
| Stop, or pause past the grace period | Runs the idle behaviour (restore by default) |
| Pick an **effect** | Switches which swatch is used, and re-applies immediately |
| Pick a **color** by hand | Applies it directly; superseded at the next track change |
| Turn the entity **off** | Stops watching and runs the idle behaviour |

Playing something with no artwork at all (a radio stream) leaves the lights
alone rather than blanking them.

## Options

**Settings → Devices & Services → Synkronize → Configure**

| Option | Default | What it does |
| --- | --- | --- |
| Color to use | Vibrant | Which swatch to pull out of the artwork |
| With multiple lights | Spread | Spread the palette across lights, or one color on all of them |
| When playback stops | Restore | Restore the previous state, hold the last color, or turn the lights off |
| Wait before handing back | 10 s | Grace period, so a quick pause does not disturb the lights |
| Fade duration | 2 s | Transition applied to every color change |
| Saturation boost | 0.4 | How far the extracted color is pushed toward fully saturated |
| Minimum saturation | 0.35 | Below this, a palette color is not considered vibrant |

Saving options reloads the entry, so changes take effect immediately.

### About "minimum saturation"

It is a preference, not a hard floor. Plenty of covers are monochrome or
near-black and have nothing more colorful to offer. When nothing clears the bar,
Synkronize relaxes the window in rounds rather than giving up, and falls back to
the dominant color for genuinely greyscale artwork. You always get *a* color.

## Actions

```yaml
# Re-download the current artwork and re-apply it, bypassing the cache
action: synkronize.resync
target:
  entity_id: light.synkronize_spotify_bed_light
```

```yaml
# Apply any image's colors, ignoring the media player.
# Handy in automations, and for checking the pipeline without playing anything.
action: synkronize.apply_image
target:
  entity_id: light.synkronize_spotify_bed_light
data:
  image_url: /local/poster.jpg
```

Everything else is a stock action on the entity:

```yaml
action: light.turn_on
target:
  entity_id: light.synkronize_spotify_bed_light
data:
  effect: Dark Vibrant
  brightness: 200
```

## State attributes

| Attribute | Description |
| --- | --- |
| `sync_state` | `disabled`, `waiting`, `synced`, or `manual` |
| `source_media_player` | The media player being followed |
| `media_title` / `media_artist` | What is playing right now |
| `album_art_url` | The artwork the current color came from |
| `color_hex` | The color being shown, as `#rrggbb` |
| `swatches` | Every extracted swatch, as `name -> #rrggbb` |
| `extracted_palette` | The raw ColorThief palette, as `[R, G, B]` triples ordered by dominance |
| `dominant_hue` / `dominant_saturation` / `dominant_lightness` | HSL breakdown of the dominant color, for template branches |
| `applied_colors` | What each underlying light was actually set to |
| `light_entities` / `light_count` | The lights under Synkronize's control |
| `last_sync` | ISO timestamp of the last successful apply |
| `last_error` | Cleared on success; set when something went wrong |
| `failed_lights` | `entity_id -> reason` for lights that could not be updated |

`last_error` and `failed_lights` mean you can debug a misbehaving light from the
UI without opening the log. Reasons are `not_found`, `unavailable`,
`no_rgb_support`, and `service_call_failed`.

## Troubleshooting

**The lights never change.** Check `sync_state`. `waiting` means no artwork has
arrived yet - confirm the media player exposes an `entity_picture` attribute in
Developer Tools → States. Not every player does.

**"No internal Home Assistant URL is available".** Album art is usually served
as a relative path by Home Assistant's own media proxy, so Synkronize needs to
know its own address. Set one under Settings → System → Network.

**Colors look muddy.** Raise the saturation boost, or switch the swatch from
Dominant to Vibrant.

**A light did not update.** Read `failed_lights`. `no_rgb_support` means the
light cannot show color at all.

**More detail in the log:**

```yaml
logger:
  logs:
    custom_components.synkronize: debug
```

## Development

```bash
scripts/setup      # install dependencies
scripts/develop    # run Home Assistant on http://localhost:8123
scripts/lint       # ruff format + check
python3 -m pytest tests/
```

`config/configuration.yaml` enables the `demo` integration, which provides
`media_player.lounge_room` (it has album art) and `light.bed_light` /
`light.ceiling_lights`, so the whole feature can be exercised without any real
hardware.

The color scoring in `custom_components/synkronize/color_extractor.py` is
deliberately made of pure functions, so it is unit-testable without a Home
Assistant instance - see `tests/test_color_extractor.py`.

### Layout

| Module | Responsibility |
| --- | --- |
| `light.py` | The `light.synkronize_*` entity: state, effects, and the extract-and-apply pipeline |
| `color_extractor.py` | ColorThief extraction, vibrancy scoring, saturation boost |
| `album_art.py` | Resolving and downloading `entity_picture` |
| `media_watcher.py` | Artwork-change detection, debouncing, idle grace timer |
| `light_controller.py` | Talking to the real lights, with per-light error tracking |
| `snapshot.py` | Capturing and restoring the pre-sync light state |
| `config_flow.py` | Setup and options flows |

## License

MIT
