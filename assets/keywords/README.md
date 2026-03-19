Custom keyword packs live in this folder.

Each `.json` file can define one or more spoken-word categories with:
- category name
- colour theme
- MIDI note hint
- entries and aliases

Supported schema:

```json
{
  "categories": [
    {
      "name": "sea",
      "theme": {
        "hue": 0.56,
        "accent_hue": 0.62,
        "saturation": 0.88,
        "value": 0.96,
        "midi_note": 74
      },
      "entries": [
        { "word": "whale", "asset": "whale", "aliases": ["orca"] },
        { "word": "jellyfish", "asset": "jellyfish" }
      ]
    }
  ]
}
```

Notes:
- `asset` should match the media filename stem in `assets/animals/` or another category folder.
- Entries can be simple strings if the spoken word and asset name match.
- GIF files and sprite-sheet manifests are supported by the asset loader.
